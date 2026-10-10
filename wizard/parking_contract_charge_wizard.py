from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ParkingContractChargeWizard(models.TransientModel):
    """Sell a product or service to a contract's customer at any time."""
    _name = "parking.contract.charge.wizard"
    _description = "Sell / Add Charge to a Contract"

    contract_id = fields.Many2one("parking.contract", required=True, readonly=True)
    partner_id = fields.Many2one(related="contract_id.partner_id")
    company_id = fields.Many2one(related="contract_id.company_id")
    company_currency_id = fields.Many2one(related="contract_id.company_currency_id")
    service_id = fields.Many2one("parking.service", string="Service / Product",
                                 domain="['|', ('company_id', '=', False), ('company_id', 'parent_of', company_id)]")
    product_id = fields.Many2one("product.product", string="Other Product",
                                 help="Any product not set up as a parking service.")
    name = fields.Char(string="Description")
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    price_unit = fields.Monetary(string="Unit Price", currency_field="company_currency_id")
    amount = fields.Monetary(string="Total (untaxed)", compute="_compute_amount", currency_field="company_currency_id")
    wash_credits = fields.Integer(string="Washes Added", compute="_compute_amount")
    mode = fields.Selection([
        ("invoice_now", "Invoice now (separate invoice)"),
        ("next_invoice", "Add to the next invoice (once)"),
        ("recurring", "Add to every invoice (subscription add-on)"),
    ], string="Billing", default="invoice_now", required=True)

    @api.onchange("service_id")
    def _onchange_service_id(self):
        if self.service_id:
            self.price_unit = self.service_id.price
            self.name = self.service_id.name
            self.product_id = False
            if self.service_id.billing_type == "recurring" and self.mode == "invoice_now":
                self.mode = "recurring"

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.service_id = False
            self.price_unit = self.product_id.lst_price
            self.name = self.product_id.display_name

    @api.depends("quantity", "price_unit", "service_id")
    def _compute_amount(self):
        for w in self:
            w.amount = w.quantity * (w.price_unit or 0.0)
            w.wash_credits = w.contract_id._wash_credits_for(w.service_id, w.quantity) if w.contract_id else 0

    def action_confirm(self):
        self.ensure_one()
        contract = self.contract_id
        if not self.service_id and not self.product_id:
            raise UserError(_("Choose a service or a product."))
        if self.quantity <= 0:
            raise UserError(_("The quantity must be positive."))
        if contract.state not in ("confirmed", "active"):
            raise UserError(_("Charges can only be added to confirmed or active contracts."))
        if self.mode == "invoice_now":
            invoice = contract._create_charge_invoice([{
                "service": self.service_id, "product": self.product_id or self.service_id.product_id,
                "name": self.name, "quantity": self.quantity, "price_unit": self.price_unit,
            }])
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": invoice.id,
                "view_mode": "form",
                "target": "current",
            } if self.env.user.has_group("parking_management.group_parking_invoicing") else {
                "type": "ir.actions.act_window_close"}
        if not self.service_id:
            raise UserError(_("Only parking services can be added to the contract; "
                              "invoice other products now instead."))
        contract.sudo().write({"service_line_ids": [(0, 0, {
            "service_id": self.service_id.id,
            "quantity": self.quantity,
            "price_unit": self.price_unit,
            "billing_type": "one_time" if self.mode == "next_invoice" else "recurring",
        })]})
        if self.mode == "next_invoice":
            # Washes are usable right away; the charge follows on the next invoice.
            contract._add_wash_credit(self.wash_credits, "purchase", note=_("Billed on the next invoice"))
        else:
            contract._onchange_service_line_ids_wash()
        return {"type": "ir.actions.act_window_close"}
