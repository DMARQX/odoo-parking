from odoo import models, fields, api, _

class ParkingSpotStatusLog(models.Model):
    _name = "parking.spot.status.log"
    _description = "Spot Status Change Log"
    _order = "change_date desc"

    spot_id = fields.Many2one("parking.spot", string="Spot", required=True)
    old_status = fields.Selection([
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("occupied", "Occupied"),
        ("client_out", "Client Out"),
        ("maintenance", "Maintenance"),
    ], string="Previous Status")
    new_status = fields.Selection([
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("occupied", "Occupied"),
        ("client_out", "Client Out"),
        ("maintenance", "Maintenance"),
    ], string="New Status", required=True)
    reason = fields.Text(string="Reason / Notes")
    change_date = fields.Datetime(string="Change Date", default=fields.Datetime.now)
    operator_id = fields.Many2one("res.users", string="Operator", default=lambda self: self.env.user)
    contract_id = fields.Many2one("parking.contract", string="Related Contract")
