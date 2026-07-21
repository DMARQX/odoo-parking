# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.http import request
import json
import base64

class RentalQuotationMobileAPI(models.Model):
    _inherit = 'rental.quotation'

    @api.model
    def mobile_get_quotations(self, filters=None):
        """Get quotations for mobile app"""
        domain = []
        if filters:
            if filters.get('state'):
                domain.append(('state', '=', filters['state']))
            if filters.get('partner_id'):
                domain.append(('partner_id', '=', filters['partner_id']))
            if filters.get('date_from'):
                domain.append(('quotation_date', '>=', filters['date_from']))
            if filters.get('date_to'):
                domain.append(('quotation_date', '<=', filters['date_to']))

        quotations = self.search(domain, limit=50)
        
        return [{
            'id': q.id,
            'name': q.name,
            'partner_name': q.partner_id.name,
            'quotation_date': q.quotation_date.strftime('%Y-%m-%d') if q.quotation_date else '',
            'total_amount': q.total_amount,
            'state': q.state,
            'state_display': dict(q._fields['state'].selection)[q.state],
            'units_count': len(q.quotation_line_ids),
        } for q in quotations]

    def mobile_get_quotation_details(self):
        """Get detailed quotation info for mobile"""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'partner_id': self.partner_id.id,
            'partner_name': self.partner_id.name,
            'partner_phone': self.partner_id.phone or '',
            'partner_email': self.partner_id.email or '',
            'quotation_date': self.quotation_date.strftime('%Y-%m-%d') if self.quotation_date else '',
            'valid_until': self.valid_until.strftime('%Y-%m-%d') if self.valid_until else '',
            'total_amount': self.total_amount,
            'discount_amount': self.discount_amount,
            'state': self.state,
            'state_display': dict(self._fields['state'].selection)[self.state],
            'notes': self.notes or '',
            'lines': [{
                'id': line.id,
                'property_name': line.property_id.name if line.property_id else '',
                'unit_name': line.unit_id.name if line.unit_id else '',
                'rental_amount': line.rental_amount,
                'quantity': line.quantity,
                'subtotal': line.subtotal,
                'description': line.description or '',
            } for line in self.quotation_line_ids],
            'approval_history': [{
                'id': history.id,
                'approver_name': history.approver_id.name,
                'approval_date': history.approval_date.strftime('%Y-%m-%d %H:%M') if history.approval_date else '',
                'action': history.action,
                'comments': history.comments or '',
            } for history in self.approval_history_ids],
        }

    @api.model
    def mobile_create_quotation(self, data):
        """Create quotation from mobile app"""
        quotation_data = {
            'partner_id': data['partner_id'],
            'quotation_date': data.get('quotation_date', fields.Date.today()),
            'valid_until': data.get('valid_until'),
            'notes': data.get('notes', ''),
        }
        
        quotation = self.create(quotation_data)
        
        # Create quotation lines
        if data.get('lines'):
            for line_data in data['lines']:
                self.env['rental.quotation.line'].create({
                    'quotation_id': quotation.id,
                    'property_id': line_data.get('property_id'),
                    'unit_id': line_data.get('unit_id'),
                    'rental_amount': line_data['rental_amount'],
                    'quantity': line_data.get('quantity', 1),
                    'description': line_data.get('description', ''),
                })
        
        quotation.calculate_totals()
        return quotation.mobile_get_quotation_details()

    def mobile_update_quotation(self, data):
        """Update quotation from mobile app"""
        self.ensure_one()
        if self.state not in ['draft', 'pending']:
            raise ValueError("Cannot update quotation in current state")
        
        # Update main quotation data
        update_data = {}
        if 'partner_id' in data:
            update_data['partner_id'] = data['partner_id']
        if 'valid_until' in data:
            update_data['valid_until'] = data['valid_until']
        if 'notes' in data:
            update_data['notes'] = data['notes']
        
        if update_data:
            self.write(update_data)
        
        # Update lines if provided
        if 'lines' in data:
            # Remove existing lines
            self.quotation_line_ids.unlink()
            
            # Create new lines
            for line_data in data['lines']:
                self.env['rental.quotation.line'].create({
                    'quotation_id': self.id,
                    'property_id': line_data.get('property_id'),
                    'unit_id': line_data.get('unit_id'),
                    'rental_amount': line_data['rental_amount'],
                    'quantity': line_data.get('quantity', 1),
                    'description': line_data.get('description', ''),
                })
        
        self.calculate_totals()
        return self.mobile_get_quotation_details()

    def mobile_submit_for_approval(self):
        """Submit quotation for approval from mobile"""
        self.ensure_one()
        self.submit_for_approval()
        return {
            'success': True,
            'message': 'Quotation submitted for approval',
            'state': self.state
        }

    def mobile_approve_quotation(self, comments=''):
        """Approve quotation from mobile"""
        self.ensure_one()
        try:
            self.approve_quotation(comments)
            return {
                'success': True,
                'message': 'Quotation approved successfully',
                'state': self.state
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'state': self.state
            }

    def mobile_reject_quotation(self, comments=''):
        """Reject quotation from mobile"""
        self.ensure_one()
        try:
            self.reject_quotation(comments)
            return {
                'success': True,
                'message': 'Quotation rejected',
                'state': self.state
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'state': self.state
            }

    @api.model
    def mobile_get_dashboard_data(self, user_id=None):
        """Get dashboard data for mobile app"""
        if not user_id:
            user_id = self.env.user.id
        
        # Basic counts
        total_quotations = self.search_count([])
        pending_quotations = self.search_count([('state', '=', 'pending')])
        approved_quotations = self.search_count([('state', '=', 'approved')])
        rejected_quotations = self.search_count([('state', '=', 'rejected')])
        
        # User's quotations
        user_quotations = self.search_count([('create_uid', '=', user_id)])
        
        # Recent quotations
        recent_quotations = self.search([
            ('create_uid', '=', user_id)
        ], limit=5, order='create_date desc')
        
        return {
            'totals': {
                'total_quotations': total_quotations,
                'pending_quotations': pending_quotations,
                'approved_quotations': approved_quotations,
                'rejected_quotations': rejected_quotations,
                'user_quotations': user_quotations,
            },
            'recent_quotations': [{
                'id': q.id,
                'name': q.name,
                'partner_name': q.partner_id.name,
                'total_amount': q.total_amount,
                'state': q.state,
                'create_date': q.create_date.strftime('%Y-%m-%d') if q.create_date else '',
            } for q in recent_quotations],
        }

class RentalQuotationMobileSync(models.Model):
    _name = 'rental.quotation.mobile.sync'
    _description = 'Mobile Sync Log'

    quotation_id = fields.Many2one('rental.quotation', 'Quotation', required=True)
    device_id = fields.Char('Device ID')
    sync_date = fields.Datetime('Sync Date', default=fields.Datetime.now)
    sync_type = fields.Selection([
        ('download', 'Download'),
        ('upload', 'Upload'),
        ('update', 'Update'),
    ], 'Sync Type')
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], 'Status')
    error_message = fields.Text('Error Message')