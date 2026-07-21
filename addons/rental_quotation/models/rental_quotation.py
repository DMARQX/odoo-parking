# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class RentalQuotation(models.Model):
    _name = 'rental.quotation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Rental Quotation'
    _order = 'create_date desc'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(
        string='Quotation Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        help="The customer who requested the quotation"
    )
    
    # Arabic Quotation Fields / حقول عرض السعر العربي
    quotation_subject = fields.Char(
        string='Subject / الموضوع',
        help="Subject of the quotation like 'برج طريق الملك'"
    )
    
    contact_person_name = fields.Char(
        string='Contact Person / اسم الأستاذ',
        help="Contact person name like 'إياد إلياس'"
    )
    
    salesperson_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        default=lambda self: self.env.user,
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    
    # Dates
    quotation_date = fields.Date(
        string='Quotation Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )
    
    validity_date = fields.Date(
        string='Valid Until',
        required=True,
        default=lambda self: fields.Date.today() + timedelta(days=30),
        tracking=True
    )
    
    grace_period = fields.Integer(
        string='Grace Period (Days) / فترة السماح (أيام)',
        compute='_compute_grace_period',
        store=True,
        readonly=False,
        help='Number of days units remain reserved after validity date expires. Calculated as difference between Quotation Date and Valid Until date.'
    )
    
    grace_period_end_date = fields.Date(
        string='Grace Period End Date / تاريخ نهاية فترة السماح',
        compute='_compute_grace_period_end_date',
        store=True,
        help='Date when the grace period expires and units become available again'
    )
    
    # Status and Workflow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('sent', 'Sent to Customer'),
        ('accepted', 'Accepted by Customer'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('converted', 'Converted to Contract')
    ], string='Status', default='draft', tracking=True)
    
    # Quotation Lines
    quotation_line_ids = fields.One2many(
        'rental.quotation.line',
        'quotation_id',
        string='Quotation Lines'
    )
    
    # Reservation tracking
    reservation_count = fields.Integer(
        string='Reservation Count',
        default=0,
        readonly=True,
        help='Number of reservations created from this quotation'
    )
    
    # Pricing
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_amounts',
        store=True
    )
    
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ], string='Discount Type', default='percentage')
    
    discount_value = fields.Float(string='Discount Value')
    
    discount_amount = fields.Float(
        string='Discount Amount',
        compute='_compute_amounts',
        store=True
    )
    
    total_amount = fields.Float(
        string='Total Amount',
        compute='_compute_amounts',
        store=True
    )
    
    # Additional Fees
    management_fee = fields.Float(string='Management Fee')
    insurance_fee = fields.Float(string='Insurance Fee')
    maintenance_fee = fields.Float(string='Maintenance Fee')
    service_fees = fields.Float(string='Service Fees / رسوم الخدمة', help='Service fees to be added to the total amount')
    
    # Terms and Conditions Template
    terms_template_id = fields.Many2one(
        'quotation.terms.template',
        string='Terms Template / قالب الشروط',
        help='Select a predefined terms and conditions template'
    )
    
    # Salutation (Greeting before table)
    salutation_html = fields.Html(
        string='Salutation / التحية',
        help='Greeting text shown above the rental fees table'
    )
    
    # Lease Requirements & Conditions
    lease_requirements_html = fields.Html(
        string='Lease Agreement Requirements & Conditions / متطلبات وشروط عقد الإيجار',
        help='Requirements and conditions (payment terms, documents, etc.)'
    )
    
    # Legacy fields (kept for backward compatibility)
    payment_terms = fields.Text(string='Payment Terms')
    terms_conditions = fields.Html(
        string='Terms & Conditions / الشروط والأحكام',
        help='Terms and conditions content (supports Arabic/English HTML)'
    )
    notes = fields.Text(string='Internal Notes')
    
    # Approval Workflow
    approval_required = fields.Boolean(
        string='Approval Required',
        compute='_compute_approval_required',
        store=True
    )
    
    current_approval_level = fields.Integer(
        string='Current Approval Level',
        default=0
    )
    
    max_approval_level = fields.Integer(
        string='Maximum Approval Level',
        compute='_compute_max_approval_level'
    )
    
    approval_history_ids = fields.One2many(
        'rental.quotation.approval',
        'quotation_id',
        string='Approval History'
    )
    
    # Computed Fields
    is_expired = fields.Boolean(
        string='Is Expired',
        compute='_compute_is_expired',
        store=True
    )
    
    can_approve = fields.Boolean(
        string='Can Approve',
        compute='_compute_user_permissions'
    )
    
    can_reject = fields.Boolean(
        string='Can Reject',
        compute='_compute_user_permissions'
    )
    
    next_approver_id = fields.Many2one(
        'res.users',
        string='Next Approver',
        compute='_compute_next_approver'
    )

    @api.model
    def create(self, vals):
        """Generate sequence number for new quotations"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('rental.quotation') or _('New')
        return super().create(vals)
    
    @api.depends('quotation_date', 'validity_date')
    def _compute_grace_period(self):
        """Calculate grace period as difference between quotation date and validity date"""
        for quotation in self:
            if quotation.quotation_date and quotation.validity_date:
                delta = quotation.validity_date - quotation.quotation_date
                quotation.grace_period = delta.days
            else:
                quotation.grace_period = 0
    
    @api.depends('validity_date', 'grace_period')
    def _compute_grace_period_end_date(self):
        """Calculate the end date of grace period"""
        for quotation in self:
            if quotation.validity_date and quotation.grace_period:
                quotation.grace_period_end_date = quotation.validity_date + timedelta(days=quotation.grace_period)
            else:
                quotation.grace_period_end_date = quotation.validity_date

    @api.depends('quotation_line_ids.total_price', 'discount_type', 'discount_value', 
                 'management_fee', 'insurance_fee', 'maintenance_fee', 'service_fees')
    def _compute_amounts(self):
        """Calculate quotation amounts"""
        for quotation in self:
            # Calculate subtotal
            quotation.subtotal = sum(quotation.quotation_line_ids.mapped('total_price'))
            
            # Calculate discount
            if quotation.discount_type == 'percentage':
                quotation.discount_amount = quotation.subtotal * (quotation.discount_value / 100)
            else:
                quotation.discount_amount = quotation.discount_value
            
            # Calculate total
            quotation.total_amount = (
                quotation.subtotal - 
                quotation.discount_amount + 
                quotation.management_fee + 
                quotation.insurance_fee + 
                quotation.maintenance_fee + 
                quotation.service_fees
            )

    @api.depends('total_amount', 'discount_value', 'salesperson_id')
    def _compute_approval_required(self):
        """Determine if approval is required based on configured rules"""
        for quotation in self:
            approval_rules = self.env['rental.approval.rule'].search([
                ('active', '=', True)
            ], order='sequence')
            
            quotation.approval_required = False
            for rule in approval_rules:
                if rule._check_rule_applies(quotation):
                    quotation.approval_required = True
                    break

    @api.depends('approval_required')
    def _compute_max_approval_level(self):
        """Calculate maximum approval level needed"""
        for quotation in self:
            if not quotation.approval_required:
                quotation.max_approval_level = 0
                continue
                
            max_level = 0
            approval_rules = self.env['rental.approval.rule'].search([
                ('active', '=', True)
            ])
            
            for rule in approval_rules:
                if rule._check_rule_applies(quotation):
                    if rule.approval_level > max_level:
                        max_level = rule.approval_level
            
            quotation.max_approval_level = max_level

    @api.depends('validity_date')
    def _compute_is_expired(self):
        """Check if quotation is expired"""
        today = fields.Date.today()
        for quotation in self:
            quotation.is_expired = quotation.validity_date < today
    
    @api.onchange('terms_template_id')
    def _onchange_terms_template(self):
        """Load terms and conditions content from selected template"""
        if self.terms_template_id:
            self.salutation_html = self.terms_template_id.salutation_html
            self.lease_requirements_html = self.terms_template_id.content_html
            # Backward compatibility
            self.terms_conditions = self.terms_template_id.content_html

    @api.depends('state', 'current_approval_level', 'max_approval_level')
    def _compute_user_permissions(self):
        """Calculate user permissions for approval actions"""
        for quotation in self:
            quotation.can_approve = False
            quotation.can_reject = False
            
            if quotation.state not in ['submitted', 'under_review']:
                continue
                
            # Check if user can approve at current level
            current_user = self.env.user
            approval_rules = self.env['rental.approval.rule'].search([
                ('approval_level', '=', quotation.current_approval_level + 1),
                ('active', '=', True)
            ])
            
            for rule in approval_rules:
                if rule._user_can_approve(current_user, quotation):
                    quotation.can_approve = True
                    quotation.can_reject = True
                    break

    @api.depends('current_approval_level', 'max_approval_level')
    def _compute_next_approver(self):
        """Find next approver based on approval rules"""
        for quotation in self:
            quotation.next_approver_id = False
            
            if quotation.current_approval_level >= quotation.max_approval_level:
                continue
                
            next_level = quotation.current_approval_level + 1
            approval_rules = self.env['rental.approval.rule'].search([
                ('approval_level', '=', next_level),
                ('active', '=', True)
            ], limit=1)
            
            if approval_rules:
                quotation.next_approver_id = approval_rules._get_approver(quotation)

    def action_submit_for_approval(self):
        """Submit quotation for approval"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Only draft quotations can be submitted for approval.'))
        
        if not self.quotation_line_ids:
            raise UserError(_('Please add at least one quotation line.'))
        
        if self.approval_required:
            self.state = 'submitted'
            self.current_approval_level = 0
            self._send_approval_notification()
        else:
            self.state = 'approved'
        
        self.message_post(
            body=_('Quotation submitted for approval.'),
            message_type='notification'
        )

    def action_approve(self):
        """Approve quotation at current level"""
        self.ensure_one()
        
        if not self.can_approve:
            raise UserError(_('You do not have permission to approve this quotation.'))
        
        # Record approval
        self.env['rental.quotation.approval'].create({
            'quotation_id': self.id,
            'user_id': self.env.user.id,
            'approval_level': self.current_approval_level + 1,
            'decision': 'approved',
            'approval_date': fields.Datetime.now(),
            'comments': _('Approved by %s') % self.env.user.name
        })
        
        self.current_approval_level += 1
        
        # Check if all approvals are complete
        if self.current_approval_level >= self.max_approval_level:
            self.state = 'approved'
            self.message_post(
                body=_('Quotation fully approved and ready to send.'),
                message_type='notification'
            )
        else:
            self.state = 'under_review'
            self._send_approval_notification()

    def action_reject(self):
        """Reject quotation and release reserved units"""
        self.ensure_one()
        
        if not self.can_reject:
            raise UserError(_('You do not have permission to reject this quotation.'))
        
        # Release reserved units back to free
        released_units = []
        for line in self.quotation_line_ids:
            if line.property_id and line.property_id.state == 'reserved':
                line.property_id.write({'state': 'free'})
                released_units.append(line.property_id.name)
        
        # Record rejection
        self.env['rental.quotation.approval'].create({
            'quotation_id': self.id,
            'user_id': self.env.user.id,
            'approval_level': self.current_approval_level + 1,
            'decision': 'rejected',
            'approval_date': fields.Datetime.now(),
            'comments': _('Rejected by %s') % self.env.user.name
        })
        
        self.state = 'rejected'
        
        # Log the release
        if released_units:
            self.message_post(
                body=_('Quotation rejected.<br/>Units released from reservation: %s') % ', '.join(released_units),
                message_type='notification'
            )
        else:
            self.message_post(
                body=_('Quotation rejected.'),
                message_type='notification'
            )

    def action_send_to_customer(self):
        """Send quotation to customer and auto-reserve units"""
        self.ensure_one()
        
        if self.state != 'approved':
            raise UserError(_('Only approved quotations can be sent to customers.'))
        
        # Check for conflicts - units already reserved or not available
        unavailable_units = []
        for line in self.quotation_line_ids:
            if line.property_id and line.property_id.state != 'free':
                unavailable_units.append(f"{line.property_id.name} ({dict(line.property_id._fields['state'].selection).get(line.property_id.state, line.property_id.state)})")
        
        if unavailable_units:
            raise UserError(
                _('Cannot send quotation. The following units are no longer available:\n%s\n\nPlease remove these units from the quotation or wait until they become available.') 
                % '\n'.join(unavailable_units)
            )
        
        # Auto-reserve all units in the quotation
        reserved_units = []
        for line in self.quotation_line_ids:
            if line.property_id and line.property_id.state == 'free':
                line.property_id.write({'state': 'reserved'})
                reserved_units.append(line.property_id.name)
        
        self.state = 'sent'
        
        # Send email with quotation
        template = self.env.ref('rental_quotation.email_template_quotation_send', False)
        if template:
            template.send_mail(self.id, force_send=True)
        
        # Log the reservation
        if reserved_units:
            self.message_post(
                body=_('Quotation sent to customer via email.<br/>Units automatically reserved: %s') % ', '.join(reserved_units),
                message_type='notification'
            )
        else:
            self.message_post(
                body=_('Quotation sent to customer via email.'),
                message_type='notification'
            )

    def action_customer_accept(self):
        """Customer accepts the quotation"""
        self.ensure_one()
        self.state = 'accepted'
        
        self.message_post(
            body=_('Quotation accepted by customer.'),
            message_type='notification'
        )

    def action_convert_to_contract(self):
        """Convert quotation to rental contract - Creates reservations for each unit"""
        self.ensure_one()
        
        if self.state != 'accepted':
            raise UserError(_('Only accepted quotations can be converted to contracts.'))
        
        if not self.quotation_line_ids:
            raise UserError(_('Cannot convert quotation without quotation lines.'))
        
        # Create reservations for each quotation line
        created_reservations = self.env['unit.reservation']
        
        for line in self.quotation_line_ids:
            if not line.property_id:
                continue
                
            # Check if property is available or reserved (by this quotation)
            if line.property_id.state not in ['free', 'reserved']:
                raise UserError(
                    _('Property %s is no longer available. Please review the quotation.') % 
                    line.property_id.name
                )
            
            # Create reservation for this unit
            reservation_vals = {
                'quotation_reference': self.name,  # Store quotation number as string
                'rs_project': line.property_id.rs_project_id.id,
                'rs_project_code': line.property_id.rs_project_id.code,
                'rs_project_unit': line.property_id.id,
                'unit_code': line.property_id.code,
                'floor': line.property_id.floor,
                'address': self._format_property_address(line.property_id),
                'pricing': int(line.total_price),
                'type': line.property_id.ptype.id if line.property_id.ptype else False,
                'status': line.property_id.status.id if line.property_id.status else False,
                'region': line.property_id.region.id if line.property_id.region else False,
                'partner_id': self.partner_id.id,
                'rs_project_area': int(line.property_area or 0),
                'state': 'confirmed',
            }
            
            reservation = self.env['unit.reservation'].create(reservation_vals)
            created_reservations |= reservation
            
            # Update unit state to reserved
            line.property_id.write({'state': 'reserved'})
        
        # Mark quotation as converted and update reservation count
        self.write({
            'state': 'converted',
            'reservation_count': len(created_reservations)
        })
        
        # Post message with created reservations count
        self.message_post(
            body=_('Quotation converted to contract. Created %d reservation(s) for units: %s') % (
                len(created_reservations),
                ', '.join(created_reservations.mapped('name'))
            ),
            message_type='notification'
        )
        
        # Return action to view created reservations
        return {
            'name': _('Created Reservations from Quotation: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'unit.reservation',
            'view_mode': 'list,form',
            'domain': [('quotation_reference', '=', self.name)],
            'context': {
                'default_partner_id': self.partner_id.id,
            },
            'target': 'current'
        }
    
    def _format_property_address(self, property_unit):
        """Format property address from sub.property"""
        address_parts = []
        if property_unit.street:
            address_parts.append(property_unit.street)
        if property_unit.street2:
            address_parts.append(property_unit.street2)
        if property_unit.city:
            address_parts.append(property_unit.city)
        if property_unit.zip:
            address_parts.append(property_unit.zip)
        return ', '.join(address_parts)

    def _send_approval_notification(self):
        """Send notification to next approver"""
        if self.next_approver_id:
            # Create activity for next approver
            self.activity_schedule(
                'rental_quotation.mail_activity_approval_request',
                user_id=self.next_approver_id.id,
                summary=_('Quotation Approval Required: %s') % self.name,
                note=_('Please review and approve quotation %s for customer %s') % (
                    self.name, self.partner_id.name
                )
            )

    @api.model
    def _cron_check_expired_quotations(self):
        """Cron job to mark expired quotations and release reserved units"""
        expired_quotations = self.search([
            ('state', 'in', ['sent', 'approved']),
            ('validity_date', '<', fields.Date.today())
        ])
        
        # Release reserved units for expired quotations
        for quotation in expired_quotations:
            released_units = []
            for line in quotation.quotation_line_ids:
                if line.property_id and line.property_id.state == 'reserved':
                    line.property_id.write({'state': 'free'})
                    released_units.append(line.property_id.name)
            
            # Log the expiration and release
            message = _('Quotation expired on %s') % quotation.validity_date
            if released_units:
                message += _('<br/>Released units: %s') % ', '.join(released_units)
            quotation.message_post(body=message)
            quotation.write({'state': 'expired'})
    
    @api.model
    def _cron_release_units_after_grace_period(self):
        """Cron job to release units after grace period expires for sent/accepted quotations"""
        today = fields.Date.today()
        
        # Find quotations where grace period has expired
        quotations = self.search([
            ('state', 'in', ['sent', 'accepted']),
            ('grace_period_end_date', '<', today)
        ])
        
        for quotation in quotations:
            released_units = []
            for line in quotation.quotation_line_ids:
                if line.property_id and line.property_id.state == 'reserved':
                    line.property_id.write({'state': 'free'})
                    released_units.append(line.property_id.name or line.property_id.unit_number)
            
            # Log the release
            if released_units:
                message = _('Grace period expired on %s. Released units: %s') % (
                    quotation.grace_period_end_date,
                    ', '.join(released_units)
                )
                quotation.message_post(body=message, message_type='notification')
                _logger.info('Released %d units for quotation %s after grace period', 
                           len(released_units), quotation.name)


    def action_view_approval_history(self):
        """Open approval history view"""
        return {
            'name': 'Approval History',
            'type': 'ir.actions.act_window',
            'res_model': 'rental.quotation.approval',
            'view_mode': 'list,form',
            'domain': [('quotation_id', '=', self.id)],
            'context': {'default_quotation_id': self.id}
        }
    
    def action_view_reservations(self):
        """Open reservations created from this quotation"""
        self.ensure_one()
        return {
            'name': _('Reservations from Quotation: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'unit.reservation',
            'view_mode': 'list,form',
            'domain': [('quotation_reference', '=', self.name)],
            'context': {
                'default_partner_id': self.partner_id.id,
            },
            'target': 'current'
        }