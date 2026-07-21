# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    name_english = fields.Char(
        string='English Name | الاسم بالإنجليزية',
        help='Employee name in English | اسم الموظف بالإنجليزية',
        translate=False
    )
    
    name_arabic = fields.Char(
        string='Arabic Name | الاسم بالعربية',
        help='Employee name in Arabic | اسم الموظف بالعربية',
        translate=False
    )
    
    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """Override name search to search in both English and Arabic names"""
        args = args or []
        if name:
            # Search in name, name_english, and name_arabic
            domain = ['|', '|', 
                     ('name', operator, name),
                     ('name_english', operator, name),
                     ('name_arabic', operator, name)]
            return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
        return super()._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)
    
    def name_get(self):
        """Display name based on user language context"""
        result = []
        for employee in self:
            # Get user's language
            lang = self.env.context.get('lang', 'en_US')
            
            # If Arabic language and Arabic name exists, use it
            if lang and lang.startswith('ar') and employee.name_arabic:
                name = employee.name_arabic
            # If English name exists, use it
            elif employee.name_english:
                name = employee.name_english
            # Otherwise use default name
            else:
                name = employee.name or _('New Employee')
            
            result.append((employee.id, name))
        return result
