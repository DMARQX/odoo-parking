from odoo import models, fields, api, _

class ParkingVehicle(models.Model):
    _name = "parking.vehicle"
    _description = "Vehicle"
    _rec_name = "display_name"
    _order = "license_plate"

    license_plate = fields.Char(string="License Plate", required=True)
    brand = fields.Char(string="Brand")
    model = fields.Char(string="Model")
    color = fields.Char(string="Color")
    year = fields.Integer(string="Year")
    owner_id = fields.Many2one("res.partner", string="Owner")
    active = fields.Boolean(default=True)
    notes = fields.Text(string="Notes")
    display_name = fields.Char(string="Vehicle", compute="_compute_display_name", store=True)

    contract_ids = fields.Many2many("parking.contract", string="Contracts")

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

    transfer_ids = fields.One2many("parking.vehicle.transfer", "vehicle_id", string="Transfers")
    transfer_count = fields.Integer(string="Transfers", compute="_compute_transfer_count")

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
