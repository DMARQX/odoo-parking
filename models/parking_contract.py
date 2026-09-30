from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

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
        ("daily", "Daily"),
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ], string="Subscription Type", required=True, default="monthly", tracking=True)
    price_per_day = fields.Monetary(string="Price/Day", currency_field="company_currency_id", tracking=True)
    booking_days = fields.Integer(string="Days", compute="_compute_booking_days",
        help="Number of days from the start date to the end date, both included.")

    price_tmpl_id = fields.Many2one("parking.price.template", string="Price Template", tracking=True)
    tax_ids = fields.Many2many("account.tax", string="Taxes", domain="[('type_tax_use', '=', 'sale'), ('company_id', '=', company_id)]", tracking=True,
        default=lambda self: self.env.company.account_sale_tax_id,
        help="Leave empty to use each product's sales tax (the company default VAT when the product has none).")
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
    free_wash_count = fields.Integer(string="Washes per Month", default=0,
        help="Washes included in the subscription each month. They are added to the wash balance "
             "whenever a subscription invoice is issued.")
    wash_credit_ids = fields.One2many("parking.wash.credit", "contract_id", string="Wash Balance History")
    washes_credited = fields.Integer(string="Washes Credited", compute="_compute_wash_counts", store=True)
    washes_used = fields.Integer(string="Washes Used", compute="_compute_wash_counts", store=True)
    remaining_washes = fields.Integer(string="Remaining Washes", compute="_compute_wash_counts", store=True)
    payment_term_id = fields.Many2one("account.payment.term", string="Payment Terms",
        help="Used on this contract's invoices, e.g. instalments. Defaults to the customer's terms.")
    prepaid_until = fields.Date(string="Prepaid Until", readonly=True, copy=False,
        help="The remaining term was billed in one invoice up to this date; no more periodic invoices.")
    amount_invoiced = fields.Monetary(string="Invoiced", compute="_compute_amount_due",
        currency_field="company_currency_id")
    amount_paid = fields.Monetary(string="Paid", compute="_compute_amount_due",
        currency_field="company_currency_id")
    statement_html = fields.Html(string="Account Statement", compute="_compute_statement_html", sanitize=False)
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
    movement_count = fields.Integer(string="Movements", compute="_compute_related_counts")
    wash_count = fields.Integer(string="Washes", compute="_compute_related_counts")
    days_remaining = fields.Integer(string="Days Remaining", compute="_compute_days_remaining",
        help="Days left until the contract end date (negative once it has passed).")
    is_expiring_soon = fields.Boolean(string="Expiring Soon", compute="_compute_days_remaining",
        search="_search_is_expiring_soon",
        help="Active or confirmed contract that ends within the next 7 days.")
    amount_due = fields.Monetary(string="Amount Due", compute="_compute_amount_due",
        currency_field="company_currency_id",
        help="Open balance of this contract's posted customer invoices.")
    renewed_from_id = fields.Many2one("parking.contract", string="Renewed From", readonly=True, copy=False)
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
            else:
                r.vehicle_details = ""

    def _compute_related_counts(self):
        Movement = self.env["parking.vehicle.movement"]
        for r in self:
            r.movement_count = Movement.search_count([("contract_id", "=", r.id)]) if r.id else 0
            r.wash_count = len(r.wash_ids)

    @api.depends("end_date", "state")
    def _compute_days_remaining(self):
        today = fields.Date.context_today(self)
        for r in self:
            r.days_remaining = (r.end_date - today).days if r.end_date else 0
            r.is_expiring_soon = bool(
                r.end_date and r.state in ("active", "confirmed") and 0 <= r.days_remaining <= 7)

    def _search_is_expiring_soon(self, operator, value):
        today = fields.Date.context_today(self)
        domain = [("state", "in", ("active", "confirmed")),
                  ("end_date", ">=", today), ("end_date", "<=", today + timedelta(days=7))]
        if (operator == "=") != bool(value):
            return ["!"] + ["&"] * 2 + domain
        return domain

    @api.depends("invoice_ids.amount_residual", "invoice_ids.state")
    def _compute_amount_due(self):
        for r in self:
            moves = r.sudo().invoice_ids.filtered(
                lambda m: m.state == "posted" and m.move_type in ("out_invoice", "out_refund"))
            r.amount_invoiced = sum(moves.mapped("amount_total_signed"))
            r.amount_due = sum(moves.mapped("amount_residual_signed"))
            r.amount_paid = r.amount_invoiced - r.amount_due

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for r in self:
            r.invoice_count = len(r.invoice_ids)

    @api.depends("invoice_ids", "invoice_ids.state", "invoice_ids.payment_state", "state")
    def _compute_invoice_status(self):
        for r in self:
            # Drafts are not billed yet and cancelled invoices never will be.
            posted = r.invoice_ids.filtered(lambda m: m.state == "posted" and m.move_type == "out_invoice")
            if not posted:
                r.invoice_status = "no" if r.state == "draft" else "to_invoice"
            elif all(inv.payment_state in ("paid", "in_payment", "reversed") for inv in posted):
                r.invoice_status = "paid"
            else:
                r.invoice_status = "invoiced"

    @api.depends("start_date", "end_date")
    def _compute_booking_days(self):
        for r in self:
            r.booking_days = (r.end_date - r.start_date).days + 1 if r.start_date and r.end_date else 0

    def _get_day_price(self):
        self.ensure_one()
        monthly = self.price_per_month or self.price_tmpl_id.price_per_month
        return self.price_per_day or self.price_tmpl_id.price_per_day or round((monthly or 0) / 30.0, 2)

    @api.depends("service_line_ids", "service_line_ids.price_subtotal", "service_line_ids.billing_type",
                 "service_line_ids.invoice_id", "price_tmpl_id", "price_per_month",
                 "price_per_day", "subscription_type", "start_date", "end_date")
    def _compute_totals(self):
        for r in self:
            if r.subscription_type == "daily":
                # A daily booking is billed once for all its days.
                base = r._get_day_price() * r.booking_days
            else:
                base = r.price_per_month or (r.price_tmpl_id.price_per_month if r.price_tmpl_id else 0)
            # What the next invoice will bill: add-ons plus one-time items not billed yet.
            svc_total = sum(r.service_line_ids._is_billable().mapped("price_subtotal"))
            r.services_total = svc_total
            r.amount_total = base + svc_total

    @api.model_create_multi
    def create(self, vals_list):
        contract_seq = self.env["ir.sequence"]
        for vals in vals_list:
            # The default name is translated when the form opens ("جديد" in Arabic),
            # so compare against every placeholder, not just the current language.
            if not vals.get("name") or vals.get("name") in ("New", "جديد", "/", _("New")):
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

    def _get_period_months(self):
        """Number of monthly fees covered by one invoice of this contract."""
        self.ensure_one()
        if self.invoice_period == "quarterly":
            return 3.0
        if self.invoice_period == "yearly":
            return 12.0
        if self.invoice_period == "one_time" and self.start_date and self.end_date:
            delta = relativedelta(self.end_date + timedelta(days=1), self.start_date)
            return float(delta.years * 12 + delta.months + (1 if delta.days else 0))
        return 1.0

    def _get_line_accounting_vals(self, period_start=None, period_end=None, deferrable=False):
        """Branch analytic distribution and, for multi-month lines, the deferral period."""
        self.ensure_one()
        vals = {}
        analytic = self.location_id.analytic_account_id
        if analytic:
            vals["analytic_distribution"] = {str(analytic.id): 100}
        line_fields = self.env["account.move.line"]._fields
        if (deferrable and period_start and period_end and self.company_id.parking_use_deferred_revenue
                and self.subscription_type != "daily"
                and "deferred_start_date" in line_fields and self._get_period_months() > 1):
            vals.update({"deferred_start_date": period_start, "deferred_end_date": period_end})
        return vals

    def _get_invoice_lines_vals(self, period_label, period_start=None, period_end=None, months=None):
        self.ensure_one()
        product = self.parking_product_id or self.env.ref(
            "parking_management.product_parking_service", False)
        product_id = product.id if product else False
        lines = []
        acc_vals = self._get_line_accounting_vals(period_start, period_end, deferrable=True)

        qty = self._get_period_months()
        price = self.amount_total - self.services_total
        if self.subscription_type == "daily":
            # One line for the whole booking: days x daily price.
            qty = float(self.booking_days or 1)
            price = self._get_day_price()
            name = _("Parking - %(spot)s - %(ref)s - %(days)s day(s) from %(start)s to %(end)s",
                     spot=self.spot_id.full_name, ref=self.name, days=self.booking_days,
                     start=self.start_date, end=self.end_date)
        elif self.invoice_period == "monthly":
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

        lines.append((0, 0, dict(acc_vals, **{
            "name": name,
            "quantity": qty,
            "price_unit": price if price > 0 else self.price_per_month or 0,
            "product_id": product_id,
            "tax_ids": self._get_invoice_tax_ids(product),
        })))

        service_acc_vals = self._get_line_accounting_vals()
        # Subscription add-ons are per month, so a quarterly invoice bills them three times.
        months = 1 if self.subscription_type == "daily" else (months or self._get_period_months())
        for line in self.service_line_ids._is_billable():
            factor = months if line.billing_type == "recurring" else 1
            lines.append((0, 0, dict(service_acc_vals, **{
                "name": line.name,
                "quantity": line.quantity * factor,
                "price_unit": line.price_unit,
                "product_id": line.product_id.id or False,
                "tax_ids": self._get_invoice_tax_ids(line.product_id),
            })))

        if self.deposit_amount and not self.deposit_invoiced:
            deposit_account = self.company_id.parking_deposit_account_id
            deposit_line = {
                "name": _("Refundable Deposit / Insurance - %(ref)s", ref=self.name),
                "quantity": 1.0,
                "price_unit": self.deposit_amount,
                "tax_ids": [(5, 0, 0)],
            }
            if deposit_account:
                # A refundable deposit is owed back to the customer: a liability, not revenue.
                deposit_line["account_id"] = deposit_account.id
            else:
                deposit_line["product_id"] = product_id
            lines.append((0, 0, deposit_line))

        return lines

    def _auto_create_invoice(self, invoice_date=None):
        self.ensure_one()
        if not invoice_date:
            invoice_date = fields.Date.today()
        period_start, period_end, label = self._get_invoice_period_dates(invoice_date)
        origin = "%s - %s" % (self.name, label)
        if self.invoice_ids.filtered(lambda m: m.state != "cancel" and m.invoice_origin == origin):
            raise UserError(_("An invoice for %s already exists. Cancel it first to issue a new one.", origin))
        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": invoice_date,
            "parking_contract_id": self.id,
            "invoice_origin": origin,
            "invoice_line_ids": self._get_invoice_lines_vals(label, period_start, period_end),
            "invoice_payment_term_id": self._get_payment_term().id,
        }
        one_time = self.service_line_ids._is_billable().filtered(lambda l: l.billing_type == "one_time")
        # Issued by the system: contract staff activate contracts without
        # holding accounting rights, and the recurring cron has none either.
        invoice = self.env["account.move"].sudo().with_company(self.company_id).create(invoice_vals)
        one_time.sudo().write({"invoice_id": invoice.id})
        self._grant_period_washes(1 if self.subscription_type == "daily" else self._get_period_months(), invoice)
        if self.company_id.parking_auto_post_invoices and invoice.amount_total > 0:
            invoice.action_post()
        self.env["parking.notification.rule"]._notify("invoice_created", invoice, self.partner_id)
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
            ("state", "=", "active"),
            ("recurring_next_date", "<=", today),
        ])
        for contract in contracts:
            if contract.end_date and contract.recurring_next_date > contract.end_date:
                contract.recurring_next_date = False
                continue
            try:
                with self.env.cr.savepoint():
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
        elif self.subscription_type == "daily":
            self.invoice_period = "one_time"
        else:
            self.invoice_period = "monthly"

    @api.onchange("start_date", "subscription_type")
    def _onchange_period_end_date(self):
        # Propose the natural end of the first term; the user can still change it.
        if self.start_date:
            if self.subscription_type == "daily":
                if not self.end_date or self.end_date < self.start_date:
                    self.end_date = self.start_date
                return
            term = relativedelta(years=1) if self.subscription_type == "yearly" else relativedelta(months=1)
            self.end_date = self.start_date + term - timedelta(days=1)

    @api.onchange("start_date", "end_date", "subscription_type")
    def _onchange_short_monthly_booking(self):
        if (self.subscription_type == "monthly" and self.start_date and self.end_date
                and (self.end_date - self.start_date).days + 1 < 28):
            return {"warning": {
                "title": _("Short booking"),
                "message": _("This booking lasts %(days)s day(s) but is set as monthly, so a full month "
                             "will be billed. Choose the Daily subscription to bill by the day.",
                             days=(self.end_date - self.start_date).days + 1),
            }}

    @api.onchange("spot_id")
    def _onchange_spot_id_pricing(self):
        if self.spot_id.price_tmpl_id and not self.price_tmpl_id:
            self.price_tmpl_id = self.spot_id.price_tmpl_id
            self._onchange_price_tmpl_id()

    @api.onchange("price_tmpl_id")
    def _onchange_price_tmpl_id(self):
        if self.price_tmpl_id:
            tmpl = self.price_tmpl_id
            self.price_per_month = tmpl.price_per_month or self.price_per_month
            self.price_per_day = tmpl.price_per_day or self.price_per_day
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
        # Recurring wash packages make up the monthly wash allowance.
        wash_packages = self.service_line_ids.filtered(
            lambda l: l.service_id and l.service_id.category == "wash" and l.service_id.included_washes
            and l.billing_type == "recurring"
        )
        if wash_packages:
            self.free_wash_count = int(sum(l.service_id.included_washes * l.quantity for l in wash_packages))

    def write(self, vals):
        if {"spot_id", "partner_id"} & set(vals):
            for rec in self.filtered(lambda c: c.state in ("draft", "confirmed", "active")):
                rec._check_spot_availability(vals)
        old_spots = self.spot_id
        res = super().write(vals)
        if vals.get("spot_id"):
            (old_spots | self.spot_id)._update_status_from_contracts()
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

    def _check_state(self, allowed, action):
        bad = self.filtered(lambda c: c.state not in allowed)
        if bad:
            raise UserError(_("You cannot %(action)s contract(s) in this status: %(names)s",
                              action=action, names=", ".join(bad.mapped("name"))))

    def action_confirm(self):
        self._check_state(("draft",), _("confirm"))
        self.write({"state": "confirmed"})
        if self.auto_invoice and not self.recurring_next_date:
            self._update_recurring_next_date()

    def action_activate(self):
        self._check_state(("confirmed",), _("activate"))
        for rec in self:
            if rec.spot_id.status == "maintenance":
                raise UserError(_("The spot %s is under maintenance and cannot be activated.", rec.spot_id.full_name))
            rec.write({"state": "active"})
            if rec.spot_id:
                rec.spot_id._set_status("occupied")
            if rec.auto_invoice:
                rec._update_recurring_next_date()
                if not rec.invoice_ids:
                    rec._auto_create_invoice()
            self.env["parking.notification.rule"]._notify("contract_activated", rec, rec.partner_id)

    def action_expire(self):
        self._check_state(("active", "confirmed"), _("expire"))
        self.write({"state": "expired"})
        self.spot_id._update_status_from_contracts()

    def action_cancel(self):
        self._check_state(("draft", "confirmed", "active"), _("cancel"))
        self.write({"state": "cancelled"})
        self.spot_id._update_status_from_contracts()

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

    def _get_invoice_tax_ids(self, product=None):
        """Taxes for an invoice line: the contract's, else the product's, else the company VAT.

        An empty tax field on the contract used to clear the taxes, so invoices
        were posted without VAT.
        """
        self.ensure_one()
        taxes = self.tax_ids
        if not taxes and product:
            taxes = product.taxes_id.filtered(lambda t: t.company_id == self.company_id)
        if not taxes:
            taxes = self.company_id.account_sale_tax_id
        return [(6, 0, taxes.ids)]

    def _is_arabic_context(self):
        return (self.env.context.get("lang") or self.env.user.lang or "").startswith("ar")

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

    def action_renew(self):
        """Create the next-term contract as a draft, keeping customer, spot and pricing."""
        self.ensure_one()
        self._check_state(("active", "expired"), _("renew"))
        start = (self.end_date or fields.Date.context_today(self)) + timedelta(days=1)
        if self.subscription_type == "daily":
            # A daily booking is renewed for the same number of days.
            term = relativedelta(days=self.booking_days or 1)
        else:
            term = relativedelta(years=1) if self.subscription_type == "yearly" else relativedelta(months=1)
        new = self.copy({
            "start_date": start,
            "end_date": start + term - timedelta(days=1),
            "renewed_from_id": self.id,
            "state": "draft",
            # The deposit is held across terms; do not bill it again on renewal.
            "deposit_invoiced": self.deposit_invoiced,
            # One-time charges belong to the old term; only subscription add-ons carry over.
            "service_line_ids": [(0, 0, {
                "service_id": line.service_id.id,
                "quantity": line.quantity,
                "price_unit": line.price_unit,
                "billing_type": "recurring",
            }) for line in self.service_line_ids.filtered(lambda l: l.billing_type == "recurring")],
            "customer_signature": False,
            "authorized_signature": False,
            "signature_date": False,
        })
        # Logged note: works for staff without an email address, unlike message_post.
        self._message_log(body=_("Renewed by contract %s.", new._get_html_link()))
        new._message_log(body=_("Renewal of contract %s.", self._get_html_link()))
        return {
            "type": "ir.actions.act_window",
            "res_model": "parking.contract",
            "res_id": new.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_movements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Vehicle Movements"),
            "res_model": "parking.vehicle.movement",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id, "default_spot_id": self.spot_id.id},
        }

    def action_view_washes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Car Washes"),
            "res_model": "parking.contract.wash",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id,
                        "default_vehicle_id": self.vehicle_ids[:1].id},
        }

    # ------------------------------------------------------------------
    # Charges, remaining-term billing and account statement
    # ------------------------------------------------------------------
    def _get_payment_term(self):
        self.ensure_one()
        return self.payment_term_id or self.partner_id.property_payment_term_id

    def _wash_credits_for(self, service, quantity):
        if service and service.category == "wash":
            return int((service.included_washes or 1) * quantity)
        return 0

    def _create_charge_invoice(self, charges, payment_term=None):
        """Invoice one sale on its own invoice, linked to the contract.

        charges: list of dicts with service, product, name, quantity, price_unit.
        """
        self.ensure_one()
        acc_vals = self._get_line_accounting_vals()
        lines = []
        for ch in charges:
            product = ch.get("product") or (ch.get("service") and ch["service"].product_id) or self.env["product.product"]
            lines.append((0, 0, dict(acc_vals, **{
                "name": ch.get("name") or (ch.get("service") and ch["service"].name) or product.display_name,
                "quantity": ch.get("quantity") or 1.0,
                "price_unit": ch.get("price_unit") or 0.0,
                "product_id": product.id or False,
                "tax_ids": self._get_invoice_tax_ids(product),
            })))
        invoice = self.env["account.move"].sudo().with_company(self.company_id).create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": fields.Date.context_today(self),
            "parking_contract_id": self.id,
            "invoice_origin": _("%s - Sale", self.name),
            "invoice_line_ids": lines,
            "invoice_payment_term_id": (payment_term or self._get_payment_term()).id,
        })
        for ch in charges:
            self._add_wash_credit(self._wash_credits_for(ch.get("service"), ch.get("quantity") or 1),
                                  "purchase", invoice)
        if self.company_id.parking_auto_post_invoices and invoice.amount_total > 0:
            invoice.action_post()
        self.env["parking.notification.rule"]._notify("invoice_created", invoice, self.partner_id)
        self._message_log(body=_("Sale invoiced separately: %s", invoice._get_html_link()))
        return invoice

    def _get_remaining_term(self):
        """(start, end, months) not billed yet, or (False, False, 0)."""
        self.ensure_one()
        if self.prepaid_until or not self.end_date or self.subscription_type == "daily":
            return False, False, 0
        start = self.recurring_next_date or (self.start_date if not self.invoice_ids else False)
        if not start or start > self.end_date:
            return False, False, 0
        delta = relativedelta(self.end_date + timedelta(days=1), start)
        months = delta.years * 12 + delta.months + (1 if delta.days else 0)
        return start, self.end_date, months

    def _bill_remaining_term(self, discount=0.0, payment_term=None):
        """One invoice for every month left until the end date; periodic billing stops."""
        self.ensure_one()
        self._check_state(("active", "confirmed"), _("bill the remaining term of"))
        start, end, months = self._get_remaining_term()
        if not months:
            raise UserError(_("Nothing is left to bill on contract %s.", self.name))
        label = _("Remaining term %(start)s - %(end)s", start=start, end=end)
        lines = self._get_invoice_lines_vals(label, start, end, months=months)
        main = lines[0][2]
        main.update({
            "quantity": float(months),
            "price_unit": self.price_per_month or self.price_tmpl_id.price_per_month or 0.0,
            "discount": discount or 0.0,
            "name": _("Parking - %(spot)s - %(ref)s - %(months)s month(s) prepaid (%(start)s - %(end)s)",
                      spot=self.spot_id.full_name, ref=self.name, months=months, start=start, end=end),
        })
        if (self.company_id.parking_use_deferred_revenue and months > 1
                and "deferred_start_date" in self.env["account.move.line"]._fields):
            main.update({"deferred_start_date": start, "deferred_end_date": end})
        one_time = self.service_line_ids._is_billable().filtered(lambda l: l.billing_type == "one_time")
        invoice = self.env["account.move"].sudo().with_company(self.company_id).create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": fields.Date.context_today(self),
            "parking_contract_id": self.id,
            "invoice_origin": "%s - %s" % (self.name, label),
            "invoice_line_ids": lines,
            "invoice_payment_term_id": (payment_term or self._get_payment_term()).id,
        })
        one_time.sudo().write({"invoice_id": invoice.id})
        if self.deposit_amount and not self.deposit_invoiced:
            self.deposit_invoiced = True
        self._grant_period_washes(months, invoice, expire=False)
        self.write({"recurring_next_date": False, "prepaid_until": end,
                    "last_invoiced_date": fields.Date.context_today(self)})
        if self.company_id.parking_auto_post_invoices and invoice.amount_total > 0:
            invoice.action_post()
        self.env["parking.notification.rule"]._notify("invoice_created", invoice, self.partner_id)
        return invoice

    def _get_statement_data(self):
        """Invoices, credit notes and payments of these contracts with a running balance."""
        moves = self.sudo().invoice_ids.filtered(
            lambda m: m.state == "posted" and m.move_type in ("out_invoice", "out_refund"))
        rows = []
        for move in moves:
            rows.append({
                "date": move.invoice_date or move.date, "ref": move.name, "contract": move.parking_contract_id.name,
                "label": move.invoice_origin or (_("Credit note") if move.move_type == "out_refund" else _("Invoice")),
                "debit": max(move.amount_total_signed, 0.0), "credit": max(-move.amount_total_signed, 0.0),
                "due_date": move.invoice_date_due, "kind": "invoice" if move.move_type == "out_invoice" else "refund",
            })
            receivable = move.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
            for partial in receivable.matched_credit_ids | receivable.matched_debit_ids:
                other = partial.credit_move_id if partial.debit_move_id in receivable else partial.debit_move_id
                # Invoice/credit-note matches are already rows of their own.
                if other.move_id in moves:
                    continue
                paid_in = partial.debit_move_id in receivable
                rows.append({
                    "date": other.date, "ref": other.move_id.name, "contract": move.parking_contract_id.name,
                    "label": _("Payment for %s", move.name) if paid_in else _("Refund paid for %s", move.name),
                    "debit": 0.0 if paid_in else partial.amount, "credit": partial.amount if paid_in else 0.0,
                    "due_date": False, "kind": "payment",
                })
        rows.sort(key=lambda r: (r["date"] or fields.Date.today(), 0 if r["kind"] != "payment" else 1))
        balance = 0.0
        for row in rows:
            balance += row["debit"] - row["credit"]
            row["balance"] = balance
        today = fields.Date.context_today(self)
        overdue = sum(m.amount_residual_signed for m in moves
                      if m.move_type == "out_invoice" and m.invoice_date_due and m.invoice_date_due < today)
        currency = (self[:1].company_currency_id or self.env.company.currency_id)
        return {
            "rows": rows,
            "invoiced": sum(r["debit"] for r in rows if r["kind"] != "payment") - sum(
                r["credit"] for r in rows if r["kind"] == "refund"),
            "paid": sum(r["credit"] for r in rows if r["kind"] == "payment") - sum(
                r["debit"] for r in rows if r["kind"] == "payment"),
            "balance": balance,
            "overdue": overdue,
            "currency": currency,
            "today": today,
        }

    def _compute_statement_html(self):
        for r in self:
            if not r.id or not self.env.user.has_group("parking_management.group_parking_invoicing"):
                r.statement_html = False
                continue
            data = r._get_statement_data()
            r.statement_html = self.env["ir.qweb"]._render(
                "parking_management.statement_table", dict(data, contracts=r))

    def action_add_charge(self):
        self.ensure_one()
        return {
            "name": _("Sell / Add Charge"),
            "type": "ir.actions.act_window",
            "res_model": "parking.contract.charge.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }

    def action_add_washes(self):
        self.ensure_one()
        wash = self.env["parking.service"].search(
            [("category", "=", "wash"), ("company_id", "in", [False, self.company_id.id])], limit=1)
        return {
            "name": _("Add Washes"),
            "type": "ir.actions.act_window",
            "res_model": "parking.contract.charge.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id, "default_service_id": wash.id,
                        "default_mode": "invoice_now"},
        }

    def action_bill_remaining_term(self):
        self.ensure_one()
        return {
            "name": _("Bill Remaining Term"),
            "type": "ir.actions.act_window",
            "res_model": "parking.contract.prepay.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }

    def action_print_statement(self):
        return self.env.ref("parking_management.action_report_parking_statement").report_action(self)

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
                elif days_left <= 0:
                    with self.env.cr.savepoint():
                        contract._send_expiry_notification()
                        contract.action_expire()
            except Exception:
                _logger.exception("Parking notification cron failed for contract %s", contract.name)

    def _send_expiry_reminder(self, days_left):
        self.ensure_one()
        self.env["parking.notification.rule"]._notify(
            "contract_expiring", self, self.partner_id, extra={"days": days_left})
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
        self.env["parking.notification.rule"]._notify("contract_expired", self, self.partner_id)
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
                template.sudo().send_mail(invoice.id, force_send=False)
        except Exception:
            pass

    @api.depends("wash_ids", "wash_ids.state", "wash_credit_ids", "wash_credit_ids.quantity")
    def _compute_wash_counts(self):
        for r in self:
            used = len(r.wash_ids.filtered(lambda w: w.state == "done"))
            credited = sum(r.wash_credit_ids.mapped("quantity"))
            r.washes_used = used
            r.washes_credited = credited
            r.remaining_washes = max(0, credited - used)

    def _add_wash_credit(self, quantity, kind, invoice=None, note=None):
        self.ensure_one()
        if quantity:
            self.env["parking.wash.credit"].sudo().create({
                "contract_id": self.id, "quantity": quantity, "kind": kind,
                "invoice_id": invoice.id if invoice else False, "note": note or False,
            })

    def _grant_period_washes(self, months, invoice=None, expire=True):
        """Credit the monthly wash allowance for the months an invoice covers.

        Without carry-over, washes left from the monthly allowance expire when the
        next allowance arrives; purchased washes never expire (washes use the allowance first).
        A prepayment (expire=False) adds the whole term's allowance and leaves the current one alone.
        """
        self.ensure_one()
        allowance = self.free_wash_count * int(max(months, 1))
        if not allowance:
            return
        if expire and not self.company_id.parking_wash_carry_over:
            last = self.wash_credit_ids.filtered(lambda c: c.kind == "allowance").sorted("id", reverse=True)[:1]
            unused = 0
            if last:
                # Washes done since that allowance used it first; what is left of it expires.
                used_since = len(self.wash_ids.filtered(
                    lambda w: w.state == "done" and w.create_date and w.create_date >= last.create_date))
                unused = min(max(last.quantity - used_since, 0), self.remaining_washes)
            if unused > 0:
                self._add_wash_credit(-unused, "expiry", note=_("Unused monthly washes expired"))
        self._add_wash_credit(allowance, "allowance", invoice)