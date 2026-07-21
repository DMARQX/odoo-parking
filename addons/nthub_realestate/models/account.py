# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    reservation_id = fields.Many2one('unit.reservation', 'Reservation')
    real_estate_ref = fields.Char('Real Estate Ref.')
    ownership_line_id = fields.Many2one('ownership.contract.line', 'Ownership Installment')
    ownership_delay_line_id = fields.Many2one('ownership.contract.line', 'Ownership Delay')
    rental_line_id = fields.Many2one('rental.contract.line', 'Rental Contract Installment')
    ownership_maintenance_line_id = fields.Many2one('ownership.contract.maintenance.line', 'Ownership Installment Maintenance')


class AccountMove(models.Model):
    _inherit = "account.move"

    real_estate_ref = fields.Char('Real Estate Ref.')
    ownership_line_id = fields.Many2one('ownership.contract.line', 'Ownership Installment')
    ownership_delay_line_id = fields.Many2one('ownership.contract.line', 'Ownership Delay')
    rental_line_id = fields.Many2one('rental.contract.line', 'Rental Contract Installment')
    ownership_maintenance_line_id = fields.Many2one('ownership.contract.maintenance.line', 'Ownership Installment Maintenance')
    property_owner_id = fields.Many2one('res.partner', 'Owner')
