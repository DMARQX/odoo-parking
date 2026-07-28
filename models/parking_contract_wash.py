from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta

class ParkingContractWash(models.Model):
    _name = "parking.contract.wash"
    _description = "Car Wash Record"
    _order = "wash_date desc, id desc"
    _rec_name = "display_name"

    contract_id = fields.Many2one("parking.contract", string="Contract", required=True, ondelete="cascade")
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", required=True)
    partner_id = fields.Many2one("res.partner", string="Customer", related="contract_id.partner_id", store=True)
    location_id = fields.Many2one("parking.location", string="Branch", related="contract_id.location_id", store=True)
    wash_date = fields.Datetime(string="Wash Date", required=True, default=fields.Datetime.now)
    washed_by = fields.Many2one("res.users", string="Washed By", default=lambda self: self.env.user)
    wash_number = fields.Integer(string="Wash #", readonly=True, copy=False)
    state = fields.Selection([
        ("draft", "Draft"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ], string="Status", default="draft")
    line_ids = fields.One2many("parking.contract.wash.line", "wash_id", string="Consumed Supplies")
    notes = fields.Text(string="Notes")
    display_name = fields.Char(string="Wash", compute="_compute_display_name", store=True)
    company_id = fields.Many2one("res.company", related="contract_id.company_id", store=True)

    @api.depends("vehicle_id", "wash_date", "wash_number")
    def _compute_display_name(self):
        for r in self:
            veh = r.vehicle_id.display_name or r.vehicle_id.license_plate or ""
            date_str = r.wash_date.strftime("%Y-%m-%d %H:%M") if r.wash_date else ""
            r.display_name = f"{veh} - Wash #{r.wash_number} - {date_str}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            contract = self.env["parking.contract"].browse(vals.get("contract_id"))
            vehicle = self.env["parking.vehicle"].browse(vals.get("vehicle_id"))

            # Check remaining washes
            if contract.remaining_washes <= 0:
                raise UserError(_("No free washes remaining for this contract."))

            # Check wash interval
            last_wash = self.search([
                ("vehicle_id", "=", vehicle.id),
                ("state", "=", "done"),
            ], order="wash_date desc", limit=1)
            if last_wash:
                interval_days = contract.wash_interval_days or 4
                next_allowed = last_wash.wash_date + timedelta(days=interval_days)
                if fields.Datetime.now() < next_allowed:
                    remaining_hours = (next_allowed - fields.Datetime.now()).total_seconds() / 3600
                    raise UserError(_(
                        "Vehicle %(veh)s was washed on %(date)s. "
                        "Next wash allowed after %(interval)d days (%(next)s). "
                        "Please wait %(hours).0f more hour(s)."
                    ) % {
                        "veh": vehicle.display_name,
                        "date": last_wash.wash_date.strftime("%Y-%m-%d %H:%M"),
                        "interval": interval_days,
                        "next": next_allowed.strftime("%Y-%m-%d %H:%M"),
                        "hours": remaining_hours,
                    })

            # Auto-number wash
            last = self.search([("vehicle_id", "=", vehicle.id)], order="wash_number desc", limit=1)
            vals["wash_number"] = (last.wash_number or 0) + 1
        return super().create(vals_list)

    def action_done(self):
        for r in self:
            r.state = "done"

    def action_cancel(self):
        for r in self:
            r.state = "cancelled"

class ParkingContractWashLine(models.Model):
    _name = "parking.contract.wash.line"
    _description = "Wash Consumed Supply Line"
    _order = "id"

    wash_id = fields.Many2one("parking.contract.wash", string="Wash", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Supply Item", required=True)
    name = fields.Char(string="Description", related="product_id.name", readonly=True)
    quantity = fields.Float(string="Quantity Consumed", required=True, default=1.0)
    uom_id = fields.Many2one("uom.uom", string="Unit", related="product_id.uom_id", readonly=True)
    price_unit = fields.Monetary(string="Unit Cost", currency_field="company_currency_id")
    company_id = fields.Many2one("res.company", related="wash_id.company_id", store=True)
    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")