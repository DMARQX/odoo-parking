from datetime import timedelta

from odoo import models, fields, api, _

class ParkingVehicle(models.Model):
    _name = "parking.vehicle"
    _description = "Vehicle"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "license_plate"

    license_plate = fields.Char(string="License Plate", required=True, tracking=True)
    brand_id = fields.Many2one("parking.vehicle.brand", string="Brand", tracking=True, index=True)
    brand_logo = fields.Image(related="brand_id.logo", string="Brand Logo")
    # Free-text brand kept for reports and imports; it follows brand_id, and typed text finds its brand.
    brand = fields.Char(string="Brand Name")
    model = fields.Char(string="Model")
    color = fields.Char(string="Color")
    year = fields.Integer(string="Year")
    owner_id = fields.Many2one("res.partner", string="Owner", tracking=True)
    active = fields.Boolean(default=True)
    notes = fields.Text(string="Notes")
    display_name = fields.Char(string="Vehicle", compute="_compute_display_name", store=True)

    contract_ids = fields.Many2many("parking.contract", string="Contracts")
    current_contract_id = fields.Many2one(
        "parking.contract", string="Current Contract", compute="_compute_customer",
        help="The vehicle's active contract (or its confirmed one, waiting to start).")
    customer_id = fields.Many2one(
        "res.partner", string="Customer", compute="_compute_customer",
        help="Customer of the current contract; without one, the registered owner. "
             "Forms that take a vehicle fill their customer from here.")

    image_front = fields.Binary(string="Front View", attachment=True)
    image_back = fields.Binary(string="Rear View", attachment=True)
    image_left = fields.Binary(string="Left Side", attachment=True)
    image_right = fields.Binary(string="Right Side", attachment=True)
    image_interior = fields.Binary(string="Interior", attachment=True)
    image_license_doc = fields.Binary(string="License Document", attachment=True)
    image_owner_id_doc = fields.Binary(string="Owner ID", attachment=True)

    inspection_ids = fields.One2many("parking.vehicle.inspection", "vehicle_id", string="Inspections")
    inspection_count = fields.Integer(string="Inspections", compute="_compute_inspection_count")

    movement_ids = fields.One2many("parking.vehicle.movement", "vehicle_id", string="Movements")
    movement_count = fields.Integer(string="Movements", compute="_compute_movement_count")

    # Key management
    key_tag = fields.Char(string="Key Tag No.", tracking=True, help="Number on the tag attached to the key.")
    key_slot = fields.Char(string="Key Box Slot", tracking=True, help="Where the key is kept while the vehicle is parked.")
    key_status = fields.Selection([
        ("none", "Not held"),
        ("in_box", "In key box"),
        ("with_customer", "With customer"),
        ("with_driver", "With driver"),
    ], string="Key Status", default="none", tracking=True)

    transfer_ids = fields.One2many("parking.vehicle.transfer", "vehicle_id", string="Transfers")
    transfer_count = fields.Integer(string="Transfers", compute="_compute_transfer_count")
    wash_ids = fields.One2many("parking.contract.wash", "vehicle_id", string="Car Washes")
    wash_count = fields.Integer(string="Total Washes", compute="_compute_wash_count", store=True)
    last_wash_date = fields.Datetime(string="Last Wash Date", compute="_compute_last_wash", store=True)
    next_allowed_wash = fields.Datetime(string="Next Wash", compute="_compute_next_allowed_wash", store=True)

    @api.depends("contract_ids.state", "contract_ids.partner_id", "owner_id")
    def _compute_customer(self):
        for vehicle in self:
            open_contracts = vehicle.contract_ids.filtered(lambda c: c.state in ("active", "confirmed"))
            contract = open_contracts.filtered(lambda c: c.state == "active")[:1] or open_contracts[:1]
            vehicle.current_contract_id = contract
            vehicle.customer_id = contract.partner_id or vehicle.owner_id

    @api.model
    def _sync_brand_vals(self, vals):
        Brand = self.env["parking.vehicle.brand"]
        if vals.get("brand_id"):
            if "brand" not in vals:
                vals["brand"] = Brand.browse(vals["brand_id"]).name
        elif vals.get("brand") and "brand_id" not in vals:
            match = Brand._match(vals["brand"])
            if match:
                vals["brand_id"] = match.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._sync_brand_vals(dict(v)) for v in vals_list])

    def write(self, vals):
        return super().write(self._sync_brand_vals(dict(vals)))

    @api.depends("license_plate", "brand", "model", "color")
    def _compute_display_name(self):
        for r in self:
            parts = [r.license_plate or ""]
            if r.brand:
                parts.append(r.brand)
            if r.model:
                parts.append(r.model)
            if r.color:
                parts.append(r.color)
            r.display_name = " / ".join(parts)

    @api.depends("inspection_ids")
    def _compute_inspection_count(self):
        for r in self:
            r.inspection_count = len(r.inspection_ids)

    @api.depends("movement_ids")
    def _compute_movement_count(self):
        for r in self:
            r.movement_count = len(r.movement_ids)

    @api.depends("transfer_ids")
    def _compute_transfer_count(self):
        for r in self:
            r.transfer_count = len(r.transfer_ids)

    def action_open_inspections(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Inspections",
            "res_model": "parking.vehicle.inspection",
            "view_mode": "list,form",
            "domain": [("vehicle_id", "=", self.id)],
            "context": {"default_vehicle_id": self.id},
        }

    def _is_arabic_context(self):
        return (self.env.context.get('lang') or self.env.user.lang or '').startswith('ar')

    def action_open_movements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Vehicle Movements",
            "res_model": "parking.vehicle.movement",
            "view_mode": "list,form",
            "domain": [("vehicle_id", "=", self.id)],
            "context": {"default_vehicle_id": self.id},
        }

    def action_open_transfers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Vehicle Transfers",
            "res_model": "parking.vehicle.transfer",
            "view_mode": "list,form",
            "domain": [("vehicle_id", "=", self.id)],
            "context": {"default_vehicle_id": self.id},
        }

    @api.depends("wash_ids", "wash_ids.state")
    def _compute_wash_count(self):
        for r in self:
            r.wash_count = len(r.wash_ids.filtered(lambda w: w.state == "done"))

    @api.depends("wash_ids", "wash_ids.wash_date", "wash_ids.state")
    def _compute_last_wash(self):
        for r in self:
            done_washes = r.wash_ids.filtered(lambda w: w.state == "done")
            last = done_washes.sorted("wash_date", reverse=True)[:1]
            r.last_wash_date = last.wash_date if last else False

    @api.depends("last_wash_date", "contract_ids", "contract_ids.wash_interval_days")
    def _compute_next_allowed_wash(self):
        for r in self:
            if not r.last_wash_date:
                r.next_allowed_wash = fields.Datetime.now()
            else:
                active_contracts = r.contract_ids.filtered(lambda c: c.state == "active")
                interval = max(active_contracts.mapped("wash_interval_days") or [0])
                r.next_allowed_wash = r.last_wash_date + timedelta(days=max(interval, 0))

    def action_register_wash(self):
        self.ensure_one()
        active_contract = self.contract_ids.filtered(lambda c: c.state == "active")[:1]
        if not active_contract:
            raise UserError(_("No active contract found for vehicle %s.") % self.display_name)
        if active_contract.remaining_washes <= 0:
            raise UserError(_("No free washes remaining on contract %s.") % active_contract.name)
        if self.last_wash_date and self.next_allowed_wash and fields.Datetime.now() < self.next_allowed_wash:
            raise UserError(_(
                "Vehicle %(veh)s was washed on %(date)s. Next wash allowed after %(next)s."
            ) % {
                "veh": self.display_name,
                "date": self.last_wash_date.strftime("%Y-%m-%d %H:%M"),
                "next": self.next_allowed_wash.strftime("%Y-%m-%d %H:%M"),
            })

        # Create wash record
        wash = self.env["parking.contract.wash"].create({
            "contract_id": active_contract.id,
            "vehicle_id": self.id,
            "state": "done",
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Car Wash Record"),
            "res_model": "parking.contract.wash",
            "res_id": wash.id,
            "view_mode": "form",
            "target": "current",
        }