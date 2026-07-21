from odoo import models, fields, api, _

class ParkingPriceTemplate(models.Model):
    _name = "parking.price.template"
    _description = "Price Template"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Template Name", required=True, tracking=True)
    location_id = fields.Many2one("parking.location", string="Branch", tracking=True)
    spot_type = fields.Selection([
        ("standard", "Standard"),
        ("large", "Large / SUV"),
        ("motorcycle", "Motorcycle"),
        ("vip", "VIP"),
    ], string="Spot Type", tracking=True)
    price_per_hour = fields.Monetary(string="Price per Hour", currency_field="company_currency_id", tracking=True)
    price_per_day = fields.Monetary(string="Price per Day", currency_field="company_currency_id", tracking=True)
    price_per_month = fields.Monetary(string="Price per Month", currency_field="company_currency_id", tracking=True)
    price_per_year = fields.Monetary(string="Price per Year", currency_field="company_currency_id", tracking=True)
    deposit_amount = fields.Monetary(string="Deposit Amount", currency_field="company_currency_id", tracking=True)
    tax_id = fields.Many2one("account.tax", string="Default Tax", domain="[('type_tax_use', '=', 'sale')]")
    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Text(string="Notes")
