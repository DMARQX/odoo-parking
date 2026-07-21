from odoo import models, fields

class ParkingVehicleInspectionLine(models.Model):
    _name = "parking.vehicle.inspection.line"
    _description = "Vehicle Inspection Line"
    _order = "checkpoint_id, id"

    inspection_id = fields.Many2one("parking.vehicle.inspection", string="Inspection", required=True, ondelete="cascade")
    checkpoint_id = fields.Many2one("parking.vehicle.checkpoint", string="Checkpoint", required=True)
    category = fields.Selection(related="checkpoint_id.category", string="Category", store=True)
    result = fields.Selection([
        ("pass", "Pass"),
        ("fail", "Fail"),
        ("na", "N/A"),
    ], string="Result")
    notes = fields.Text(string="Notes")
    image = fields.Image(string="Photo", max_width=1024, max_height=1024)
