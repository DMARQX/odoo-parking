from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ParkingBranchStock(models.Model):
    _name = "parking.branch.stock"
    _description = "Branch Stock / Inventory"
    _order = "location_id, product_id"
    _sql_constraints = [
        ("stock_location_product_unique", "unique(location_id, product_id)", "Product already exists in this branch stock!"),
    ]

    location_id = fields.Many2one("parking.location", string="Branch", required=True)
    product_id = fields.Many2one("product.product", string="Product", required=True)
    name = fields.Char(string="Name", related="product_id.name", readonly=True)
    quantity = fields.Float(string="Current Quantity", required=True, default=0.0)
    min_quantity = fields.Float(string="Minimum Quantity", default=0.0)
    uom_id = fields.Many2one("uom.uom", string="Unit", related="product_id.uom_id", readonly=True)
    is_low = fields.Boolean(string="Low Stock", compute="_compute_is_low", store=True)
    # company_id = fields.Many2one("res.company", related="location_id.company_id", store=True)  # removed: parking.location has no company_id

    @api.depends("quantity", "min_quantity")
    def _compute_is_low(self):
        for r in self:
            r.is_low = r.quantity <= r.min_quantity if r.min_quantity > 0 else False

    def deduct_stock(self, product_id, qty, location_id):
        """Deduct qty from branch stock. Called when a wash is done."""
        stock = self.search([("location_id", "=", location_id), ("product_id", "=", product_id)], limit=1)
        if not stock:
            raise UserError(_(
                "Product '%s' is not tracked in branch stock. "
                "Please add it to branch inventory first."
            ) % product_id.display_name)
        if stock.quantity < qty:
            raise UserError(_(
                "Not enough stock of '%(prod)s' in branch '%(branch)s'. "
                "Available: %(qty).1f %(uom)s, Required: %(req).1f %(uom)s"
            ) % {
                "prod": product_id.display_name,
                "branch": location_id.display_name,
                "qty": stock.quantity,
                "uom": stock.uom_id.name or "units",
                "req": qty,
            })
        stock.quantity -= qty
        return True

class ParkingBranchStockMove(models.Model):
    _name = "parking.branch.stock.move"
    _description = "Branch Stock Movement Log"
    _order = "date desc, id desc"

    location_id = fields.Many2one("parking.location", string="Branch", required=True)
    product_id = fields.Many2one("product.product", string="Product", required=True)
    name = fields.Char(string="Description", related="product_id.name", readonly=True)
    quantity = fields.Float(string="Quantity")
    move_type = fields.Selection([
        ("in", "In"),
        ("out", "Out"),
        ("adjust", "Adjustment"),
    ], string="Type", required=True)
    wash_id = fields.Many2one("parking.contract.wash", string="Related Wash", readonly=True)
    date = fields.Datetime(string="Date", default=fields.Datetime.now, required=True)
    notes = fields.Text(string="Notes")