from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
from dateutil.relativedelta import relativedelta

class ParkingContract(models.Model):
    _name = "parking.contract"
    _description = "Parking Contract"
    _rec_name = "name"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Contract Ref", required=True, copy=False, readonly=True, default=lambda self: _("New"))
    partner_id = fields.Many2one("res.partner", string="Customer", required=True, tracking=True)
    vehicle_ids = fields.Many2many("parking.vehicle", string="Vehicles", tracking=True)
    vehicle_count = fields.Integer(string="Vehicle Count", compute="_compute_vehicle_count")
    spot_id = fields.Many2one("parking.spot", string="Spot", required=True, tracking=True)
    location_id = fields.Many2one("parking.location", string="Branch", related="spot_id.location_id", store=True, tracking=True)
    vehicle_details = fields.Char(string="Vehicle Details", compute="_compute_vehicle_details")

    start_date = fields.Date(string="Start Date", required=True, default=fields.Date.today, tracking=True)
    end_date = fields.Date(string="End Date", required=True, tracking=True)
    subscription_type = fields.Selection([
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ], string="Subscription Type", required=True, default="monthly", tracking=True)

    price_tmpl_id = fields.Many2one("parking.price.template", string="Price Template", tracking=True)
    tax_ids = fields.Many2many("account.tax", string="Taxes", domain="[('type_tax_use', '=', 'sale'), ('company_id', '=', company_id)]", tracking=True)
    price_per_month = fields.Monetary(string="Price/Month", currency_field="company_currency_id", tracking=True)
    service_line_ids = fields.One2many("parking.contract.service.line", "contract_id", string="Additional Services", tracking=True)
    wash_ids = fields.One2many("parking.contract.wash", "contract_id", string="Car Washes")
    services_total = fields.Monetary(string="Services Total", compute="_compute_totals", currency_field="company_currency_id", store=True)

    amount_total = fields.Monetary(string="Total Amount", compute="_compute_totals", currency_field="company_currency_id", store=True, tracking=True)
    deposit_amount = fields.Monetary(string="Deposit Amount", currency_field="company_currency_id", tracking=True)
    deposit_invoiced = fields.Boolean(string="Deposit Invoiced", default=False, copy=False, help="Whether the deposit/insurance line has been added to a customer invoice.")

    user_id = fields.Many2one("res.users", string="Responsible Employee", default=lambda self: self.env.user, tracking=True)

    state = fields.Selection([
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ], string="Status", default="draft", tracking=True)

    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    notes = fields.Text(string="Notes")

    # Signature & Terms
    terms_id = fields.Many2one("parking.terms.conditions", string="T&C Template", tracking=True)
    terms_conditions = fields.Html(string="Terms & Conditions", translate=True)
    customer_signature = fields.Binary(string="Customer Signature", attachment=True)
    authorized_signature = fields.Binary(string="Authorized Signature", attachment=True)
    signature_date = fields.Date(string="Signature Date")

    history_ids = fields.One2many("parking.vehicle.movement", "contract_id", string="Check In/Out History")
    invoice_ids = fields.One2many("account.move", "parking_contract_id", string="Invoices")

    auto_invoice = fields.Boolean(string="Auto Generate Invoices", default=True, tracking=True)
    free_wash_count = fields.Integer(string="Free Washes Included", default=0)
    washes_used = fields.Integer(string="Washes Used", compute="_compute_wash_counts", store=True)
    remaining_washes = fields.Integer(string="Remaining Washes", compute="_compute_wash_counts", store=True)
    wash_interval_days = fields.Integer(string="Wash Interval (Days)", default=0)
    invoice_period = fields.Selection([
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
        ("one_time", "One Time"),
    ], string="Invoice Period", default="monthly", tracking=True)
    last_invoiced_date = fields.Date(string="Last Invoiced Date", readonly=True, copy=False)
    recurring_next_date = fields.Date(string="Next Invoice Date", readonly=True, copy=False)
    parking_product_id = fields.Many2one("product.product", string="Parking Product",
        domain="[('type', '=', 'service')]", tracking=True)
    invoice_count = fields.Integer(string="Invoice Count", compute="_compute_invoice_count")
    invoice_status = fields.Selection([
        ("no", "Nothing to Invoice"),
        ("to_invoice", "To Invoice"),
        ("invoiced", "Fully Invoiced"),
        ("paid", "Paid"),
    ], string="Invoice Status", compute="_compute_invoice_status", store=True)

    @api.depends("vehicle_ids")
    def _compute_vehicle_count(self):
        for r in self:
            r.vehicle_count = len(r.vehicle_ids)

    @api.depends("vehicle_ids", "vehicle_ids.license_plate", "vehicle_ids.brand", "vehicle_ids.model", "vehicle_ids.color", "vehicle_ids.owner_id")
    def _compute_vehicle_details(self):
        for r in self:
            if r.vehicle_ids:
                v = r.vehicle_ids[0]
                parts = [p for p in [v.brand, v.model, v.color, v.license_plate] if p]
                owner = v.owner_id.name if v.owner_id else ""
                r.vehicle_details = " / ".join(parts + ([owner] if owner else []))

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for r in self:
            r.invoice_count = len(r.invoice_ids)

    @api.depends("invoice_ids", "invoice_ids.payment_state", "state")
    def _compute_invoice_status(self):
        for r in self:
            if not r.invoice_ids:
                r.invoice_status = "no" if r.state == "draft" else "to_invoice"
            elif all(inv.payment_state == "paid" for inv in r.invoice_ids):
                r.invoice_status = "paid"
            elif any(inv.payment_state == "in_payment" for inv in r.invoice_ids):
                r.invoice_status = "to_invoice"
            else:
                r.invoice_status = "invoiced"

    @api.depends("service_line_ids", "service_line_ids.price_subtotal", "price_tmpl_id", "price_per_month")
    def _compute_totals(self):
        for r in self:
            base = r.price_per_month or (r.price_tmpl_id.price_per_month if r.price_tmpl_id else 0)
            svc_total = sum(line.price_subtotal for line in r.service_line_ids)
            r.services_total = svc_total
            r.amount_total = base + svc_total

    @api.model_create_multi
    def create(self, vals_list):
        contract_seq = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = contract_seq.next_by_code("parking.contract") or _("New")
            self._check_spot_availability(vals)
        records = super().create(vals_list)
        for record in records:
            if record.auto_invoice:
                record._update_recurring_next_date()
        return records

    def _get_invoice_period_dates(self, from_date=None):
        self.ensure_one()
        if not from_date:
            from_date = fields.Date.today()
        if self.invoice_period == "monthly":
            period_start = from_date.replace(day=1)
            period_end = period_start + relativedelta(months=1) - timedelta(days=1)
            label = _("Month of %s") % period_start.strftime("%B %Y")
        elif self.invoice_period == "quarterly":
            quarter_month = ((from_date.month - 1) // 3) * 3 + 1
            period_start = from_date.replace(month=quarter_month, day=1)
            period_end = period_start + relativedelta(months=3) - timedelta(days=1)
            label = _("Q%(q)s %(y)s") % {
                "q": (quarter_month // 3) + 1,
                "y": period_start.year,
            }
        elif self.invoice_period == "yearly":
            period_start = from_date.replace(month=1, day=1)
            period_end = period_start + relativedelta(years=1) - timedelta(days=1)
            label = _("Year %s") % period_start.year
        else:
            period_start = self.start_date or from_date
            period_end = self.end_date or from_date
            label = _("Parking Contract - %s") % self.name
        return period_start, period_end, label

    def _get_invoice_lines_vals(self, period_label):
        self.ensure_one()
        tax_ids = self._get_invoice_tax_ids()
        lines = []

        product = self.parking_product_id or self.env.ref(
            "parking_management.product_parking_service", False)
        product_id = product.id if product else False

        qty = 1.0
        price = self.amount_total - self.services_total
        if self.invoice_period == "monthly":
            name = _("Parking - %(spot)s (%(type)s) - %(ref)s - %(period)s",
                     spot=self.spot_id.full_name,
                     type=dict(self._fields["subscription_type"].selection).get(self.subscription_type),
                     ref=self.name,
                     period=period_label)
        else:
            name = _("Parking - %(spot)s - %(ref)s - %(period)s",
                     spot=self.spot_id.full_name,
                     ref=self.name,
                     period=period_label)

        lines.append((0, 0, {
            "name": name,
            "quantity": qty,
            "price_unit": price if price > 0 else self.price_per_month or 0,
            "product_id": product_id,
            "tax_ids": tax_ids,
        }))

        for line in self.service_line_ids:
            lines.append((0, 0, {
                "name": line.name,
                "quantity": line.quantity,
                "price_unit": line.price_unit,
                "product_id": line.product_id.id or False,
                "tax_ids": tax_ids,
            }))

        if self.deposit_amount and not self.deposit_invoiced:
            lines.append((0, 0, {
                "name": _("Refundable Deposit / Insurance - %(ref)s", ref=self.name),
                "quantity": 1.0,
                "price_unit": self.deposit_amount,
                "product_id": product_id,
                "tax_ids": [(5, 0, 0)],
            }))

        return lines

    def _auto_create_invoice(self, invoice_date=None):
        self.ensure_one()
        if not invoice_date:
            invoice_date = fields.Date.today()
        period_start, period_end, label = self._get_invoice_period_dates(invoice_date)
        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": invoice_date,
            "parking_contract_id": self.id,
            "invoice_origin": "%s - %s" % (self.name, label),
            "invoice_line_ids": self._get_invoice_lines_vals(label),
            "invoice_payment_term_id": self.partner_id.property_payment_term_id.id or False,
        }
        invoice = self.env["account.move"].create(invoice_vals)
        if self.deposit_amount and not self.deposit_invoiced:
            self.write({"deposit_invoiced": True})
        self.write({
            "last_invoiced_date": invoice_date,
            "recurring_next_date": self._compute_next_invoice_date(invoice_date),
        })
        self._send_invoice_notification(invoice)
        return invoice

    def _compute_next_invoice_date(self, from_date):
        self.ensure_one()
        if self.invoice_period == "monthly":
            return from_date + relativedelta(months=1)
        elif self.invoice_period == "quarterly":
            return from_date + relativedelta(months=3)
        elif self.invoice_period == "yearly":
            return from_date + relativedelta(years=1)
        else:
            return False

    def _update_recurring_next_date(self):
        self.ensure_one()
        if self.auto_invoice and not self.recurring_next_date:
            if self.invoice_period == "monthly":
                next_date = (self.start_date or fields.Date.today()).replace(day=1)
                next_date = next_date + relativedelta(months=1)
            elif self.invoice_period == "yearly":
                next_date = (self.start_date or fields.Date.today()).replace(month=1, day=1)
                next_date = next_date + relativedelta(years=1)
            elif self.invoice_period == "quarterly":
                q_month = ((self.start_date or fields.Date.today()).month - 1) // 3 * 3 + 1
                next_date = (self.start_date or fields.Date.today()).replace(month=q_month, day=1)
                next_date = next_date + relativedelta(months=3)
            else:
                next_date = self.end_date or fields.Date.today()
            self.recurring_next_date = next_date

    def _cron_generate_recurring_invoices(self):
        today = fields.Date.today()
        contracts = self.search([
            ("auto_invoice", "=", True),
            ("state", "in", ["active", "confirmed"]),
            ("recurring_next_date", "<=", today),
        ])
        for contract in contracts:
            try:
                contract._auto_create_invoice(today)
            except Exception as e:
                contract.env["ir.logging"].sudo().create({
                    "name": "Parking Invoice Cron",
                    "type": "server",
                    "level": "error",
                    "message": str(e),
                    "path": "parking_contract._cron_generate_recurring_invoices",
                    "func": "_cron_generate_recurring_invoices",
                })

    @api.onchange("subscription_type")
    def _onchange_subscription_type(self):
        if self.subscription_type == "yearly":
            self.invoice_period = "yearly"
        else:
            self.invoice_period = "monthly"

    @api.onchange("price_tmpl_id")
    def _onchange_price_tmpl_id(self):
        if self.price_tmpl_id:
            tmpl = self.price_tmpl_id
            self.price_per_month = tmpl.price_per_month or self.price_per_month
            self.deposit_amount = tmpl.deposit_amount if (tmpl.deposit_amount and not self.deposit_invoiced) else self.deposit_amount
            if tmpl.tax_id:
                self.tax_ids = [(6, 0, [tmpl.tax_id.id])]
        elif not self.price_tmpl_id:
            self.tax_ids = [(5, 0, 0)]

    @api.onchange("partner_id")
    def _onchange_partner_id_autofill(self):
        if self.partner_id:
            Contract = self.env["parking.contract"]
            last_contract = Contract.search([
                ("partner_id", "=", self.partner_id.id),
                ("state", "in", ["active", "confirmed"]),
            ], limit=1)
            if last_contract:
                if not self.spot_id:
                    self.spot_id = last_contract.spot_id
                if not self.vehicle_ids:
                    self.vehicle_ids = [(6, 0, last_contract.vehicle_ids.ids)]
                if not self.price_per_month:
                    self.price_per_month = last_contract.price_per_month
            elif not self.vehicle_ids:
                vehicles = self.env["parking.vehicle"].search([("owner_id", "=", self.partner_id.id)])
                if vehicles:
                    self.vehicle_ids = [(6, 0, vehicles.ids)]

    @api.onchange("vehicle_ids")
    def _onchange_vehicle_ids_autofill(self):
        if self.vehicle_ids and not self.partner_id:
            first = self.vehicle_ids[:1]
            if first.owner_id:
                self.partner_id = first.owner_id

    @api.onchange("terms_id")
    def _onchange_terms_id(self):
        if self.terms_id and self.terms_id.content:
            self.terms_conditions = self.terms_id.content

    @api.onchange("service_line_ids", "service_line_ids.service_id")
    def _onchange_service_line_ids_wash(self):
        wash_packages = self.service_line_ids.filtered(
            lambda l: l.service_id and l.service_id.category == "wash" and l.service_id.included_washes
        )
        if wash_packages:
            self.free_wash_count = max(l.service_id.included_washes for l in wash_packages)

    def write(self, vals):
        for rec in self:
            rec._check_spot_availability(vals)
        res = super().write(vals)
        if vals.get("spot_id"):
            for rec in self:
                if rec.spot_id:
                    rec.spot_id._update_status_from_contracts()
        return res

    def _check_spot_availability(self, vals):
        spot_id = vals.get("spot_id", self.spot_id.id) if vals.get("spot_id") else self.spot_id.id
        partner_id = vals.get("partner_id", self.partner_id.id) if vals.get("partner_id") else self.partner_id.id
        if not spot_id or not partner_id:
            return
        spot = self.env["parking.spot"].browse(spot_id)
        if spot.status == "maintenance":
            raise UserError(_(
                "The spot %s is under maintenance and cannot be used."
            ) % spot.full_name)
        if spot.status in ("reserved", "occupied", "client_out"):
            holding_contract = spot.contract_ids.filtered(
                lambda c: c.id != self.id and c.state in ("active", "confirmed"))[:1]
            if not holding_contract:
                return
            if holding_contract.partner_id.id != partner_id:
                raise UserError(_(
                    "The spot %(spot)s is currently %(status)s for customer %(customer)s. "
                    "You can only use it after the existing contract is ended, cancelled, "
                    "or the spot number is changed on that contract."
                ) % {
                    "spot": spot.full_name,
                    "status": spot.status,
                    "customer": holding_contract.partner_id.display_name,
                })

    @api.model
    def _default_terms(self):
        return _("""
<h4>General Terms and Conditions</h4>
<ol>
<li><b>Contract Period:</b> This contract is valid from the start date until the end date specified above.</li>
<li><b>Payment:</b> The customer agrees to pay the full subscription amount as per the agreed schedule.</li>
<li><b>Vehicle Access:</b> Only registered vehicles listed in the contract are permitted to use the parking spot.</li>
<li><b>Responsibility:</b> The parking facility is not responsible for any loss, theft, or damage to the vehicle or its contents.</li>
<li><b>Compliance:</b> The customer must comply with all parking facility rules and regulations.</li>
<li><b>Subletting:</b> The parking spot cannot be sublet or transferred to another party without written consent.</li>
<li><b>Termination:</b> Either party may terminate this contract with a notice period as per facility policy.</li>
<li><b>Maintenance:</b> The customer must keep the parking spot clean and report any damages immediately.</li>
<li><b>Security:</b> The customer must display the parking permit at all times while on the premises.</li>
<li><b>Governing Law:</b> This contract is governed by the laws of the Kingdom of Saudi Arabia.</li>
</ol>
<p>By signing this contract, you acknowledge that you have read, understood, and agree to all terms and conditions stated above.</p>
        """)

    def action_sign(self):
        self.ensure_one()
        if not self.customer_signature:
            raise UserError(_("Please capture the customer signature before signing."))
        self.write({
            "signature_date": fields.Date.today(),
            "state": "confirmed" if self.state == "draft" else self.state,
        })

    def action_confirm(self):
        self.write({"state": "confirmed"})
        if self.auto_invoice and not self.recurring_next_date:
            self._update_recurring_next_date()

    def action_activate(self):
        self.write({"state": "active"})
        if self.spot_id:
            self.spot_id.status = "occupied"
        if self.auto_invoice:
            self._update_recurring_next_date()
            if not self.invoice_ids:
                self._auto_create_invoice()

    def action_expire(self):
        self.write({"state": "expired"})
        if self.spot_id:
            self.spot_id.status = "available"

    def action_cancel(self):
        self.write({"state": "cancelled"})
        if self.spot_id:
            self.spot_id.status = "available"

    def action_check_out(self):
        """Register vehicle check-out (exit) for the contract's spot."""
        self.ensure_one()
        if not self.vehicle_ids:
            raise UserError(_("No vehicles registered on this contract."))
        if not self.spot_id:
            raise UserError(_("No spot assigned to this contract."))
        return self.spot_id.action_vehicle_checkout()

    def action_check_in(self):
        """Register vehicle check-in (return) for the contract's spot."""
        self.ensure_one()
        if not self.spot_id:
            raise UserError(_("No spot assigned to this contract."))
        return self.spot_id.action_vehicle_checkin()

    def _get_invoice_tax_ids(self):
        self.ensure_one()
        if self.tax_ids:
            return [(6, 0, self.tax_ids.ids)]
        return [(5, 0, 0)]

    def _is_arabic_context(self):
        import logging, traceback
        _logger = logging.getLogger(__name__)
        try:
            ctx_lang = self.env.context.get('lang', 'NONE')
            user_lang = self.env.user.lang
            result = (ctx_lang or user_lang or '').startswith('ar')
            _logger.info(f"_is_arabic_context: ctx.lang={ctx_lang!r} user.lang={user_lang!r} result={result}")
            return result
        except Exception as e:
            _logger.error(f"_is_arabic_context ERROR: {e}\n{traceback.format_exc()}")
            return False

    def action_create_invoice(self):
        self.ensure_one()
        if self.state == "draft":
            raise UserError(_("Please confirm the contract before creating an invoice."))
        invoice = self._auto_create_invoice()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "parking_management.action_parking_contract_invoices")
        action["domain"] = [("parking_contract_id", "=", self.id)]
        action["context"] = {
            "default_parking_contract_id": self.id,
            "default_partner_id": self.partner_id.id,
        }
        if self.invoice_count == 1:
            action["res_id"] = self.invoice_ids.id
            action["view_mode"] = "form"
        return action

    def action_register_payment(self):
        self.ensure_one()
        invoices = self.invoice_ids.filtered(lambda inv: inv.payment_state in ("not_paid", "partial"))
        if not invoices:
            raise UserError(_("There is no open invoice on this contract to pay. Create an invoice first."))
        return {
            "name": _("Register Payment"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment.register",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "account.move",
                "active_ids": invoices.ids,
                "active_id": invoices.ids[0],
            },
        }

    def action_generate_recurring(self):
        for r in self:
            r._cron_generate_recurring_invoices()
        return True

    def _cron_send_notifications(self):
        today = fields.Date.today()
        contracts = self.search([("state", "in", ["active", "confirmed"])])

        for contract in contracts:
            if not contract.end_date:
                continue
            days_left = (contract.end_date - today).days

            try:
                if days_left == 7:
                    contract._send_expiry_reminder(7)
                elif days_left == 3:
                    contract._send_expiry_reminder(3)
                elif days_left == 1:
                    contract._send_expiry_reminder(1)
                elif days_left == 0:
                    contract._send_expiry_notification()
                    contract.action_expire()
            except Exception:
                pass

    def _send_expiry_reminder(self, days_left):
        self.ensure_one()
        subject = _("Contract %(name)s expires in %(days)d day(s)", name=self.name, days=days_left)
        body = _("Your contract for spot %(spot)s expires on %(date)s.",
                 spot=self.spot_id.full_name, date=self.end_date)
        self.message_post(subject=subject, body=body, subtype_xmlid="mail.mt_comment")
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=subject,
            note=body,
            user_id=self.user_id.id or self.env.user.id,
            date_deadline=fields.Date.today(),
        )
        try:
            template = self.env.ref("parking_management.email_template_contract_expiry", False)
            if template:
                template.send_mail(self.id, force_send=False)
        except Exception:
            pass

    def _send_expiry_notification(self):
        self.ensure_one()
        subject = _("Contract %s has expired!") % self.name
        body = _("Contract %(name)s for spot %(spot)s has expired on %(date)s.",
                 name=self.name, spot=self.spot_id.full_name, date=self.end_date)
        self.message_post(subject=subject, body=body, subtype_xmlid="mail.mt_comment")
        try:
            template = self.env.ref("parking_management.email_template_contract_expired", False)
            if template:
                template.send_mail(self.id, force_send=False)
        except Exception:
            pass

    def _send_invoice_notification(self, invoice):
        self.ensure_one()
        try:
            template = self.env.ref("parking_management.email_template_invoice_created", False)
            if template:
                template.send_mail(invoice.id, force_send=False)
        except Exception:
            pass

    @api.depends("wash_ids", "wash_ids.state", "free_wash_count")
    def _compute_wash_counts(self):
        for r in self:
            used = len(r.wash_ids.filtered(lambda w: w.state == "done"))
            r.washes_used = used
            r.remaining_washes = max(0, r.free_wash_count - used)