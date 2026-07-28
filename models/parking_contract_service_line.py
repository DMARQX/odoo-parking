from odoo import models, fields, api

class ParkingContractServiceLine(models.Model):
    _name = "parking.contract.service.line"
    _description = "Contract Service Line"
    _order = "id"

    contract_id = fields.Many2one("parking.contract", string="Contract", required=True, ondelete="cascade")
    service_id = fields.Many2one("parking.service", string="Service", required=True,
        domain="[('company_id', '=', company_id)]")
    product_id = fields.Many2one("product.product", string="Product", related="service_id.product_id",
        readonly=True)
    name = fields.Char(string="Description", related="service_id.name", readonly=True)
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    price_unit = fields.Monetary(string="Unit Price", currency_field="company_currency_id")
    price_subtotal = fields.Monetary(string="Subtotal", currency_field="company_currency_id",
        compute="_compute_price_subtotal", store=True)
    company_id = fields.Many2one("res.company", related="contract_id.company_id", store=True)
    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange("service_id")
    def _onchange_service_id(self):
        if self.service_id:
            self.price_unit = self.service_id.price
