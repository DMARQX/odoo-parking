from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import babel_locale_parse, get_lang
from odoo.tools import is_html_empty
from babel.dates import get_month_names
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
    tax_ids = fields.Many2many("account.tax", string="Taxes", domain="[('type_tax_use', '=', 'sale'), ('company_id', 'parent_of', company_id)]", tracking=True,
        default=lambda self: self.env.company.account_sale_tax_id,
        help="Leave empty to use each product's sales tax (the company default VAT when the product has none).")
    price_per_month = fields.Monetary(string="Price/Month", currency_field="company_currency_id", tracking=True)
    service_line_ids = fields.One2many("parking.contract.service.line", "contract_id", string="Additional Services", tracking=True)
    wash_ids = fields.One2many("parking.contract.wash", "contract_id", string="Car Washes")
    # Totals of the contract itself (they do not change when something gets invoiced).
    rent_amount = fields.Monetary(
        string="Rent", compute="_compute_totals", currency_field="company_currency_id", store=True,
        help="Rent of one month; for a daily booking, the rent of the whole booking. Excludes VAT.")
    recurring_services_total = fields.Monetary(
        string="Recurring Services", compute="_compute_totals", currency_field="company_currency_id", store=True,
        help="Services billed with every invoice (\"Every invoice\" lines), per month. Excludes VAT.")
    one_time_services_total = fields.Monetary(
        string="One-time Services", compute="_compute_totals", currency_field="company_currency_id", store=True,
        help="Services billed once (\"Once\" lines), invoiced or not. Not part of the period amount.")
    services_total = fields.Monetary(
        string="Services Total", compute="_compute_totals", currency_field="company_currency_id", store=True,
        help="All services on the contract: recurring plus one-time.")
    amount_total = fields.Monetary(
        string="Period Amount (untaxed)", compute="_compute_totals", currency_field="company_currency_id",
        store=True, tracking=True,
        help="Rent plus recurring services for one month (for a daily booking: the whole booking). "
             "Excludes VAT and one-time services.")
    amount_tax = fields.Monetary(
        string="VAT", compute="_compute_amount_tax", currency_field="company_currency_id",
        help="VAT on the period amount, with the same taxes the invoice uses (customer's fiscal position included).")
    amount_total_incl = fields.Monetary(
        string="Period Amount incl. VAT", compute="_compute_amount_tax", currency_field="company_currency_id")
    deposit_amount = fields.Monetary(string="Deposit Amount", currency_field="company_currency_id", tracking=True)
    deposit_invoiced = fields.Boolean(string="Deposit Invoiced", default=False, copy=False, help="Whether the deposit/insurance line has been added to a customer invoice.")
    deposit_enabled = fields.Boolean(related="company_id.parking_use_deposit")
    deposit_refunded = fields.Boolean(string="Deposit Refunded", readonly=True, copy=False)
    deposit_refund_move_id = fields.Many2one("account.move", string="Deposit Refund", readonly=True, copy=False)

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
    terms_id = fields.Many2one("parking.terms.conditions", string="T&C Template", tracking=True,
        default=lambda self: self.env["parking.terms.conditions"]._get_default(self.env.company))
    terms_conditions = fields.Html(string="Terms & Conditions", translate=True,
        default=lambda self: self.env["parking.terms.conditions"]._get_default(self.env.company).content)
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
    draft_invoice_count = fields.Integer(string="Draft Invoices", compute="_compute_draft_invoice_count")
    wash_interval_days = fields.Integer(
        string="Wash Interval (Days)", default=lambda self: self.env.company.parking_wash_interval_days,
        help="Minimum days between two washes of the same vehicle. 0 = no minimum. "
             "New contracts take the default from Parking settings.")
    invoice_period = fields.Selection([
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
        ("one_time", "One Time"),
    ], string="Invoice Period", default="monthly", tracking=True)
    last_invoiced_date = fields.Date(string="Last Invoiced Date", readonly=True, copy=False)
    recurring_next_date = fields.Date(string="Next Invoice Date", readonly=True, copy=False)
    parking_product_id = fields.Many2one("product.product", string="Parking Product",
        domain="[('type', '=', 'service')]", tracking=True,
        help="Filled from the spot type when the spot is chosen. Leave empty to use the default parking service.")
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

    def _get_month_price(self):
        self.ensure_one()
        return self.price_per_month or (self.price_tmpl_id.price_per_month if self.price_tmpl_id else 0.0)

    @api.depends("service_line_ids", "service_line_ids.price_subtotal", "service_line_ids.billing_type",
                 "price_tmpl_id", "price_per_month", "price_per_day", "subscription_type", "start_date", "end_date")
    def _compute_totals(self):
        for r in self:
            if r.subscription_type == "daily":
                # A daily booking is billed once for all its days.
                rent = r._get_day_price() * r.booking_days
            else:
                rent = r._get_month_price()
            recurring = sum(r.service_line_ids.filtered(lambda l: l.billing_type == "recurring").mapped("price_subtotal"))
            one_time = sum(r.service_line_ids.filtered(lambda l: l.billing_type != "recurring").mapped("price_subtotal"))
            r.rent_amount = rent
            r.recurring_services_total = recurring
            r.one_time_services_total = one_time
            r.services_total = recurring + one_time
            r.amount_total = rent + recurring

    @api.depends("rent_amount", "recurring_services_total", "service_line_ids.price_subtotal",
                 "service_line_ids.billing_type", "tax_ids", "partner_id", "parking_product_id", "spot_id")
    def _compute_amount_tax(self):
        Tax = self.env["account.tax"]
        for r in self:
            amounts = [(r.rent_amount, r._get_parking_product())] + [
                (l.price_subtotal, l.product_id)
                for l in r.service_line_ids.filtered(lambda l: l.billing_type == "recurring")]
            tax = 0.0
            for amount, product in amounts:
                if not amount:
                    continue
                taxes = Tax.browse(r._get_invoice_tax_ids(product)[0][2])
                res = taxes.compute_all(amount, currency=r.company_currency_id, quantity=1.0,
                                        product=product, partner=r.partner_id)
                tax += res["total_included"] - res["total_excluded"]
            r.amount_tax = tax
            r.amount_total_incl = r.amount_total + tax

    @api.model_create_multi
    def create(self, vals_list):
        contract_seq = self.env["ir.sequence"]
        for vals in vals_list:
            # The default name is translated when the form opens ("جديد" in Arabic),
            # so compare against every placeholder, not just the current language.
            if not vals.get("name") or vals.get("name") in ("New", "جديد", "/", _("New")):
                vals["name"] = contract_seq.next_by_code("parking.contract") or _("New")
            self._check_spot_availability(vals)
            if vals.get("spot_id"):
                spot = self.env["parking.spot"].browse(vals["spot_id"])
                if not vals.get("parking_product_id") and spot.spot_type_id.product_id:
                    vals["parking_product_id"] = spot.spot_type_id.product_id.id
                if spot.location_id.company_id:
                    # Invoices go out under the branch's company (its VAT number and journals).
                    vals["company_id"] = spot.location_id.company_id.id
            # Terms: the chosen template, else the default one of the contract's company. Text typed
            # on the contract itself is kept.
            Terms = self.env["parking.terms.conditions"]
            if "terms_id" not in vals:
                company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
                vals["terms_id"] = Terms._get_default(company).id
            if vals.get("terms_id") and is_html_empty(vals.get("terms_conditions")):
                vals["terms_conditions"] = Terms.browse(vals["terms_id"]).content
            elif not vals.get("terms_id"):
                # No template wanted: the default text does not sneak in either.
                vals.setdefault("terms_conditions", False)
        records = super().create(vals_list)
        for record in records:
            if record.auto_invoice:
                record._update_recurring_next_date()
        return records

    def _get_invoice_period_dates(self, from_date=None):
        """(start, end, label) of the invoice period containing from_date.

        The label is in the language of the environment: call it on _invoice_ctx().
        """
        self.ensure_one()
        if not from_date:
            from_date = fields.Date.today()
        if self.invoice_period == "monthly":
            period_start = from_date.replace(day=1)
            period_end = period_start + relativedelta(months=1) - timedelta(days=1)
            label = self._month_label(period_start)
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
            label = _("Contract term")
        return period_start, period_end, label

    def _invoice_ctx(self):
        """The contract in the language of its invoice texts (company setting, else the customer's)."""
        self.ensure_one()
        lang = self.company_id.parking_invoice_lang or self.partner_id.lang or self.env.lang or "en_US"
        return self.with_context(lang=lang)

    def _month_label(self, value):
        """Month name in the environment language, year and digits kept Western ("سبتمبر 2026")."""
        try:
            names = get_month_names("wide", locale=babel_locale_parse(get_lang(self.env).code))
            return "%s %s" % (names[value.month], value.year)
        except Exception:
            return value.strftime("%B %Y")

    def _format_invoice_date(self, value):
        return value.strftime("%d/%m/%Y") if value else ""

    def _period_origins(self, from_date):
        """Every source text an invoice of this period may carry: each installed language,
        plus the wording used before 18.0.4.1.0 ("Month of September 2026")."""
        self.ensure_one()
        origins = set()
        for code, _name in self.env["res.lang"].get_installed():
            contract = self.with_context(lang=code)
            origins.add("%s - %s" % (self.name, contract._get_invoice_period_dates(from_date)[2]))
            origins.add("%s - %s" % (self.name, contract._legacy_period_label(from_date)))
        return origins

    def _legacy_period_label(self, from_date):
        if self.invoice_period == "monthly":
            return _("Month of %s") % from_date.replace(day=1).strftime("%B %Y")
        if self.invoice_period == "one_time":
            return _("Parking Contract - %s") % self.name
        return self._get_invoice_period_dates(from_date)[2]

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
        product = self._get_parking_product()
        product_id = product.id if product else False
        lines = []
        acc_vals = self._get_line_accounting_vals(period_start, period_end, deferrable=True)

        qty = self._get_period_months()
        price = self._get_month_price()
        fmt = self._format_invoice_date
        if self.subscription_type == "daily":
            # One line for the whole booking: days x daily price.
            qty = float(self.booking_days or 1)
            price = self._get_day_price()
            name = _("Parking rent %(spot)s - %(days)s day(s) (%(start)s - %(end)s)",
                     spot=self.spot_id.name, days=self.booking_days,
                     start=fmt(self.start_date), end=fmt(self.end_date))
        else:
            start, end = period_start, period_end
            if months is None and period_start and period_end and self.company_id.parking_prorate:
                # Pay only the contract's days inside the period: days x the period's daily rate.
                start = max(period_start, self.start_date or period_start)
                end = min(period_end, self.end_date or period_end)
                period_days = (period_end - period_start).days + 1
                days = (end - start).days + 1
                if 0 < days < period_days:
                    price = round(price * qty / period_days, 2)
                    qty = float(days)
            name = _("Parking rent %(spot)s - %(period)s (%(start)s - %(end)s)",
                     spot=self.spot_id.name, period=period_label,
                     start=fmt(start), end=fmt(end))

        lines.append((0, 0, dict(acc_vals, **{
            "name": name,
            "quantity": qty,
            "price_unit": price,
            "product_id": product_id,
            "tax_ids": self._get_invoice_tax_ids(product),
            "parking_line_kind": "rent",
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
                "parking_line_kind": "service",
            })))

        if self._deposit_due():
            deposit_account = self.company_id.parking_deposit_account_id
            deposit_line = {
                "name": _("Refundable deposit - %(ref)s", ref=self.name),
                "quantity": 1.0,
                "price_unit": self.deposit_amount,
                "tax_ids": [(5, 0, 0)],
                # A refundable deposit is owed back to the customer: a liability, not revenue.
                "account_id": deposit_account.id,
                "parking_line_kind": "deposit",
            }
            lines.append((0, 0, deposit_line))

        return lines

    def _auto_create_invoice(self, invoice_date=None):
        self.ensure_one()
        if not invoice_date:
            invoice_date = fields.Date.today()
        contract = self._invoice_ctx()
        period_start, period_end, label = contract._get_invoice_period_dates(invoice_date)
        origin = "%s - %s" % (self.name, label)
        if self._period_invoiced(period_start, invoice_date):
            raise UserError(_("An invoice for %s already exists. Cancel it first to issue a new one.", origin))
        invoice_vals = dict(self._invoice_header_vals("period", period_start, period_end), **{
            "move_type": "out_invoice",
            "invoice_date": invoice_date,
            "invoice_origin": origin,
            "invoice_line_ids": contract._get_invoice_lines_vals(label, period_start, period_end),
            "invoice_payment_term_id": self._get_payment_term().id,
        })
        one_time = self.service_line_ids._is_billable().filtered(lambda l: l.billing_type == "one_time")
        # Issued by the system: contract staff activate contracts without
        # holding accounting rights, and the recurring cron has none either.
        invoice = self.env["account.move"].sudo().with_company(self.company_id).create(invoice_vals)
        one_time.sudo().write({"invoice_id": invoice.id})
        self._grant_period_washes(1 if self.subscription_type == "daily" else self._get_period_months(), invoice)
        if self.company_id.parking_auto_post_invoices and invoice.amount_total > 0:
            invoice.action_post()
        self.env["parking.notification.rule"]._notify("invoice_created", invoice, self.partner_id)
        if invoice._parking_has_deposit():
            self.write({"deposit_invoiced": True})
        self.write({
            "last_invoiced_date": invoice_date,
            # From the period, not the invoice date: a late run must not shift the billing day.
            "recurring_next_date": self._compute_next_invoice_date(period_start),
        })
        self._send_invoice_notification(invoice)
        return invoice

    def _period_invoiced(self, period_start, invoice_date):
        """An invoice (not cancelled) already bills this period."""
        self.ensure_one()
        live = self.invoice_ids.filtered(lambda m: m.state != "cancel" and m.move_type == "out_invoice")
        if live.filtered(lambda m: m.parking_invoice_kind == "period" and m.parking_period_start == period_start):
            return True
        # Invoices issued before 18.0.5.0.0 carry the period only in their source text.
        origins = self._period_origins(invoice_date)
        return bool(live.filtered(lambda m: not m.parking_invoice_kind and m.invoice_origin in origins))

    def _deposit_due(self):
        """The deposit goes on the next invoice: feature on, amount set, not billed yet."""
        self.ensure_one()
        if not (self.company_id.parking_use_deposit and self.deposit_amount and not self.deposit_invoiced):
            return False
        if not self.company_id.parking_deposit_account_id:
            raise UserError(_(
                "Set the customer deposits account in Parking settings before invoicing the deposit of %s.",
                self.name))
        return True

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
            # Catch up every period that fell due (e.g. after the server was down), oldest first.
            for _i in range(36):
                due = contract.recurring_next_date
                if not due or due > today or contract.state != "active" or contract.prepaid_until:
                    break
                if contract.end_date and due > contract.end_date:
                    contract.recurring_next_date = False
                    break
                try:
                    with self.env.cr.savepoint():
                        contract._auto_create_invoice(due)
                except Exception as e:
                    contract.env["ir.logging"].sudo().create({
                        "name": "Parking Invoice Cron",
                        "type": "server",
                        "level": "error",
                        "message": "%s: %s" % (contract.name, e),
                        "path": "parking_contract._cron_generate_recurring_invoices",
                        "func": "_cron_generate_recurring_invoices",
                        "line": "0",  # required: without it this log crashed the whole run
                    })
                    contract._billing_alert(_("Automatic invoice failed"), str(e))
                    break
                if contract.recurring_next_date == due:
                    break

    def _billing_alert(self, summary, note):
        """To-do for the contract's responsible: billing needs a human (once per open alert)."""
        for contract in self:
            open_same = contract.activity_ids.filtered(lambda a: a.summary == summary)
            if open_same:
                continue
            contract.sudo().activity_schedule(
                "mail.mail_activity_data_todo", summary=summary, note=note,
                user_id=(contract.user_id or self.env.user).id)

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

    def _get_parking_product(self):
        """Product for the rent line: the contract's, else the spot type's, else the default service."""
        self.ensure_one()
        return (self.parking_product_id or self.spot_id.spot_type_id.product_id
                or self.env.ref("parking_management.product_parking_service", False)
                or self.env["product.product"])

    @api.constrains("company_id", "spot_id")
    def _check_branch_company(self):
        for r in self:
            branch_company = r.location_id.company_id
            if branch_company and r.company_id != branch_company:
                raise ValidationError(_(
                    "Contract %(name)s must belong to %(company)s, the company of branch %(branch)s.",
                    name=r.name, company=branch_company.name, branch=r.location_id.display_name))

    @api.onchange("spot_id")
    def _onchange_spot_id_pricing(self):
        if self.spot_id.location_id.company_id:
            self.company_id = self.spot_id.location_id.company_id
        if self.spot_id.spot_type_id.product_id:
            self.parking_product_id = self.spot_id.spot_type_id.product_id
        if self.spot_id.price_tmpl_id and not self.price_tmpl_id:
            self.price_tmpl_id = self.spot_id.price_tmpl_id
            self._onchange_price_tmpl_id()

    @api.onchange("price_tmpl_id")
    def _onchange_price_tmpl_id(self):
        if self.price_tmpl_id:
            tmpl = self.price_tmpl_id
            self.price_per_month = tmpl.price_per_month or self.price_per_month
            self.price_per_day = tmpl.price_per_day or self.price_per_day
            if self.company_id.parking_use_deposit and tmpl.deposit_amount and not self.deposit_invoiced:
                self.deposit_amount = tmpl.deposit_amount
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
        """A vehicle brings its customer. With a customer already chosen he is kept, and a vehicle
        registered to somebody else is pointed out (it can be right: a new owner, a family car)."""
        if not self.vehicle_ids:
            return
        if not self.partner_id:
            self.partner_id = self.vehicle_ids.mapped("customer_id")[:1]
            return
        partner = self.partner_id.commercial_partner_id
        others = self.vehicle_ids.filtered(
            lambda v: v.customer_id and v.customer_id.commercial_partner_id != partner)
        if others:
            return {"warning": {
                "title": _("Vehicle of another customer"),
                "message": _("%(vehicles)s is registered to %(customers)s, not to %(partner)s. "
                             "Check the customer or the vehicle.",
                             vehicles=", ".join(others.mapped("display_name")),
                             customers=", ".join(others.mapped("customer_id.display_name")),
                             partner=self.partner_id.display_name),
            }}

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
        was_active = self.filtered(lambda c: c.state == "active")
        self.write({"state": "expired"})
        self.spot_id._update_status_from_contracts()
        was_active._close_billing()

    def action_cancel(self):
        self._check_state(("draft", "confirmed", "active"), _("cancel"))
        was_active = self.filtered(lambda c: c.state == "active")
        self.write({"state": "cancelled", "recurring_next_date": False})
        self.spot_id._update_status_from_contracts()
        was_active._close_billing(early=True)

    def _close_billing(self, early=False):
        """Settle a contract that stops: bill what was sold but not invoiced, credit prepaid months
        that will not be used, and leave to-dos for drafts and the deposit."""
        today = fields.Date.context_today(self)
        for contract in self:
            pending = contract.service_line_ids.filtered(lambda l: l.billing_type == "one_time" and not l.invoice_id)
            if pending:
                invoice = contract._create_charge_invoice([{
                    "service": l.service_id, "product": l.product_id, "name": l.name,
                    "quantity": l.quantity, "price_unit": l.price_unit,
                } for l in pending], kind="final", credit_washes=False)
                pending.sudo().write({"invoice_id": invoice.id})
            if early and contract.prepaid_until and contract.prepaid_until > today:
                contract._credit_unused_prepaid(today)
            drafts = contract.invoice_ids.filtered(lambda m: m.state == "draft")
            if drafts:
                contract._billing_alert(
                    _("Review draft invoices of a closed contract"),
                    _("Draft invoices: %s. Post or cancel them.", ", ".join(d.name or _("Draft") for d in drafts)))
            if contract.deposit_enabled and contract.deposit_invoiced and not contract.deposit_refunded:
                contract._billing_alert(_("Refund the deposit"),
                                        _("Contract %s has ended: refund its deposit.", contract.name))

    def _credit_unused_prepaid(self, today):
        """Draft credit note for the whole prepaid months after this one."""
        self.ensure_one()
        prepaid = self.invoice_ids.filtered(lambda m: m.parking_invoice_kind == "prepaid" and m.state == "posted")[-1:]
        rent = prepaid.invoice_line_ids.filtered(lambda l: l.parking_line_kind == "rent")[:1]
        start = today.replace(day=1) + relativedelta(months=1)
        if not rent or start > self.prepaid_until:
            return False
        delta = relativedelta(self.prepaid_until + timedelta(days=1), start)
        months = delta.years * 12 + delta.months
        if months <= 0:
            return False
        end = start + relativedelta(months=months) - timedelta(days=1)
        contract = self._invoice_ctx()
        refund = self.env["account.move"].sudo().with_company(self.company_id).create(
            dict(self._invoice_header_vals("prepaid_refund", start, end), **{
                "move_type": "out_refund",
                "invoice_date": today,
                "invoice_origin": contract._unused_prepaid_text(start, end, months),
                "reversed_entry_id": prepaid.id,
                "invoice_line_ids": [(0, 0, dict(self._get_line_accounting_vals(), **{
                    "name": contract._unused_prepaid_text(start, end, months),
                    "quantity": float(months),
                    "price_unit": rent.price_unit,
                    "discount": rent.discount,
                    "product_id": rent.product_id.id,
                    "tax_ids": [(6, 0, rent.tax_ids.ids)],
                    "parking_line_kind": "rent",
                }))],
            }))
        self.prepaid_until = today
        self._billing_alert(_("Check the prepaid refund"),
                            _("Draft credit note %s for unused prepaid months: review and post it.", refund.name or ""))
        return refund

    def _unused_prepaid_text(self, start, end, months):
        fmt = self._format_invoice_date
        return _("Unused prepaid parking %(spot)s - %(months)s month(s) (%(start)s - %(end)s)",
                 spot=self.spot_id.name, months=months, start=fmt(start), end=fmt(end))

    def action_refund_deposit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Refund Deposit"),
            "res_model": "parking.deposit.refund.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }

    def _refund_deposit(self, deduction=0.0, reason=False, income_account=False):
        """Give the deposit back: a credit note on the deposits account for the refundable part,
        and a journal entry moving any deduction (damages, unpaid fees) from the liability to income."""
        self.ensure_one()
        account = self.company_id.parking_deposit_account_id
        if not account:
            raise UserError(_("Set the customer deposits account in Parking settings first."))
        if not self.deposit_invoiced or self.deposit_refunded:
            raise UserError(_("Contract %s has no invoiced deposit left to refund.", self.name))
        deduction = max(0.0, min(deduction or 0.0, self.deposit_amount))
        refund_amount = self.deposit_amount - deduction
        contract = self._invoice_ctx()
        moves = self.env["account.move"]
        if refund_amount > 0:
            moves |= self.env["account.move"].sudo().with_company(self.company_id).create(
                dict(self._invoice_header_vals("deposit_refund"), **{
                    "move_type": "out_refund",
                    "invoice_date": fields.Date.context_today(self),
                    "invoice_origin": contract._deposit_refund_text(),
                    "invoice_line_ids": [(0, 0, {
                        "name": contract._deposit_refund_text(),
                        "quantity": 1.0,
                        "price_unit": refund_amount,
                        "account_id": account.id,
                        "tax_ids": [(5, 0, 0)],
                        "parking_line_kind": "deposit",
                    })],
                }))
        if deduction > 0:
            if not income_account:
                raise UserError(_("Choose the income account for the deduction."))
            journal = self.env["account.journal"].sudo().search(
                [("type", "=", "general"), ("company_id", "=", self.company_id.id)], limit=1)
            label = contract._deposit_deduction_text(reason)
            moves |= self.env["account.move"].sudo().with_company(self.company_id).create({
                "move_type": "entry",
                "journal_id": journal.id,
                "date": fields.Date.context_today(self),
                "ref": label,
                "parking_contract_id": self.id,
                "parking_invoice_kind": "deposit_refund",
                "line_ids": [
                    (0, 0, {"name": label, "account_id": account.id, "partner_id": self.partner_id.id,
                            "debit": deduction, "credit": 0.0}),
                    (0, 0, dict(self._get_line_accounting_vals(), **{
                        "name": label, "account_id": income_account.id, "partner_id": self.partner_id.id,
                        "debit": 0.0, "credit": deduction})),
                ],
            })
        moves.filtered(lambda m: m.move_type == "entry" or self.company_id.parking_auto_post_invoices).action_post()
        self.write({"deposit_refunded": True, "deposit_refund_move_id": moves[:1].id})
        self.activity_ids.filtered(lambda a: a.summary == _("Refund the deposit")).action_done()
        self._message_log(body=_("Deposit refunded: %s", ", ".join(m._get_html_link() for m in moves)))
        return moves

    def _deposit_refund_text(self):
        return _("Deposit refund - %(ref)s", ref=self.name)

    def _deposit_deduction_text(self, reason):
        return _("Deposit deduction - %(ref)s: %(reason)s", ref=self.name, reason=reason or "-")

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
        fiscal_position = self._get_fiscal_position()
        if fiscal_position:
            # Exempt or export customers get their mapped (e.g. zero-rated) taxes.
            taxes = fiscal_position.map_tax(taxes)
        return [(6, 0, taxes.ids)]

    def _get_fiscal_position(self):
        self.ensure_one()
        return self.env["account.fiscal.position"].sudo().with_company(self.company_id)._get_fiscal_position(
            self.partner_id)

    def _invoice_header_vals(self, kind, period_start=False, period_end=False):
        """Fields every parking invoice carries."""
        self.ensure_one()
        return {
            "partner_id": self.partner_id.id,
            "parking_contract_id": self.id,
            "parking_invoice_kind": kind,
            "parking_period_start": period_start,
            "parking_period_end": period_end,
            "fiscal_position_id": self._get_fiscal_position().id,
        }

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

    def _create_charge_invoice(self, charges, payment_term=None, kind="sale", credit_washes=True, origin=None):
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
                "parking_line_kind": "service",
            })))
        invoice = self.env["account.move"].sudo().with_company(self.company_id).create(
            dict(self._invoice_header_vals(kind), **{
                "move_type": "out_invoice",
                "invoice_date": fields.Date.context_today(self),
                "invoice_origin": origin or self._invoice_ctx()._sale_origin(),
                "invoice_line_ids": lines,
                "invoice_payment_term_id": (payment_term or self._get_payment_term()).id,
            }))
        for ch in charges if credit_washes else []:
            self._add_wash_credit(self._wash_credits_for(ch.get("service"), ch.get("quantity") or 1),
                                  "purchase", invoice)
        if self.company_id.parking_auto_post_invoices and invoice.amount_total > 0:
            invoice.action_post()
        self.env["parking.notification.rule"]._notify("invoice_created", invoice, self.partner_id)
        self._message_log(body=_("Sale invoiced separately: %s", invoice._get_html_link()))
        return invoice

    def _sale_origin(self):
        return _("%s - Sale", self.name)

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

    def _remaining_term_texts(self, start, end, months):
        fmt = self._format_invoice_date
        label = _("Remaining term %(start)s - %(end)s", start=fmt(start), end=fmt(end))
        name = _("Parking rent %(spot)s - %(months)s month(s) paid in advance (%(start)s - %(end)s)",
                 spot=self.spot_id.name, months=months, start=fmt(start), end=fmt(end))
        return label, name

    def _bill_remaining_term(self, discount=0.0, payment_term=None):
        """One invoice for every month left until the end date; periodic billing stops."""
        self.ensure_one()
        self._check_state(("active", "confirmed"), _("bill the remaining term of"))
        start, end, months = self._get_remaining_term()
        if not months:
            raise UserError(_("Nothing is left to bill on contract %s.", self.name))
        contract = self._invoice_ctx()
        label, name = contract._remaining_term_texts(start, end, months)
        lines = contract._get_invoice_lines_vals(label, start, end, months=months)
        main = lines[0][2]
        main.update({
            "quantity": float(months),
            "price_unit": self.price_per_month or self.price_tmpl_id.price_per_month or 0.0,
            "discount": discount or 0.0,
            "name": name,
        })
        if (self.company_id.parking_use_deferred_revenue and months > 1
                and "deferred_start_date" in self.env["account.move.line"]._fields):
            main.update({"deferred_start_date": start, "deferred_end_date": end})
        one_time = self.service_line_ids._is_billable().filtered(lambda l: l.billing_type == "one_time")
        invoice = self.env["account.move"].sudo().with_company(self.company_id).create(
            dict(self._invoice_header_vals("prepaid", start, end), **{
                "move_type": "out_invoice",
                "invoice_date": fields.Date.context_today(self),
                "invoice_origin": "%s - %s" % (self.name, label),
                "invoice_line_ids": lines,
                "invoice_payment_term_id": (payment_term or self._get_payment_term()).id,
            }))
        one_time.sudo().write({"invoice_id": invoice.id})
        if any(l[2].get("parking_line_kind") == "deposit" for l in lines):
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
        drafts = self.sudo().invoice_ids.filtered(
            lambda m: m.state == "draft" and m.move_type in ("out_invoice", "out_refund")).sorted(
            lambda m: (m.invoice_date or m.date or today, m.id))
        draft_rows = [{
            "date": m.invoice_date or m.date, "contract": m.parking_contract_id.name,
            "label": m.invoice_origin or _("Invoice"),
            "amount": m.amount_total_signed, "untaxed": m.amount_untaxed_signed, "tax": m.amount_tax_signed,
            "no_tax": m.move_type == "out_invoice" and not m.amount_tax and m.amount_untaxed > 0,
        } for m in drafts]
        draft_total = sum(r["amount"] for r in draft_rows)
        return {
            "drafts": draft_rows,
            "draft_total": draft_total,
            "rows": rows,
            "invoiced": sum(r["debit"] for r in rows if r["kind"] != "payment") - sum(
                r["credit"] for r in rows if r["kind"] == "refund"),
            "paid": sum(r["credit"] for r in rows if r["kind"] == "payment") - sum(
                r["debit"] for r in rows if r["kind"] == "payment"),
            "balance": balance,
            "balance_with_drafts": balance + draft_total,
            "overdue": overdue,
            "currency": currency,
            "today": today,
        }

    @api.depends("invoice_ids.state")
    def _compute_draft_invoice_count(self):
        for r in self:
            r.draft_invoice_count = len(r.invoice_ids.filtered(lambda m: m.state == "draft"))

    def action_post_draft_invoices(self):
        """Post every draft invoice of the contract; the ones that cannot be posted are reported."""
        self.ensure_one()
        drafts = self.invoice_ids.filtered(lambda m: m.state == "draft")
        failed = []
        for move in drafts:
            try:
                with self.env.cr.savepoint():
                    move.action_post()
            except UserError as e:
                failed.append("%s: %s" % (move.invoice_origin or move.id, e.args[0] if e.args else e))
        posted = len(drafts) - len(failed)
        if failed:
            raise UserError(_("%(posted)s invoice(s) posted. These could not be posted:\n%(failed)s",
                              posted=posted, failed="\n".join(failed)))
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"type": "success", "message": _("%s invoice(s) posted.", posted),
                       "next": {"type": "ir.actions.client", "tag": "soft_reload"}},
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
            [("category", "=", "wash"), "|", ("company_id", "=", False),
             ("company_id", "parent_of", self.company_id.id)], limit=1)
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