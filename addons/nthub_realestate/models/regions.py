# -*- coding: utf-8 -*-
from odoo import models, fields, api,_


class Regions(models.Model):
    _name = 'regions'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "regions"
    _rec_name = 'name'

    name = fields.Char(string=_("Name"),required=True)
    region = fields.Many2one("regions", string=_("Parent Region"))
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    street = fields.Char(string=_('Street'))
    street2 = fields.Char(string=_('Street2'))
    city = fields.Char(string=_('City'))
    country_id = fields.Many2one('res.country')
    zip = fields.Char(string=_('Zip'))
    state_id = fields.Many2one('res.country.state', string=_("State"))
    quantity = fields.Integer(string="Quantity", compute='get_project_number')
    
    def get_project_number(self):
        wn_obj = self.env['rs.project']
        own_ids = wn_obj.search_count([('region', '=', self.id)])
        self.quantity = own_ids
        
    def get_number_project(self):
        return {
            'name': _('project'),
            'domain': [('region', '=', self.id)],
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'rs.project',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'target': 'current',
        }

