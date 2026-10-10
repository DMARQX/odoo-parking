from odoo import models, fields, api


class ParkingContractServiceLine(models.Model):
    _name = "parking.contract.service.line"
    _description = "Contract Service Line"
    _order = "id"

    contract_id = fields.Many2one("parking.contract", string="Contract", required=True, ondelete="cascade")
    service_id = fields.Many2one("parking.service", string="Service", required=True,
        domain="['|', ('company_id', '=', False), ('company_id', 'parent_of', company_id)]")
    product_id = fields.Many2one("product.product", string="Product", related="service_id.product_id",
        readonly=True)
    name = fields.Char(string="Description", related="service_id.name", readonly=True)
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    price_unit = fields.Monetary(string="Unit Price", currency_field="company_currency_id")
    price_subtotal = fields.Monetary(string="Subtotal", currency_field="company_currency_id",
        compute="_compute_price_subtotal", store=True)
    company_id = fields.Many2one("res.company", related="contract_id.company_id", store=True)
    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")
    billing_type = fields.Selection([
        ("recurring", "Every invoice"),
        ("one_time", "Once"),
    ], string="Billing", default="recurring", required=True,
        help="Every invoice: billed with each periodic invoice. Once: billed on the next invoice only.")
    invoice_id = fields.Many2one("account.move", string="Invoiced On", readonly=True, copy=False,
        help="Invoice that billed this one-time line.")

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange("service_id")
    def _onchange_service_id(self):
        if self.service_id:
            self.price_unit = self.service_id.price
            self.billing_type = self.service_id.billing_type

    def _is_billable(self):
        """Recurring lines are billed every time; one-time lines until they are invoiced."""
        return self.filtered(lambda l: l.billing_type == "recurring" or not l.invoice_id)
