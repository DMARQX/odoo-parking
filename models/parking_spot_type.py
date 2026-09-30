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
    product_id = fields.Many2one(
        "product.product", string="Parking Product", domain="[('type', '=', 'service')]",
        help="Service product used on the invoices of contracts for spots of this type "
             "(revenue account and taxes). Leave empty to use the default parking service.")

    _sql_constraints = [
        ("code_unique", "unique(code)", "Spot Type Code must be unique!"),
    ]