from odoo import models, fields, api, _


class ParkingWashCredit(models.Model):
    """Wash balance ledger of a contract: every credit or expiry of washes is a line.

    Remaining washes = sum of these lines - completed washes.
    """
    _name = "parking.wash.credit"
    _description = "Contract Wash Credit"
    _order = "date desc, id desc"

    contract_id = fields.Many2one("parking.contract", required=True, ondelete="cascade", index=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    quantity = fields.Integer(string="Washes", required=True,
                              help="Positive: washes added. Negative: washes expired or removed.")
    kind = fields.Selection([
        ("opening", "Opening balance"),
        ("allowance", "Monthly allowance"),
        ("purchase", "Purchased"),
        ("manual", "Manual adjustment"),
        ("expiry", "Expired (no carry-over)"),
    ], string="Type", required=True, default="manual")
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True)
    note = fields.Char(string="Note")
    company_id = fields.Many2one(related="contract_id.company_id", store=True)
