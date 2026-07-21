# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class RentalQuotationLine(models.Model):
    _name = 'rental.quotation.line'
    _description = 'Rental Quotation Line'
    _order = 'sequence, id'

    quotation_id = fields.Many2one(
        'rental.quotation',
        string='Quotation',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Property Information
    property_id = fields.Many2one(
        'sub.property',
        string='Property Unit',
        required=True,
        domain="[('state', '=', 'free')]"
    )
    
    property_code = fields.Char(
        string='Property Code',
        related='property_id.name',
        readonly=True
    )
    
    property_area = fields.Float(
        string='Area (m²)',
        default=0.0,
        readonly=True
    )
    
    # Pricing Details
    rental_price_per_sqm = fields.Float(
        string='Rental Price per m²',
        compute='_compute_pricing',
        store=True,
        readonly=False
    )
    
    electricity_price_per_sqm = fields.Float(
        string='Electricity Price per m²',
        compute='_compute_pricing',
        store=True,
        readonly=False
    )
    
    base_rental_amount = fields.Float(
        string='Base Rental Amount',
        compute='_compute_amounts',
        store=True
    )
    
    electricity_amount = fields.Float(
        string='Electricity Amount',
        compute='_compute_amounts',
        store=True
    )
    
    # Service Fee from Property
    service_fee = fields.Float(
        string='Service Fee',
        compute='_compute_pricing',
        store=True,
        readonly=False
    )
    
    # Additional Charges
    maintenance_charge = fields.Float(string='Maintenance Charge')
    insurance_charge = fields.Float(string='Insurance Charge')
    other_charges = fields.Float(string='Other Charges')
    
    # Line Discount
    line_discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ], string='Discount Type', default='percentage')
    
    line_discount_value = fields.Float(string='Discount Value')
    
    line_discount_amount = fields.Float(
        string='Discount Amount',
        compute='_compute_amounts',
        store=True
    )
    
    # Totals
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_amounts',
        store=True
    )
    
    total_price = fields.Float(
        string='Total Price',
        compute='_compute_amounts',
        store=True
    )
    
    # Rental Terms
    proposed_lease_duration = fields.Integer(
        string='Proposed Lease Duration (Months)',
        default=12
    )
    
    move_in_date = fields.Date(string='Proposed Move-in Date')
    
    # Notes
    description = fields.Text(string='Description')
    special_terms = fields.Text(string='Special Terms')

    @api.depends('property_id')
    def _compute_pricing(self):
        """Get default pricing from property"""
        for line in self:
            if line.property_id:
                line.rental_price_per_sqm = line.property_id.rental_price_per_sqm
                line.electricity_price_per_sqm = line.property_id.electricity_price_per_sqm
                line.service_fee = line.property_id.service_fee
            else:
                line.rental_price_per_sqm = 0.0
                line.electricity_price_per_sqm = 0.0
                line.service_fee = 0.0

    @api.depends('property_area', 'rental_price_per_sqm', 'electricity_price_per_sqm', 'service_fee',
                 'maintenance_charge', 'insurance_charge', 'other_charges',
                 'line_discount_type', 'line_discount_value')
    def _compute_amounts(self):
        """Calculate line amounts"""
        for line in self:
            # Base calculations
            line.base_rental_amount = line.property_area * line.rental_price_per_sqm
            line.electricity_amount = line.property_area * line.electricity_price_per_sqm
            
            # Subtotal before discount (including service fee)
            line.subtotal = (
                line.base_rental_amount + 
                line.electricity_amount + 
                line.service_fee +
                line.maintenance_charge + 
                line.insurance_charge + 
                line.other_charges
            )
            
            # Calculate line discount
            if line.line_discount_type == 'percentage':
                line.line_discount_amount = line.subtotal * (line.line_discount_value / 100)
            else:
                line.line_discount_amount = line.line_discount_value
            
            # Final total
            line.total_price = line.subtotal - line.line_discount_amount

    @api.constrains('property_id')
    def _check_property_availability(self):
        """Ensure property is available (free or reserved by same quotation)"""
        for line in self:
            if not line.property_id:
                continue
                
            # Allow if property is free
            if line.property_id.state == 'free':
                continue
            
            # Allow if property is reserved by THIS quotation (when editing sent quotations)
            if line.property_id.state == 'reserved' and line.quotation_id.state == 'sent':
                # Check if this property is reserved by the same quotation
                reserved_by_same = self.search([
                    ('quotation_id', '=', line.quotation_id.id),
                    ('property_id', '=', line.property_id.id),
                    ('id', '!=', line.id)
                ], limit=1)
                if reserved_by_same or line.quotation_id.state == 'sent':
                    continue
            
            # Otherwise, property is not available
            raise ValidationError(
                _('Property %s is not available. It may be reserved by another quotation or already rented.') % 
                line.property_id.name
            )

    @api.constrains('line_discount_value')
    def _check_discount_value(self):
        """Validate discount value"""
        for line in self:
            if line.line_discount_type == 'percentage' and line.line_discount_value > 100:
                raise ValidationError(_('Discount percentage cannot exceed 100%.'))
            if line.line_discount_value < 0:
                raise ValidationError(_('Discount value cannot be negative.'))

    @api.onchange('property_id')
    def _onchange_property_id(self):
        """Update description when property changes"""
        if self.property_id:
            self.description = _(
                'Rental of property %s - %s m²'
            ) % (
                self.property_id.name,
                self.property_area or 0
            )