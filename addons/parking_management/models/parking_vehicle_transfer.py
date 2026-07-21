from odoo import models, fields, api, _


class ParkingVehicleTransfer(models.Model):
    _name = "parking.vehicle.transfer"
    _description = "Vehicle Transfer"
    _rec_name = "display_name"
    _order = "transfer_date desc, id desc"

    name = fields.Char(string="Reference", readonly=True, copy=False)
    partner_id = fields.Many2one("res.partner", string="Customer", required=True)
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", required=True)
    transfer_type_id = fields.Many2one("parking.transfer.type", string="Transfer Type", required=True)
    transfer_type_code = fields.Char(string="Transfer Type Code", related="transfer_type_id.code", store=True, readonly=True)
    transfer_date = fields.Datetime(string="Transfer Date", default=fields.Datetime.now, required=True)
    operator_id = fields.Many2one("res.users", string="Operator", default=lambda self: self.env.user)
    state = fields.Selection([
        ("draft", "Draft"),
        ("in_transit", "In Transit"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ], string="Status", default="draft", required=True)

    source_location_id = fields.Many2one("parking.location", string="Source Branch")
    source_spot_id = fields.Many2one("parking.spot", string="Source Spot",
        domain="[('location_id', '=', source_location_id)]")

    destination_location_id = fields.Many2one("parking.location", string="Destination Branch")
    destination_spot_id = fields.Many2one("parking.spot", string="Destination Spot",
        domain="[('location_id', '=', destination_location_id)]")

    service_center_name = fields.Char(string="Service Center Name")
    service_center_phone = fields.Char(string="Service Center Phone")
    service_center_address = fields.Text(string="Service Center Address")

    destination_partner_id = fields.Many2one("res.partner", string="Delivery Customer")

    driver_id = fields.Many2one("parking.driver", string="Driver", required=True)
    transporter_vehicle_id = fields.Many2one("parking.transporter.vehicle", string="Transporter Vehicle", required=True)
    transporter_notes = fields.Text(string="Transporter Notes")

    notes = fields.Text(string="Notes")
    display_name = fields.Char(string="Transfer", compute="_compute_display_name", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                seq = self.env["ir.sequence"].next_by_code("parking.vehicle.transfer") or "TR-001"
                vals["name"] = seq
        return super().create(vals_list)

    @api.depends("name", "vehicle_id", "transfer_type_id")
    def _compute_display_name(self):
        for r in self:
            parts = [r.name or ""]
            if r.vehicle_id:
                parts.append(r.vehicle_id.display_name or r.vehicle_id.license_plate or "")
            if r.transfer_type_id:
                parts.append(r.transfer_type_id.name or "")
            r.display_name = " - ".join(parts)

    def action_draft(self):
        self.state = "draft"

    def action_in_transit(self):
        self.state = "in_transit"

    def action_complete(self):
        self.state = "completed"

    def action_cancel(self):
        self.state = "cancelled"
