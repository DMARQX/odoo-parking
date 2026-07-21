# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class RentalQuotationSimple(models.Model):
    _name = 'rental.quotation'
    _description = 'Rental Quotation'
    # _inherit = ['mail.thread']  # Remove mail dependency for now

    # Basic fields only
    name = fields.Char(
        string='Quotation Number',
        required=True,
        default=lambda self: _('New')
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True
    )
    
    quotation_date = fields.Date(
        string='Quotation Date',
        default=fields.Date.today,
        required=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft')
    
    total_amount = fields.Float(
        string='Total Amount',
        default=0.0
    )
    
    description = fields.Text(string='Description')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('rental.quotation') or _('New')
        return super().create(vals)
    
    def action_submit_for_approval(self):
        self.write({'state': 'submitted'})
        return True
    
    def action_approve(self):
        self.write({'state': 'approved'})
        return True
    
    def action_reject(self):
        self.write({'state': 'rejected'})
        return True