from odoo import api, fields, models


class ParkingContractPrepayWizard(models.TransientModel):
    """Bill every remaining month of a contract in one invoice (optionally discounted, in instalments)."""
    _name = "parking.contract.prepay.wizard"
    _description = "Bill Remaining Contract Term"

    contract_id = fields.Many2one("parking.contract", required=True, readonly=True)
    company_currency_id = fields.Many2one(related="contract_id.company_currency_id")
    start_date = fields.Date(string="From", compute="_compute_term")
    end_date = fields.Date(string="To", compute="_compute_term")
    months = fields.Integer(string="Months", compute="_compute_term")
    monthly_price = fields.Monetary(string="Price/Month", compute="_compute_term", currency_field="company_currency_id")
    discount = fields.Float(string="Discount (%)", help="Discount for paying the remaining term at once.")
    amount = fields.Monetary(string="Subscription Amount (untaxed)", compute="_compute_term",
                             currency_field="company_currency_id")
    payment_term_id = fields.Many2one("account.payment.term", string="Payment Terms",
                                      help="Choose instalments here to split the invoice into several due dates.")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        contract = self.env["parking.contract"].browse(res.get("contract_id") or self.env.context.get("default_contract_id"))
        if contract and "payment_term_id" in fields_list:
            res["payment_term_id"] = contract._get_payment_term().id
        return res

    @api.depends("contract_id", "discount")
    def _compute_term(self):
        for w in self:
            start, end, months = w.contract_id._get_remaining_term() if w.contract_id else (False, False, 0)
            price = w.contract_id.price_per_month or w.contract_id.price_tmpl_id.price_per_month or 0.0
            w.start_date, w.end_date, w.months, w.monthly_price = start, end, months, price
            w.amount = months * price * (1 - (w.discount or 0.0) / 100.0)

    def action_confirm(self):
        self.ensure_one()
        invoice = self.contract_id._bill_remaining_term(self.discount, self.payment_term_id)
        if self.env.user.has_group("parking_management.group_parking_invoicing"):
            return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": invoice.id,
                    "view_mode": "form", "target": "current"}
        return {"type": "ir.actions.act_window_close"}
