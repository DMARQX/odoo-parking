from odoo import models, fields, api, _


class ParkingTransferType(models.Model):
    _name = "parking.transfer.type"
    _description = "Transfer Type"
    _rec_name = "name"
    _order = "sequence, name"

    name = fields.Char(string="Type Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True)
    destination_kind = fields.Selection([
        ("branch", "Another branch"),
        ("service_center", "Service center / workshop"),
        ("customer", "Customer address"),
        ("other", "Other"),
    ], string="Destination", required=True, default="branch",
        help="Decides which destination fields a transfer of this type asks for.")
    price = fields.Monetary(string="Price", currency_field="currency_id",
        help="Charged to the customer for each transfer of this type (excludes VAT). 0 = not invoiced.")
    product_id = fields.Many2one(
        "product.product", string="Invoice Product", domain="[('type', '=', 'service')]",
        help="Service product on the transfer's invoice line: its income account and taxes are used.")
    currency_id = fields.Many2one(related="company_id.currency_id")
    description = fields.Text(string="Description")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    _sql_constraints = [
        ("unique_code", "unique(code)", "Transfer type code must be unique!"),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = (vals.get("name", "") or "").upper().replace(" ", "_")
        return super().create(vals_list)
