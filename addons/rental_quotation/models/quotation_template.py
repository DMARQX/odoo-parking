# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class RentalQuotationTemplate(models.Model):
    _name = 'rental.quotation.template'
    _description = 'Rental Quotation Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    
    # Template Configuration
    property_type_ids = fields.Many2many(
        'rs.project.type',
        string='Property Types',
        help="Property types this template applies to"
    )
    
    # Default Values
    default_lease_duration = fields.Integer(
        string='Default Lease Duration (Months)',
        default=12
    )
    
    default_discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ], string='Default Discount Type', default='percentage')
    
    default_discount_value = fields.Float(string='Default Discount Value')
    
    # Default Fees
    default_management_fee = fields.Float(string='Default Management Fee')
    default_insurance_fee = fields.Float(string='Default Insurance Fee')
    default_maintenance_fee = fields.Float(string='Default Maintenance Fee')
    
    # Terms and Conditions
    default_payment_terms = fields.Text(string='Default Payment Terms')
    default_terms_conditions = fields.Html(string='Default Terms & Conditions')
    
    # Email Settings
    email_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        domain="[('model', '=', 'rental.quotation')]"
    )
    
    # Description
    description = fields.Text(string='Description')
    
    def apply_template(self, quotation):
        """Apply template settings to quotation"""
        self.ensure_one()
        
        values = {
            'discount_type': self.default_discount_type,
            'discount_value': self.default_discount_value,
            'management_fee': self.default_management_fee,
            'insurance_fee': self.default_insurance_fee,
            'maintenance_fee': self.default_maintenance_fee,
            'payment_terms': self.default_payment_terms,
            'terms_conditions': self.default_terms_conditions,
        }
        
        quotation.write(values)
        
        # Apply to lines
        for line in quotation.quotation_line_ids:
            line.proposed_lease_duration = self.default_lease_duration