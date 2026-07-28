from odoo import models, fields

class ParkingVehicleCheckpoint(models.Model):
    _name = "parking.vehicle.checkpoint"
    _description = "Vehicle Inspection Checkpoint"
    _order = "category, sequence, id"

    name = fields.Char(string="Checkpoint", required=True, translate=True)
    category = fields.Selection([
        ("exterior", "Exterior"),
        ("interior", "Interior"),
        ("mechanical", "Mechanical"),
        ("electrical", "Electrical"),
        ("documents", "Documents"),
        ("other", "Other"),
    ], string="Category", required=True, default="other")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)
