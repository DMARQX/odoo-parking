from odoo import models, fields, api, _


class ParkingDriver(models.Model):
    _name = "parking.driver"
    _description = "Driver"
    _rec_name = "display_name"
    _order = "name"

    name = fields.Char(string="Driver Name", required=True)
    phone = fields.Char(string="Phone", required=True)
    id_number = fields.Char(string="National ID / Iqama")
    license_number = fields.Char(string="License Number")
    license_expiry = fields.Date(string="License Expiry")
    address = fields.Text(string="Address")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    transfer_ids = fields.One2many("parking.vehicle.transfer", "driver_id", string="Transfers")
    transfer_count = fields.Integer(string="Transfers", compute="_compute_transfer_count")

    display_name = fields.Char(string="Driver", compute="_compute_display_name", store=True)

    @api.depends("transfer_ids")
    def _compute_transfer_count(self):
        for r in self:
            r.transfer_count = len(r.transfer_ids)

    @api.depends("name", "phone", "id_number")
    def _compute_display_name(self):
        for r in self:
            parts = [r.name or ""]
            if r.phone:
                parts.append(r.phone)
            if r.id_number:
                parts.append(f"ID: {r.id_number}")
            r.display_name = " - ".join(parts)

    @api.onchange("id_number")
    def _onchange_id_number(self):
        if self.id_number:
            self.id_number = self.id_number.strip()
