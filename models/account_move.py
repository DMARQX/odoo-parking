from odoo import models, fields

class AccountMove(models.Model):
    _inherit = "account.move"

    parking_contract_id = fields.Many2one("parking.contract", string="Parking Contract")
    parking_location_id = fields.Many2one("parking.location", string="Parking Branch",
        related="parking_contract_id.location_id", store=True, readonly=True)
