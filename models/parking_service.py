from odoo import models, fields, api, _

class ParkingService(models.Model):
    _name = "parking.service"
    _description = "Additional Service"
    _order = "name"

    name = fields.Char(string="Service Name", required=True)
    description = fields.Text(string="Description")
    price = fields.Monetary(string="Price", currency_field="company_currency_id")
    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    included_washes = fields.Integer(string="Included Washes",
        help="Number of car washes granted to the contract when this wash package is selected.")
    category = fields.Selection([
        ("wash", "Car Wash"),
        ("cover", "Car Cover"),
        ("polish", "Polishing"),
        ("safety", "Safety Equipment"),
        ("other", "Other"),
    ], string="Category", default="other")
    active = fields.Boolean(default=True)
    product_id = fields.Many2one("product.product", string="Linked Product",
        help="Select the product that represents this service in invoices.")
    billing_type = fields.Selection([
        ("recurring", "Every invoice"),
        ("one_time", "Once"),
    ], string="Billing", default="one_time", required=True,
        help="Every invoice: a subscription add-on billed with each periodic invoice (e.g. a monthly wash "
             "package). Once: a sale billed a single time (e.g. a product).")
