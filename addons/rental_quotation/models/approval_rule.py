# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class RentalApprovalRule(models.Model):
    _name = 'rental.approval.rule'
    _description = 'Rental Quotation Approval Rules'
    _order = 'sequence, approval_level'

    name = fields.Char(string='Rule Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Approval Level
    approval_level = fields.Integer(
        string='Approval Level',
        required=True,
        help="1 = First level, 2 = Second level, etc."
    )
    
    # Rule Conditions
    rule_type = fields.Selection([
        ('amount', 'Based on Amount'),
        ('discount', 'Based on Discount'),
        ('user_role', 'Based on User Role'),
        ('property_type', 'Based on Property Type'),
        ('custom', 'Custom Condition')
    ], string='Rule Type', required=True)
    
    condition_type = fields.Selection([
        ('amount', 'Amount Based'),
        ('discount', 'Discount Based'),
        ('customer_type', 'Customer Type Based'),
        ('property_type', 'Property Type Based'),
        ('always', 'Always Applicable')
    ], string='Condition Type', required=True, default='always')
    
    # Amount-based conditions
    min_amount = fields.Float(string='Minimum Amount')
    max_amount = fields.Float(string='Maximum Amount')
    
    # Discount-based conditions
    max_discount_percentage = fields.Float(string='Maximum Discount %')
    max_discount_amount = fields.Float(string='Maximum Discount Amount')
    
    # User role conditions
    salesperson_groups = fields.Many2many(
        'res.groups',
        'approval_rule_salesperson_groups_rel',
        string='Salesperson Groups',
        help="If salesperson belongs to these groups, this rule applies"
    )
    
    # Property type conditions
    property_types = fields.Many2many(
        'rs.project.type',
        string='Property Types',
        help="Rule applies to these property types"
    )
    
    # Custom domain condition
    domain_condition = fields.Text(
        string='Domain Condition',
        help="Python domain condition for custom rules"
    )
    
    # Approver Configuration
    approver_type = fields.Selection([
        ('specific_user', 'Specific User'),
        ('user_group', 'User Group'),
        ('manager', 'Salesperson Manager'),
        ('department_manager', 'Department Manager'),
        ('company_manager', 'Company Manager')
    ], string='Approver Type', required=True)
    
    approver_user_id = fields.Many2one(
        'res.users',
        string='Specific Approver'
    )
    
    approver_group_id = fields.Many2one(
        'res.groups',
        string='Approver Group'
    )
    
    # Notifications
    send_email_notification = fields.Boolean(
        string='Send Email Notification',
        default=True
    )
    
    send_system_notification = fields.Boolean(
        string='Send System Notification',
        default=True
    )
    
    # Auto-approval settings
    auto_approve_after_hours = fields.Integer(
        string='Auto-approve After (Hours)',
        help="Automatically approve if no action taken within this time"
    )
    
    escalate_after_hours = fields.Integer(
        string='Escalate After (Hours)',
        help="Escalate to next level if no action taken"
    )
    
    # Comments and description
    description = fields.Text(string='Description')
    comments = fields.Text(string='Internal Comments')

    # Company field
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    # Self-approval field
    can_self_approve = fields.Boolean(string='Can Self Approve', default=False)
    
    # Customer type conditions
    customer_type = fields.Selection([
        ('individual', 'Individual'),
        ('corporate', 'Corporate'),
        ('government', 'Government'),
        ('other', 'Other')
    ], string='Customer Type')
    
    # Property type field (simplified)
    property_type = fields.Selection([
        ('apartment', 'Apartment'),
        ('villa', 'Villa'),
        ('office', 'Office'),
        ('warehouse', 'Warehouse'),
        ('shop', 'Shop'),
        ('other', 'Other')
    ], string='Property Type')

    @api.constrains('approval_level')
    def _check_approval_level(self):
        """Validate approval level"""
        for rule in self:
            if rule.approval_level <= 0:
                raise ValidationError(_('Approval level must be positive.'))

    @api.constrains('min_amount', 'max_amount')
    def _check_amount_range(self):
        """Validate amount range"""
        for rule in self:
            if rule.rule_type == 'amount':
                if rule.min_amount < 0:
                    raise ValidationError(_('Minimum amount cannot be negative.'))
                if rule.max_amount > 0 and rule.min_amount > rule.max_amount:
                    raise ValidationError(_('Minimum amount cannot exceed maximum amount.'))

    @api.constrains('max_discount_percentage')
    def _check_discount_percentage(self):
        """Validate discount percentage"""
        for rule in self:
            if rule.rule_type == 'discount' and rule.max_discount_percentage > 100:
                raise ValidationError(_('Discount percentage cannot exceed 100%.'))

    @api.constrains('approver_type', 'approver_user_id', 'approver_group_id')
    def _check_approver_configuration(self):
        """Validate approver configuration"""
        for rule in self:
            if rule.approver_type == 'specific_user' and not rule.approver_user_id:
                raise ValidationError(_('Please specify the approver user.'))
            if rule.approver_type == 'user_group' and not rule.approver_group_id:
                raise ValidationError(_('Please specify the approver group.'))

    def _check_rule_applies(self, quotation):
        """Check if this rule applies to the given quotation"""
        self.ensure_one()
        
        if self.rule_type == 'amount':
            return self._check_amount_condition(quotation)
        elif self.rule_type == 'discount':
            return self._check_discount_condition(quotation)
        elif self.rule_type == 'user_role':
            return self._check_user_role_condition(quotation)
        elif self.rule_type == 'property_type':
            return self._check_property_type_condition(quotation)
        elif self.rule_type == 'custom':
            return self._check_custom_condition(quotation)
        
        return False

    def _check_amount_condition(self, quotation):
        """Check amount-based condition"""
        amount = quotation.total_amount
        
        if self.min_amount > 0 and amount < self.min_amount:
            return False
        if self.max_amount > 0 and amount > self.max_amount:
            return False
        
        return True

    def _check_discount_condition(self, quotation):
        """Check discount-based condition"""
        # Check percentage discount
        if self.max_discount_percentage > 0:
            if quotation.discount_type == 'percentage':
                if quotation.discount_value > self.max_discount_percentage:
                    return True
        
        # Check amount discount
        if self.max_discount_amount > 0:
            if quotation.discount_amount > self.max_discount_amount:
                return True
        
        # Check line-level discounts
        for line in quotation.quotation_line_ids:
            if line.line_discount_type == 'percentage':
                if line.line_discount_value > self.max_discount_percentage:
                    return True
            elif line.line_discount_amount > self.max_discount_amount:
                return True
        
        return False

    def _check_user_role_condition(self, quotation):
        """Check user role condition"""
        if not self.salesperson_groups:
            return True
        
        user_groups = quotation.salesperson_id.groups_id
        return bool(set(self.salesperson_groups.ids) & set(user_groups.ids))

    def _check_property_type_condition(self, quotation):
        """Check property type condition"""
        if not self.property_types:
            return True
        
        quotation_property_types = quotation.quotation_line_ids.mapped('property_id.ptype')
        return bool(set(self.property_types.ids) & set(quotation_property_types.ids))

    def _check_custom_condition(self, quotation):
        """Check custom domain condition"""
        if not self.domain_condition:
            return True
        
        try:
            domain = eval(self.domain_condition)
            return bool(quotation.filtered_domain(domain))
        except Exception:
            return False

    def _user_can_approve(self, user, quotation):
        """Check if user can approve based on this rule"""
        self.ensure_one()
        
        if self.approver_type == 'specific_user':
            return user.id == self.approver_user_id.id
        
        elif self.approver_type == 'user_group':
            return self.approver_group_id in user.groups_id
        
        elif self.approver_type == 'manager':
            # Check if user is manager of the salesperson
            return user.id == quotation.salesperson_id.parent_id.id
        
        elif self.approver_type == 'department_manager':
            # Check if user is department manager
            salesperson_employee = quotation.salesperson_id.employee_id
            if salesperson_employee and salesperson_employee.department_id:
                return user.id == salesperson_employee.department_id.manager_id.user_id.id
            return False
        
        elif self.approver_type == 'company_manager':
            # Check if user has company management rights
            return user.has_group('base.group_system')
        
        return False

    def _get_approver(self, quotation):
        """Get the specific approver for this quotation"""
        self.ensure_one()
        
        if self.approver_type == 'specific_user':
            return self.approver_user_id or False
        
        elif self.approver_type == 'user_group':
            # Return first active user in the group
            users = self.env['res.users'].search([
                ('groups_id', 'in', self.approver_group_id.id),
                ('active', '=', True)
            ], limit=1)
            return users[0] if users else False
        
        elif self.approver_type == 'manager':
            return quotation.salesperson_id.parent_id or False
        
        elif self.approver_type == 'department_manager':
            salesperson_employee = quotation.salesperson_id.employee_id
            if salesperson_employee and salesperson_employee.department_id:
                return salesperson_employee.department_id.manager_id.user_id
            return False
        
        elif self.approver_type == 'company_manager':
            # Return first system admin
            users = self.env['res.users'].search([
                ('groups_id', 'in', self.env.ref('base.group_system').id),
                ('active', '=', True)
            ], limit=1)
            return users[0] if users else False
        
        return False

    @api.model
    def get_applicable_rules(self, quotation):
        """Get all rules that apply to the quotation"""
        rules = self.search([('active', '=', True)], order='sequence, approval_level')
        applicable_rules = rules.filtered(lambda r: r._check_rule_applies(quotation))
        return applicable_rules

    def name_get(self):
        """Custom name display"""
        result = []
        for rule in self:
            name = f"[L{rule.approval_level}] {rule.name}"
            if rule.rule_type:
                name += f" ({dict(rule._fields['rule_type'].selection)[rule.rule_type]})"
            result.append((rule.id, name))
        return result

    def toggle_active(self):
        """Toggle active state"""
        for rule in self:
            rule.active = not rule.active