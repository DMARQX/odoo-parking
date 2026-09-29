import json
import logging
import re

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT = 20
MAX_ATTEMPTS = 3

EVENTS = [
    ("vehicle_received", "Vehicle received (check in)"),
    ("vehicle_delivered", "Vehicle delivered (check out)"),
    ("contract_activated", "Contract activated"),
    ("contract_expiring", "Contract expiring soon"),
    ("contract_expired", "Contract expired"),
    ("invoice_created", "Invoice created"),
    ("wash_done", "Car wash done"),
]


PLACEHOLDER = re.compile(r"\{(\w+)\}")


def render(template, values):
    """Replace {name} placeholders that exist in values; leave every other brace alone.

    str.format would choke on JSON bodies ({"to": ...}) and on stray braces in messages.
    """
    return PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), template or "")


class ParkingMessagingGateway(models.Model):
    _name = "parking.messaging.gateway"
    _description = "SMS / WhatsApp Gateway"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    channel = fields.Selection([("sms", "SMS"), ("whatsapp", "WhatsApp")], required=True, default="sms")
    provider = fields.Selection([
        ("odoo_sms", "Odoo SMS (IAP credits)"),
        ("twilio", "Twilio"),
        ("unifonic", "Unifonic"),
        ("meta_whatsapp", "WhatsApp Cloud API (Meta)"),
        ("generic_http", "Generic HTTP API"),
    ], required=True, default="generic_http")

    # Credentials: visible to parking managers and administrators only.
    account_sid = fields.Char(string="Account SID / App ID", groups="parking_management.group_parking_manager",
                              help="Twilio Account SID or Unifonic AppSid.")
    api_key = fields.Char(string="API Key / Token", groups="parking_management.group_parking_manager",
                          help="Twilio auth token, Meta access token or the generic API key.")
    sender = fields.Char(string="Sender", help="Sender name or number (Twilio from number, Unifonic SenderID).")
    phone_number_id = fields.Char(string="WhatsApp Phone Number ID", help="Meta WhatsApp Cloud API phone number id.")
    api_version = fields.Char(string="API Version", default="v20.0")

    # Generic HTTP API
    endpoint = fields.Char(string="Endpoint URL")
    http_method = fields.Selection([("POST", "POST"), ("GET", "GET")], default="POST")
    auth_type = fields.Selection([
        ("none", "None"), ("bearer", "Bearer token"), ("basic", "Basic (user + key)"), ("header", "Custom header"),
    ], default="bearer")
    auth_header_name = fields.Char(string="Auth Header Name", default="X-API-Key")
    username = fields.Char(string="Username", groups="parking_management.group_parking_manager")
    payload_type = fields.Selection([("json", "JSON body"), ("form", "Form fields"), ("query", "URL parameters")],
                                    default="json")
    payload_template = fields.Text(
        string="Payload Template",
        default='{"to": "{to}", "message": "{message}", "sender": "{sender}"}',
        help="JSON object; {to}, {message}, {sender} are replaced when sending.")
    success_codes = fields.Char(string="Success HTTP Codes", default="200,201,202")

    test_number = fields.Char(string="Test Number")
    last_test_result = fields.Text(string="Last Test Result", readonly=True)

    # ------------------------------------------------------------------ utils
    def _format_number(self, number):
        """Digits in international format without '+' (e.g. 9665XXXXXXXX)."""
        digits = re.sub(r"\D", "", number or "")
        if not digits:
            return ""
        cc = (self.company_id.parking_phone_country_code or "966").lstrip("+")
        if digits.startswith("00"):
            digits = digits[2:]
        elif digits.startswith("0"):
            digits = cc + digits[1:]
        elif len(digits) <= 9:
            digits = cc + digits
        return digits

    def _json_escape(self, value):
        return json.dumps(value or "")[1:-1]

    # ---------------------------------------------------------------- sending
    def _send(self, number, body, wa_template=None, wa_lang=None, wa_params=None):
        """Send one message. Returns (ok, detail)."""
        self.ensure_one()
        to = self._format_number(number)
        if not to:
            return False, _("No valid phone number.")
        gateway = self.sudo()
        try:
            handler = getattr(gateway, "_send_%s" % gateway.provider)
            return handler(to, body, wa_template, wa_lang, wa_params or [])
        except requests.RequestException as e:
            return False, _("Connection error: %s", e)

    def _check_response(self, response):
        codes = [int(c) for c in re.findall(r"\d+", self.success_codes or "200")] or [200]
        ok = response.status_code in codes
        return ok, "%s %s" % (response.status_code, (response.text or "")[:500])

    def _send_odoo_sms(self, to, body, *args):
        self.env["sms.sms"].sudo().create({"number": "+" + to, "body": body}).send()
        return True, _("Queued in Odoo SMS.")

    def _send_twilio(self, to, body, *args):
        prefix = "whatsapp:" if self.channel == "whatsapp" else ""
        response = requests.post(
            "https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json" % self.account_sid,
            data={"To": prefix + "+" + to, "From": prefix + (self.sender or ""), "Body": body},
            auth=(self.account_sid or "", self.api_key or ""), timeout=TIMEOUT)
        return self._check_response(response)

    def _send_unifonic(self, to, body, *args):
        response = requests.post(
            self.endpoint or "https://el.cloud.unifonic.com/rest/SMS/messages",
            data={"AppSid": self.account_sid, "SenderID": self.sender, "Recipient": to, "Body": body},
            timeout=TIMEOUT)
        return self._check_response(response)

    def _send_meta_whatsapp(self, to, body, wa_template, wa_lang, wa_params):
        # Messages that start a conversation must use an approved template.
        if wa_template:
            payload = {
                "messaging_product": "whatsapp", "to": to, "type": "template",
                "template": {
                    "name": wa_template, "language": {"code": wa_lang or "ar"},
                    "components": [{"type": "body", "parameters": [
                        {"type": "text", "text": str(p)} for p in wa_params]}] if wa_params else [],
                },
            }
        else:
            payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}}
        response = requests.post(
            "https://graph.facebook.com/%s/%s/messages" % (self.api_version or "v20.0", self.phone_number_id),
            json=payload, headers={"Authorization": "Bearer %s" % self.api_key}, timeout=TIMEOUT)
        return self._check_response(response)

    def _send_generic_http(self, to, body, *args):
        if not self.endpoint:
            raise UserError(_("Set the endpoint URL of gateway %s.", self.name))
        values = {"to": self._json_escape(to), "message": self._json_escape(body),
                  "sender": self._json_escape(self.sender)}
        try:
            payload = json.loads(render(self.payload_template or "{}", values))
        except ValueError as e:
            return False, _("Invalid payload template: %s", e)
        headers = {}
        auth = None
        if self.auth_type == "bearer":
            headers["Authorization"] = "Bearer %s" % (self.api_key or "")
        elif self.auth_type == "header":
            headers[self.auth_header_name or "X-API-Key"] = self.api_key or ""
        elif self.auth_type == "basic":
            auth = (self.username or "", self.api_key or "")
        kwargs = {"headers": headers, "auth": auth, "timeout": TIMEOUT}
        if self.payload_type == "json" and self.http_method == "POST":
            kwargs["json"] = payload
        elif self.payload_type == "form" and self.http_method == "POST":
            kwargs["data"] = payload
        else:
            kwargs["params"] = payload
        response = requests.request(self.http_method or "POST", self.endpoint, **kwargs)
        return self._check_response(response)

    def action_send_test(self):
        self.ensure_one()
        if not self.test_number:
            raise UserError(_("Enter a test number first."))
        ok, detail = self._send(self.test_number, _("Test message from %s", self.company_id.name))
        self.last_test_result = ("OK: " if ok else "FAILED: ") + (detail or "")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success" if ok else "danger",
                "message": self.last_test_result,
                "sticky": not ok,
            },
        }


class ParkingNotificationRule(models.Model):
    _name = "parking.notification.rule"
    _description = "Customer Notification Rule"
    _order = "event, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    event = fields.Selection(EVENTS, required=True)
    channel = fields.Selection([("sms", "SMS"), ("whatsapp", "WhatsApp"), ("both", "SMS and WhatsApp")],
                               required=True, default="sms")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    body = fields.Text(
        string="Message", required=True, translate=True,
        help="Placeholders: {customer} {plate} {vehicle} {spot} {branch} {contract} {end_date} "
             "{days} {amount} {invoice} {company} {date}")
    wa_template = fields.Char(string="WhatsApp Template Name",
                              help="Approved Meta template to use for WhatsApp (required by Meta "
                                   "for business-initiated messages). Leave empty to send the text.")
    wa_lang = fields.Char(string="Template Language", default="ar")
    wa_params = fields.Char(string="Template Parameters", default="customer,plate",
                            help="Comma-separated placeholder names filled into the template, in order.")
    log_count = fields.Integer(compute="_compute_log_count")

    def _compute_log_count(self):
        Log = self.env["parking.message.log"]
        for rule in self:
            rule.log_count = Log.search_count([("rule_id", "=", rule.id)])

    # ------------------------------------------------------------ rendering
    @api.model
    def _values(self, record, partner, extra=None):
        today = fields.Date.context_today(self)
        values = {"customer": partner.name or "", "company": record.env.company.name, "date": str(today)}
        model = record._name
        contract = vehicle = spot = self.env["parking.contract"]
        if model == "parking.contract":
            contract = record
        elif model in ("parking.vehicle.movement", "parking.contract.wash"):
            contract = record.contract_id
            vehicle = record.vehicle_id
        elif model == "account.move":
            contract = record.parking_contract_id
            values.update({"invoice": record.name or "", "amount": "%.2f" % record.amount_total})
        vehicle = vehicle or contract.vehicle_ids[:1]
        spot = getattr(record, "spot_id", False) or contract.spot_id
        values.update({
            "contract": contract.name or "",
            "end_date": str(contract.end_date or ""),
            "amount": values.get("amount") or ("%.2f" % contract.amount_total if contract else ""),
            "plate": vehicle.license_plate or "",
            "vehicle": vehicle.display_name or "",
            "spot": spot.display_name if spot else "",
            "branch": (spot.location_id.name if spot else "") or contract.location_id.name or "",
        })
        values.update(extra or {})
        return {k: str(v) for k, v in values.items()}

    @api.model
    def _notify(self, event, record, partner, extra=None):
        """Queue the messages of every active rule for this event. Never raises."""
        try:
            record = record.sudo()
            partner = partner.sudo()
            company = getattr(record, "company_id", False) or self.env.company
            rules = self.sudo().search([("event", "=", event), ("company_id", "=", company.id)])
            if not rules or not partner:
                return
            number = partner.mobile or partner.phone
            values = self._values(record, partner, extra)
            Log = self.env["parking.message.log"].sudo()
            for rule in rules.with_context(lang=partner.lang or self.env.lang):
                channels = ["sms", "whatsapp"] if rule.channel == "both" else [rule.channel]
                for channel in channels:
                    gateway = company["parking_%s_gateway_id" % channel]
                    body = render(rule.body, values)
                    params = [values.get(p.strip(), "") for p in (rule.wa_params or "").split(",") if p.strip()]
                    Log.create({
                        "rule_id": rule.id,
                        "event": event,
                        "channel": channel,
                        "gateway_id": gateway.id,
                        "partner_id": partner.id,
                        "number": number or "",
                        "body": body,
                        "wa_params": json.dumps(params, ensure_ascii=False),
                        "res_model": record._name,
                        "res_id": record.id,
                        "company_id": company.id,
                        "state": "queued" if (gateway and number) else "skipped",
                        "error": False if (gateway and number) else (
                            _("No %s gateway configured.", channel) if not gateway else _("Customer has no mobile number.")),
                    })
        except Exception:
            _logger.exception("Parking notification for %s failed", event)

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Message Log"),
            "res_model": "parking.message.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }


class ParkingMessageLog(models.Model):
    _name = "parking.message.log"
    _description = "Customer Message Log"
    _order = "create_date desc, id desc"

    rule_id = fields.Many2one("parking.notification.rule", ondelete="set null")
    event = fields.Selection(EVENTS)
    channel = fields.Selection([("sms", "SMS"), ("whatsapp", "WhatsApp")])
    gateway_id = fields.Many2one("parking.messaging.gateway", ondelete="set null")
    partner_id = fields.Many2one("res.partner", string="Customer")
    number = fields.Char()
    body = fields.Text(string="Message")
    wa_params = fields.Text(string="Template Parameters")
    state = fields.Selection([("queued", "Queued"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")],
                             default="queued", index=True)
    attempts = fields.Integer()
    error = fields.Text(string="Result / Error")
    sent_date = fields.Datetime()
    res_model = fields.Char(string="Related Model")
    res_id = fields.Integer(string="Related Record")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    def _process(self):
        for log in self:
            rule = log.rule_id
            ok, detail = log.gateway_id._send(
                log.number, log.body,
                wa_template=rule.wa_template if log.channel == "whatsapp" else None,
                wa_lang=rule.wa_lang,
                wa_params=json.loads(log.wa_params or "[]"))
            attempts = log.attempts + 1
            log.write({
                "attempts": attempts,
                "error": detail,
                "state": "sent" if ok else ("failed" if attempts >= MAX_ATTEMPTS else "queued"),
                "sent_date": fields.Datetime.now() if ok else False,
            })

    @api.model
    def _cron_send_queued(self, limit=100):
        logs = self.sudo().search([("state", "=", "queued"), ("gateway_id", "!=", False)], limit=limit,
                                  order="id")
        for log in logs:
            try:
                with self.env.cr.savepoint():
                    log._process()
            except Exception as e:
                _logger.exception("Parking message %s failed", log.id)
                log.write({"attempts": log.attempts + 1, "error": str(e),
                           "state": "failed" if log.attempts + 1 >= MAX_ATTEMPTS else "queued"})

    def action_retry(self):
        self.filtered(lambda l: l.state in ("failed", "skipped") and l.gateway_id and l.number).write(
            {"state": "queued", "attempts": 0})
        return True

    def action_open_record(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return False
        return {"type": "ir.actions.act_window", "res_model": self.res_model, "res_id": self.res_id,
                "view_mode": "form", "target": "current"}
