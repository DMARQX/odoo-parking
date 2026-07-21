# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HrContract(models.Model):
    _inherit = 'hr.contract'

    allowance_ids = fields.One2many(
        'hr.allowance',
        'contract_id',
        string='Allowances | البدلات',
        help='Employee allowances for this contract | بدلات الموظف لهذا العقد'
    )
    
    total_allowances = fields.Float(
        string='Total Allowances | إجمالي البدلات',
        compute='_compute_total_allowances',
        store=True,
        help='Sum of all allowances | مجموع جميع البدلات'
    )
    
    total_salary_with_allowances = fields.Float(
        string='Total Salary + Allowances | إجمالي الراتب + البدلات',
        compute='_compute_total_salary_with_allowances',
        store=True,
        help='Basic salary plus all allowances | الراتب الأساسي بالإضافة إلى جميع البدلات'
    )
    
    allowances_count = fields.Integer(
        string='Allowances Count | عدد البدلات',
        compute='_compute_allowances_count',
        store=True
    )
    
    @api.depends('allowance_ids.amount', 'allowance_ids.state')
    def _compute_total_allowances(self):
        for contract in self:
            active_allowances = contract.allowance_ids.filtered(lambda a: a.state == 'active')
            contract.total_allowances = sum(active_allowances.mapped('amount'))
    
    @api.depends('wage', 'total_allowances')
    def _compute_total_salary_with_allowances(self):
        for contract in self:
            contract.total_salary_with_allowances = contract.wage + contract.total_allowances
    
    @api.depends('allowance_ids')
    def _compute_allowances_count(self):
        for contract in self:
            contract.allowances_count = len(contract.allowance_ids)
    
    def action_view_allowances(self):
        """Action to view allowances for this contract"""
        self.ensure_one()
        return {
            'name': _('Allowances: %s') % self.employee_id.name,
            'domain': [('contract_id', '=', self.id)],
            'view_type': 'form',
            'res_model': 'hr.allowance',
            'view_mode': 'tree,form',
            'type': 'ir.actions.act_window',
            'context': {'default_contract_id': self.id},
        }
    
    def action_add_allowance(self):
        """Action to add a new allowance to this contract"""
        self.ensure_one()
        return {
            'name': _('Add Allowance'),
            'view_type': 'form',
            'res_model': 'hr.allowance',
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
            'context': {'default_contract_id': self.id},
            'target': 'new',
        }
    
    def create_mandatory_allowances(self):
        """Create mandatory allowances for this contract"""
        self.ensure_one()
        mandatory_types = self.env['hr.allowance.type'].search([('is_mandatory', '=', True)])
        existing_types = self.allowance_ids.mapped('allowance_type_id')
        
        for allowance_type in mandatory_types:
            if allowance_type not in existing_types:
                vals = {
                    'contract_id': self.id,
                    'allowance_type_id': allowance_type.id,
                    'amount': allowance_type.default_amount,
                    'percentage': allowance_type.default_percentage if allowance_type.percentage_of_salary else 0,
                    'date_start': self.date_start or fields.Date.today(),
                    'state': 'active',
                }
                self.env['hr.allowance'].create(vals)
    
    @api.model
    def create(self, vals):
        """Override create to add mandatory allowances"""
        contract = super().create(vals)
        contract.create_mandatory_allowances()
        return contract
    
    def write(self, vals):
        """Override write to update percentage-based allowances when wage changes"""
        result = super().write(vals)
        if 'wage' in vals:
            for contract in self:
                percentage_allowances = contract.allowance_ids.filtered(
                    lambda a: a.is_percentage_based and a.state == 'active'
                )
                for allowance in percentage_allowances:
                    allowance._compute_amount_from_percentage()
        return result