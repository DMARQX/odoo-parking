# -*- coding: utf-8 -*-
from odoo import api, fields, models


class Configration(models.TransientModel):
    _inherit = 'res.config.settings'

    reservation_days = fields.Integer(string='Days to release units reservation',
                                      config_parameter='nthub_realestate.reservation_days')

    location_id = fields.Many2one(
        'stock.location', 'Source Location',
        domain="[('usage','=','internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True, config_parameter='nthub_realestate.location_id')

    location_dest_id = fields.Many2one(
        'stock.location', 'Destination Location',
        domain="[('usage','=','internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True, config_parameter='nthub_realestate.location_dest_id')

    ownership_settlement_account = fields.Many2one('account.account', 'OwnerShip Settlement Account',
                                                   config_parameter='nthub_realestate.ownership_settlement_account')
    ownership_maintenance_account = fields.Many2one('account.account', 'OwnerShip Maintain Account',
                                                 config_parameter='nthub_realestate.ownership_maintenance_account')
    ownership_delay_account = fields.Many2one('account.account', 'OwnerShip Delay Account',
                                              config_parameter='nthub_realestate.ownership_delay_account')
    ownership_extras_account = fields.Many2one('account.account', 'OwnerShip Extras Account',
                                               config_parameter='nthub_realestate.ownership_extras_account')
    rental_settlement_account = fields.Many2one('account.account', 'Rental Settlement Account',
                                                config_parameter='nthub_realestate.rental_settlement_account')

    contract_article_1 = fields.Text(string="Article (1): Introduction")
    contract_article_2 = fields.Text(string="Article (2): Second Party Appointment and Scope of Work")
    contract_article_3 = fields.Text(string="Article (3): Details of Duties of Both Parties")
    contract_article_4 = fields.Text(string="Article (4): Offices of the Second Party")
    contract_article_5 = fields.Text(string="Article (5): Fees and Payment Terms")
    contract_article_6 = fields.Text(string="Article (6): Payment Delays")
    contract_article_7 = fields.Text(string="Article (7): Termination Conditions")
    contract_article_8 = fields.Text(string="Article (8): Force Majeure")
    contract_article_9 = fields.Text(string="Article (9): Special Conditions")
    contract_article_10 = fields.Text(string="Article (10): General Conditions")
    contract_article_11 = fields.Text(string="Article (11): Indemnification of Both Parties")
    contract_article_12 = fields.Text(string="Article (12): Governing Law")
    contract_article_13 = fields.Text(string="Article (13): Correspondence")
    contract_article_14 = fields.Text(string="Article (14): Entire Agreement")

    @api.model
    def get_values(self):
        res = super().get_values()
        IrConfig = self.env['ir.config_parameter'].sudo()
        keys = range(1, 15)
        for i in keys:
            res[f'contract_article_{i}'] = IrConfig.get_param(f'rs_project.contract_article_{i}', default='')
        return res

    def set_values(self):
        super().set_values()
        IrConfig = self.env['ir.config_parameter'].sudo()
        keys = range(1, 15)
        for i in keys:
            IrConfig.set_param(f'rs_project.contract_article_{i}', getattr(self, f'contract_article_{i}', '') or '')




