from odoo import models, fields, api, _

class ParkingWashKitItem(models.Model):
    _name = "parking.wash.kit.item"
    _description = "Wash Kit Item (Supplies per Car Wash)"
    _order = "sequence, id"

    name = fields.Char(string="Item Name", required=True)
    product_id = fields.Many2one("product.product", string="Product")
    default_quantity = fields.Float(string="Default Qty per Wash", required=True, default=1.0)
    uom_id = fields.Many2one("uom.uom", string="Unit", related="product_id.uom_id", readonly=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)