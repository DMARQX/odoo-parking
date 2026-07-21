# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrAllowance(models.Model):
    _name = 'hr.allowance'
    _description = 'Employee Allowance | بدل الموظف'
    _order = 'contract_id, allowance_type_id'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name | الاسم المعروض',
        compute='_compute_display_name',
        store=True
    )
    
    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract | العقد',
        required=True,
        ondelete='cascade',
        help='Employee contract | عقد الموظف'
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee | الموظف',
        related='contract_id.employee_id',
        store=True,
        readonly=True
    )
    
    allowance_type_id = fields.Many2one(
        'hr.allowance.type',
        string='Allowance Type | نوع البدل',
        required=True,
        help='Type of allowance | نوع البدل'
    )
    
    allowance_name = fields.Char(
        string='Allowance Name | اسم البدل',
        related='allowance_type_id.name',
        readonly=True
    )
    
    allowance_code = fields.Char(
        string='Code | الكود',
        related='allowance_type_id.code',
        readonly=True
    )
    
    amount = fields.Float(
        string='Amount | المبلغ',
        required=True,
        help='Allowance amount | مبلغ البدل'
    )
    
    percentage = fields.Float(
        string='Percentage % | النسبة %',
        help='Percentage of basic salary | نسبة من الراتب الأساسي'
    )
    
    is_percentage_based = fields.Boolean(
        string='Percentage Based | مبني على النسبة',
        related='allowance_type_id.percentage_of_salary',
        readonly=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency | العملة',
        related='contract_id.currency_id',
        readonly=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft | مسودة'),
        ('active', 'Active | نشط'),
        ('inactive', 'Inactive | غير نشط'),
        ('cancelled', 'Cancelled | ملغي'),
    ], string='State | الحالة', default='draft', tracking=True)
    
    date_start = fields.Date(
        string='Start Date | تاريخ البداية',
        required=True,
        default=fields.Date.today,
        help='Date when allowance starts | تاريخ بداية البدل'
    )
    
    date_end = fields.Date(
        string='End Date | تاريخ النهاية',
        help='Date when allowance ends (leave empty for permanent) | تاريخ انتهاء البدل (اتركه فارغًا للدائم)'
    )
    
    is_taxable = fields.Boolean(
        string='Taxable | خاضع للضريبة',
        related='allowance_type_id.is_taxable',
        readonly=True
    )
    
    notes = fields.Text(
        string='Notes | ملاحظات',
        help='Additional notes about this allowance | ملاحظات إضافية حول هذا البدل'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company | الشركة',
        related='contract_id.company_id',
        store=True,
        readonly=True
    )
    
    @api.depends('allowance_type_id.name', 'employee_id.name', 'amount')
    def _compute_display_name(self):
        for record in self:
            if record.allowance_type_id and record.employee_id:
                record.display_name = f"{record.employee_id.name} - {record.allowance_type_id.name} ({record.amount})"
            else:
                record.display_name = 'New Allowance'
    
    @api.onchange('allowance_type_id')
    def _onchange_allowance_type_id(self):
        """Set default values when allowance type changes"""
        if self.allowance_type_id:
            if self.allowance_type_id.percentage_of_salary:
                self.percentage = self.allowance_type_id.default_percentage
                self._compute_amount_from_percentage()
            else:
                self.amount = self.allowance_type_id.default_amount
    
    @api.onchange('percentage')
    def _onchange_percentage(self):
        """Compute amount when percentage changes"""
        if self.is_percentage_based and self.percentage:
            self._compute_amount_from_percentage()
    
    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        """Clear percentage calculation when contract changes"""
        if self.is_percentage_based and self.percentage:
            self._compute_amount_from_percentage()
    
    def _compute_amount_from_percentage(self):
        """Compute allowance amount from percentage of basic salary"""
        if self.contract_id and self.percentage and self.is_percentage_based:
            basic_salary = self.contract_id.wage or 0
            self.amount = (basic_salary * self.percentage) / 100
    
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_end and record.date_start > record.date_end:
                raise ValidationError(_('Start date must be before end date! | تاريخ البداية يجب أن يكون قبل تاريخ النهاية!'))
    
    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount < 0:
                raise ValidationError(_('Allowance amount cannot be negative! | مبلغ البدل لا يمكن أن يكون سالبًا!'))
    
    @api.constrains('percentage')
    def _check_percentage(self):
        for record in self:
            if record.percentage < 0 or record.percentage > 100:
                raise ValidationError(_('Percentage must be between 0 and 100! | النسبة يجب أن تكون بين 0 و 100!'))
    
    def action_activate(self):
        """Activate the allowance"""
        self.write({'state': 'active'})
    
    def action_deactivate(self):
        """Deactivate the allowance"""
        self.write({'state': 'inactive'})
    
    def action_cancel(self):
        """Cancel the allowance"""
        self.write({'state': 'cancelled'})
    
    @api.model
    def create(self, vals):
        """Override create to auto-activate allowance"""
        allowance = super().create(vals)
        if allowance.state == 'draft':
            allowance.action_activate()
        return allowance
    
    _sql_constraints = [
        ('unique_allowance_per_contract', 
         'unique(contract_id, allowance_type_id)', 
         'Each allowance type can only be assigned once per contract! | كل نوع بدل يمكن تعيينه مرة واحدة فقط لكل عقد!'),
    ]