from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ParkingDepositRefundWizard(models.TransientModel):
    _name = "parking.deposit.refund.wizard"
    _description = "Refund Contract Deposit"

    contract_id = fields.Many2one("parking.contract", required=True, readonly=True)
    currency_id = fields.Many2one(related="contract_id.company_currency_id")
    deposit_amount = fields.Monetary(related="contract_id.deposit_amount", string="Deposit")
    deduction = fields.Monetary(string="Deduction",
        help="Kept from the deposit, e.g. damages or unpaid fees. It is booked as income.")
    reason = fields.Char(string="Reason")
    income_account_id = fields.Many2one(
        "account.account", string="Deduction Account",
        domain="[('account_type', 'in', ('income', 'income_other'))]",
        help="Income account credited with the deduction.")
    refund_amount = fields.Monetary(string="Refunded to Customer", compute="_compute_refund_amount")

    @api.depends("deduction", "deposit_amount")
    def _compute_refund_amount(self):
        for w in self:
            w.refund_amount = max(0.0, (w.deposit_amount or 0.0) - (w.deduction or 0.0))

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        contract = self.env["parking.contract"].browse(vals.get("contract_id"))
        product = contract._get_parking_product() if contract else False
        account = product and product.product_tmpl_id.with_company(contract.company_id)._get_product_accounts().get("income")
        if account and "income_account_id" in fields_list:
            vals["income_account_id"] = account.id
        return vals

    def action_confirm(self):
        self.ensure_one()
        if self.deduction < 0 or self.deduction > self.deposit_amount:
            raise UserError(_("The deduction must be between 0 and the deposit amount."))
        if self.deduction and not self.reason:
            raise UserError(_("Give the reason for the deduction."))
        moves = self.contract_id._refund_deposit(self.deduction, self.reason, self.income_account_id)
        refund = moves.filtered(lambda m: m.move_type == "out_refund")[:1]
        if refund:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": refund.id,
                "view_mode": "form",
                "target": "current",
            }
        return {"type": "ir.actions.act_window_close"}
