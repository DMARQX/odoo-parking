# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HrAllowanceType(models.Model):
    _name = 'hr.allowance.type'
    _description = 'Allowance Type | نوع البدل'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Allowance Name | اسم البدل',
        required=True,
        translate=True,
        help='Name of the allowance type | اسم نوع البدل'
    )
    
    name_arabic = fields.Char(
        string='Arabic Name | الاسم بالعربية',
        help='Arabic name for the allowance | الاسم العربي للبدل'
    )
    
    code = fields.Char(
        string='Code | الكود',
        required=True,
        help='Unique code for the allowance type | كود فريد لنوع البدل'
    )
    
    description = fields.Text(
        string='Description | الوصف',
        translate=True,
        help='Description of the allowance | وصف البدل'
    )
    
    active = fields.Boolean(
        string='Active | نشط',
        default=True,
        help='Whether this allowance type is active | ما إذا كان نوع البدل نشطًا'
    )
    
    sequence = fields.Integer(
        string='Sequence | التسلسل',
        default=10,
        help='Sequence for ordering | التسلسل للترتيب'
    )
    
    is_taxable = fields.Boolean(
        string='Taxable | خاضع للضريبة',
        default=True,
        help='Whether this allowance is subject to tax | ما إذا كان هذا البدل خاضعًا للضريبة'
    )
    
    is_mandatory = fields.Boolean(
        string='Mandatory | إجباري',
        default=False,
        help='Whether this allowance is mandatory for all contracts | ما إذا كان هذا البدل إجباريًا لجميع العقود'
    )
    
    percentage_of_salary = fields.Boolean(
        string='Percentage of Salary | نسبة من الراتب',
        default=False,
        help='If checked, allowance amount will be calculated as percentage of basic salary | إذا تم التحديد، سيتم حساب مبلغ البدل كنسبة من الراتب الأساسي'
    )
    
    default_amount = fields.Float(
        string='Default Amount | المبلغ الافتراضي',
        help='Default amount for this allowance | المبلغ الافتراضي لهذا البدل'
    )
    
    default_percentage = fields.Float(
        string='Default Percentage | النسبة الافتراضية',
        help='Default percentage if percentage_of_salary is enabled | النسبة الافتراضية إذا كان حساب النسبة من الراتب مفعلاً'
    )
    
    category = fields.Selection([
        ('transport', 'Transportation | المواصلات'),
        ('housing', 'Housing | السكن'),
        ('food', 'Food | الطعام'),
        ('communication', 'Communication | الاتصالات'),
        ('medical', 'Medical | طبي'),
        ('performance', 'Performance | الأداء'),
        ('overtime', 'Overtime | الوقت الإضافي'),
        ('special', 'Special | خاص'),
        ('other', 'Other | أخرى'),
    ], string='Category | الفئة', required=True, default='other')
    
    allowance_ids = fields.One2many(
        'hr.allowance',
        'allowance_type_id',
        string='Allowances | البدلات'
    )
    
    allowance_count = fields.Integer(
        string='Allowance Count | عدد البدلات',
        compute='_compute_allowance_count'
    )
    
    @api.depends('allowance_ids')
    def _compute_allowance_count(self):
        for record in self:
            record.allowance_count = len(record.allowance_ids)
    
    def action_view_allowances(self):
        """Action to view allowances of this type"""
        self.ensure_one()
        return {
            'name': _('Allowances: %s') % self.name,
            'domain': [('allowance_type_id', '=', self.id)],
            'view_type': 'form',
            'res_model': 'hr.allowance',
            'view_mode': 'list,form',
            'type': 'ir.actions.act_window',
        }
    
    @api.model
    def create(self, vals):
        """Override to ensure code uniqueness"""
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super().create(vals)
    
    def write(self, vals):
        """Override to ensure code uniqueness"""
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super().write(vals)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The allowance type code must be unique! | كود نوع البدل يجب أن يكون فريدًا!'),
        ('name_unique', 'unique(name)', 'The allowance type name must be unique! | اسم نوع البدل يجب أن يكون فريدًا!'),
    ]