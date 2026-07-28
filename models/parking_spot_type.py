from odoo import models, fields, api, _

class ParkingSpotType(models.Model):
    _name = "parking.spot.type"
    _description = "Parking Spot Type"
    _order = "sequence, name"

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True, copy=False)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string="Description")

    _sql_constraints = [
        ("code_unique", "unique(code)", "Spot Type Code must be unique!"),
    ]