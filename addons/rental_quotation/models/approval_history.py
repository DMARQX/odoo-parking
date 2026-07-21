# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class RentalQuotationApproval(models.Model):
    _name = 'rental.quotation.approval'
    _description = 'Rental Quotation Approval History'
    _order = 'approval_date desc'
    _rec_name = 'display_name'

    quotation_id = fields.Many2one(
        'rental.quotation',
        string='Quotation',
        required=True,
        ondelete='cascade'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Approver',
        required=True
    )
    
    approval_level = fields.Integer(
        string='Approval Level',
        required=True
    )
    
    decision = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('delegated', 'Delegated'),
        ('escalated', 'Escalated')
    ], string='Decision', required=True)
    
    approval_date = fields.Datetime(
        string='Approval Date',
        required=True,
        default=fields.Datetime.now
    )
    
    comments = fields.Text(string='Comments')
    
    # Additional approval details
    delegated_to_id = fields.Many2one(
        'res.users',
        string='Delegated To',
        help="User to whom approval was delegated"
    )
    
    escalated_to_id = fields.Many2one(
        'res.users',
        string='Escalated To',
        help="User to whom approval was escalated"
    )
    
    approval_rule_id = fields.Many2one(
        'rental.approval.rule',
        string='Applied Rule',
        help="The rule that was used for this approval"
    )
    
    # System fields
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Char(string='User Agent')
    
    # Computed fields
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('user_id', 'decision', 'approval_level', 'approval_date')
    def _compute_display_name(self):
        """Compute display name for approval record"""
        for approval in self:
            date_str = approval.approval_date.strftime('%Y-%m-%d %H:%M') if approval.approval_date else ''
            approval.display_name = f"Level {approval.approval_level} - {approval.decision.title()} by {approval.user_id.name} on {date_str}"

    def name_get(self):
        """Custom name display"""
        result = []
        for approval in self:
            name = f"L{approval.approval_level} - {approval.decision.title()} ({approval.user_id.name})"
            result.append((approval.id, name))
        return result