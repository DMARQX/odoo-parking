from odoo import models, fields

class AccountMove(models.Model):
    _inherit = "account.move"

    parking_contract_id = fields.Many2one("parking.contract", string="Parking Contract")
