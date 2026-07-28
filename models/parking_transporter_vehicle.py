from odoo import models, fields, api, _


class ParkingTransporterVehicle(models.Model):
    _name = "parking.transporter.vehicle"
    _description = "Transporter Vehicle"
    _rec_name = "display_name"
    _order = "license_plate"

    license_plate = fields.Char(string="License Plate", required=True)
    vehicle_type = fields.Char(string="Vehicle Type")
    brand = fields.Char(string="Brand")
    model = fields.Char(string="Model")
    color = fields.Char(string="Color")
    driver_id = fields.Many2one("parking.driver", string="Primary Driver")
    company_name = fields.Char(string="Transport Company")
    company_phone = fields.Char(string="Company Phone")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    transfer_count = fields.Integer(string="Transfers", compute="_compute_transfer_count")

    display_name = fields.Char(string="Transporter", compute="_compute_display_name", store=True)

    @api.depends("license_plate", "vehicle_type", "company_name")
    def _compute_display_name(self):
        for r in self:
            parts = [r.license_plate or ""]
            if r.vehicle_type:
                parts.append(r.vehicle_type)
            if r.company_name:
                parts.append(f"[{r.company_name}]")
            r.display_name = " / ".join(parts)

    @api.depends("transfer_ids")
    def _compute_transfer_count(self):
        for r in self:
            r.transfer_count = len(r.transfer_ids)

    transfer_ids = fields.One2many("parking.vehicle.transfer", "transporter_vehicle_id", string="Transfers")
