# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class RentalQuotationMobileAPI(http.Controller):
    
    @http.route('/api/rental/quotations', type='json', auth='user', methods=['GET'])
    def get_quotations(self, **kwargs):
        """Get quotations list for mobile app"""
        try:
            domain = []
            
            # Apply filters
            if kwargs.get('state'):
                domain.append(('state', '=', kwargs['state']))
            if kwargs.get('salesperson_id'):
                domain.append(('salesperson_id', '=', kwargs['salesperson_id']))
            if kwargs.get('date_from'):
                domain.append(('quotation_date', '>=', kwargs['date_from']))
            if kwargs.get('date_to'):
                domain.append(('quotation_date', '<=', kwargs['date_to']))
            
            # User can only see their own quotations unless they're a manager
            user = request.env.user
            if not user.has_group('rental_quotation.group_rental_quotation_manager'):
                domain.append(('salesperson_id', '=', user.id))
            
            quotations = request.env['rental.quotation'].search(domain, limit=kwargs.get('limit', 50))
            
            result = []
            for quotation in quotations:
                result.append({
                    'id': quotation.id,
                    'name': quotation.name,
                    'partner_name': quotation.partner_id.name,
                    'total_amount': quotation.total_amount,
                    'state': quotation.state,
                    'state_label': dict(quotation._fields['state'].selection)[quotation.state],
                    'quotation_date': quotation.quotation_date.isoformat() if quotation.quotation_date else None,
                    'validity_date': quotation.validity_date.isoformat() if quotation.validity_date else None,
                    'can_approve': quotation.can_approve,
                    'can_reject': quotation.can_reject,
                    'approval_required': quotation.approval_required,
                    'current_approval_level': quotation.current_approval_level,
                    'max_approval_level': quotation.max_approval_level,
                    'is_expired': quotation.is_expired,
                    'salesperson_name': quotation.salesperson_id.name,
                })
            
            return {
                'status': 'success',
                'data': result,
                'count': len(result)
            }
            
        except Exception as e:
            _logger.error(f"Error in get_quotations: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/api/rental/quotations/<int:quotation_id>', type='json', auth='user', methods=['GET'])
    def get_quotation_detail(self, quotation_id, **kwargs):
        """Get detailed quotation information for mobile app"""
        try:
            quotation = request.env['rental.quotation'].browse(quotation_id)
            
            if not quotation.exists():
                return {
                    'status': 'error',
                    'message': 'Quotation not found'
                }
            
            # Check access rights
            user = request.env.user
            if not user.has_group('rental_quotation.group_rental_quotation_manager'):
                if quotation.salesperson_id.id != user.id:
                    return {
                        'status': 'error',
                        'message': 'Access denied'
                    }
            
            # Get quotation lines
            lines = []
            for line in quotation.quotation_line_ids:
                lines.append({
                    'id': line.id,
                    'property_name': line.property_id.name if line.property_id else '',
                    'unit_price': line.unit_price,
                    'quantity': line.quantity,
                    'total_price': line.total_price,
                    'description': line.description or '',
                })
            
            # Get approval history
            approvals = []
            for approval in quotation.approval_history_ids:
                approvals.append({
                    'id': approval.id,
                    'approver_name': approval.approver_id.name,
                    'status': approval.status,
                    'status_label': dict(approval._fields['status'].selection)[approval.status],
                    'approval_date': approval.approval_date.isoformat() if approval.approval_date else None,
                    'comments': approval.comments or '',
                    'approval_level': approval.approval_level,
                    'auto_approved': approval.auto_approved,
                })
            
            result = {
                'id': quotation.id,
                'name': quotation.name,
                'partner_id': quotation.partner_id.id,
                'partner_name': quotation.partner_id.name,
                'partner_email': quotation.partner_id.email,
                'partner_phone': quotation.partner_id.phone,
                'salesperson_id': quotation.salesperson_id.id,
                'salesperson_name': quotation.salesperson_id.name,
                'quotation_date': quotation.quotation_date.isoformat() if quotation.quotation_date else None,
                'validity_date': quotation.validity_date.isoformat() if quotation.validity_date else None,
                'state': quotation.state,
                'state_label': dict(quotation._fields['state'].selection)[quotation.state],
                'subtotal': quotation.subtotal,
                'discount_type': quotation.discount_type,
                'discount_value': quotation.discount_value,
                'discount_amount': quotation.discount_amount,
                'management_fee': quotation.management_fee,
                'insurance_fee': quotation.insurance_fee,
                'maintenance_fee': quotation.maintenance_fee,
                'total_amount': quotation.total_amount,
                'payment_terms': quotation.payment_terms or '',
                'terms_conditions': quotation.terms_conditions or '',
                'notes': quotation.notes or '',
                'approval_required': quotation.approval_required,
                'current_approval_level': quotation.current_approval_level,
                'max_approval_level': quotation.max_approval_level,
                'can_approve': quotation.can_approve,
                'can_reject': quotation.can_reject,
                'is_expired': quotation.is_expired,
                'next_approver_id': quotation.next_approver_id.id if quotation.next_approver_id else None,
                'next_approver_name': quotation.next_approver_id.name if quotation.next_approver_id else '',
                'lines': lines,
                'approval_history': approvals,
            }
            
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            _logger.error(f"Error in get_quotation_detail: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/api/rental/quotations/<int:quotation_id>/approve', type='json', auth='user', methods=['POST'])
    def approve_quotation(self, quotation_id, **kwargs):
        """Approve a quotation via mobile app"""
        try:
            quotation = request.env['rental.quotation'].browse(quotation_id)
            
            if not quotation.exists():
                return {
                    'status': 'error',
                    'message': 'Quotation not found'
                }
            
            # Check if user can approve
            if not quotation.can_approve:
                return {
                    'status': 'error',
                    'message': 'You are not authorized to approve this quotation'
                }
            
            comments = kwargs.get('comments', '')
            
            # Call the approval method
            quotation.approve_quotation(comments=comments)
            
            return {
                'status': 'success',
                'message': 'Quotation approved successfully',
                'data': {
                    'id': quotation.id,
                    'state': quotation.state,
                    'state_label': dict(quotation._fields['state'].selection)[quotation.state],
                    'current_approval_level': quotation.current_approval_level,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in approve_quotation: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/api/rental/quotations/<int:quotation_id>/reject', type='json', auth='user', methods=['POST'])
    def reject_quotation(self, quotation_id, **kwargs):
        """Reject a quotation via mobile app"""
        try:
            quotation = request.env['rental.quotation'].browse(quotation_id)
            
            if not quotation.exists():
                return {
                    'status': 'error',
                    'message': 'Quotation not found'
                }
            
            # Check if user can reject
            if not quotation.can_reject:
                return {
                    'status': 'error',
                    'message': 'You are not authorized to reject this quotation'
                }
            
            comments = kwargs.get('comments', '')
            if not comments:
                return {
                    'status': 'error',
                    'message': 'Comments are required for rejection'
                }
            
            # Call the rejection method
            quotation.reject_quotation(comments=comments)
            
            return {
                'status': 'success',
                'message': 'Quotation rejected successfully',
                'data': {
                    'id': quotation.id,
                    'state': quotation.state,
                    'state_label': dict(quotation._fields['state'].selection)[quotation.state],
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in reject_quotation: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/api/rental/pending-approvals', type='json', auth='user', methods=['GET'])
    def get_pending_approvals(self, **kwargs):
        """Get pending approvals for current user"""
        try:
            user = request.env.user
            
            # Find quotations where user can approve
            quotations = request.env['rental.quotation'].search([
                ('state', 'in', ['submitted', 'under_review']),
                ('can_approve', '=', True)
            ])
            
            result = []
            for quotation in quotations:
                # Double check if user can actually approve
                if quotation.can_approve:
                    result.append({
                        'id': quotation.id,
                        'name': quotation.name,
                        'partner_name': quotation.partner_id.name,
                        'salesperson_name': quotation.salesperson_id.name,
                        'total_amount': quotation.total_amount,
                        'quotation_date': quotation.quotation_date.isoformat() if quotation.quotation_date else None,
                        'validity_date': quotation.validity_date.isoformat() if quotation.validity_date else None,
                        'current_approval_level': quotation.current_approval_level,
                        'max_approval_level': quotation.max_approval_level,
                        'days_pending': (fields.Date.today() - quotation.quotation_date).days if quotation.quotation_date else 0,
                        'priority': 'high' if quotation.total_amount > 50000 or quotation.discount_value > 20 else 'normal',
                    })
            
            # Sort by priority and date
            result = sorted(result, key=lambda x: (x['priority'] == 'high', x['days_pending']), reverse=True)
            
            return {
                'status': 'success',
                'data': result,
                'count': len(result)
            }
            
        except Exception as e:
            _logger.error(f"Error in get_pending_approvals: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/api/rental/dashboard-summary', type='json', auth='user', methods=['GET'])
    def get_dashboard_summary(self, **kwargs):
        """Get dashboard summary for mobile app"""
        try:
            user = request.env.user
            domain = []
            
            # Apply date filter (default: last 30 days)
            date_from = kwargs.get('date_from')
            if not date_from:
                date_from = (datetime.now() - timedelta(days=30)).date()
            else:
                date_from = fields.Date.from_string(date_from)
            
            domain.append(('quotation_date', '>=', date_from))
            
            # User can only see their own quotations unless they're a manager
            if not user.has_group('rental_quotation.group_rental_quotation_manager'):
                domain.append(('salesperson_id', '=', user.id))
            
            quotations = request.env['rental.quotation'].search(domain)
            
            # Calculate statistics
            total_quotations = len(quotations)
            pending_approvals = len(quotations.filtered(lambda q: q.state in ['submitted', 'under_review']))
            approved_quotations = len(quotations.filtered(lambda q: q.state in ['approved', 'sent', 'accepted']))
            converted_quotations = len(quotations.filtered(lambda q: q.state == 'converted'))
            rejected_quotations = len(quotations.filtered(lambda q: q.state == 'rejected'))
            
            total_value = sum(quotations.mapped('total_amount'))
            converted_value = sum(quotations.filtered(lambda q: q.state == 'converted').mapped('total_amount'))
            
            conversion_rate = (converted_quotations / total_quotations * 100) if total_quotations else 0
            
            # My pending approvals
            my_approvals = request.env['rental.quotation'].search([
                ('state', 'in', ['submitted', 'under_review']),
                ('can_approve', '=', True)
            ])
            
            result = {
                'period_days': (fields.Date.today() - date_from).days,
                'total_quotations': total_quotations,
                'pending_approvals': pending_approvals,
                'approved_quotations': approved_quotations,
                'converted_quotations': converted_quotations,
                'rejected_quotations': rejected_quotations,
                'total_value': total_value,
                'converted_value': converted_value,
                'conversion_rate': round(conversion_rate, 1),
                'average_value': round(total_value / total_quotations, 2) if total_quotations else 0,
                'my_pending_approvals': len(my_approvals),
                'performance_score': min(100, round(conversion_rate * 1.5 + (approved_quotations / total_quotations * 50 if total_quotations else 0), 1)),
            }
            
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            _logger.error(f"Error in get_dashboard_summary: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/api/rental/notifications', type='json', auth='user', methods=['GET'])
    def get_notifications(self, **kwargs):
        """Get notifications for mobile app"""
        try:
            user = request.env.user
            
            notifications = []
            
            # Pending approvals notifications
            pending_approvals = request.env['rental.quotation'].search([
                ('state', 'in', ['submitted', 'under_review']),
                ('can_approve', '=', True)
            ])
            
            for quotation in pending_approvals:
                days_pending = (fields.Date.today() - quotation.quotation_date).days
                priority = 'high' if days_pending > 2 or quotation.total_amount > 50000 else 'normal'
                
                notifications.append({
                    'id': f"approval_{quotation.id}",
                    'type': 'approval_required',
                    'title': f'Approval Required: {quotation.name}',
                    'message': f'Quotation from {quotation.salesperson_id.name} worth {quotation.total_amount:,.2f} needs approval',
                    'quotation_id': quotation.id,
                    'priority': priority,
                    'date': quotation.quotation_date.isoformat() if quotation.quotation_date else None,
                    'days_pending': days_pending,
                })
            
            # My quotations status updates
            my_quotations = request.env['rental.quotation'].search([
                ('salesperson_id', '=', user.id),
                ('write_date', '>=', fields.Datetime.now() - timedelta(days=7))
            ])
            
            for quotation in my_quotations:
                if quotation.state == 'approved':
                    notifications.append({
                        'id': f"approved_{quotation.id}",
                        'type': 'quotation_approved',
                        'title': f'Quotation Approved: {quotation.name}',
                        'message': f'Your quotation for {quotation.partner_id.name} has been approved',
                        'quotation_id': quotation.id,
                        'priority': 'normal',
                        'date': quotation.write_date.date().isoformat(),
                    })
                elif quotation.state == 'rejected':
                    notifications.append({
                        'id': f"rejected_{quotation.id}",
                        'type': 'quotation_rejected',
                        'title': f'Quotation Rejected: {quotation.name}',
                        'message': f'Your quotation for {quotation.partner_id.name} was rejected',
                        'quotation_id': quotation.id,
                        'priority': 'high',
                        'date': quotation.write_date.date().isoformat(),
                    })
            
            # Sort by priority and date
            notifications = sorted(notifications, 
                                 key=lambda x: (x['priority'] == 'high', x['date']), 
                                 reverse=True)
            
            return {
                'status': 'success',
                'data': notifications[:20],  # Limit to 20 notifications
                'count': len(notifications)
            }
            
        except Exception as e:
            _logger.error(f"Error in get_notifications: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

class RentalQuotationAuthAPI(http.Controller):
    
    @http.route('/api/rental/auth/login', type='json', auth='public', methods=['POST'], csrf=False)
    def mobile_login(self, **kwargs):
        """Mobile app login endpoint"""
        try:
            username = kwargs.get('username')
            password = kwargs.get('password')
            
            if not username or not password:
                return {
                    'status': 'error',
                    'message': 'Username and password are required'
                }
            
            # Authenticate user
            uid = request.session.authenticate(request.session.db, username, password)
            
            if uid:
                user = request.env.user
                return {
                    'status': 'success',
                    'message': 'Login successful',
                    'data': {
                        'user_id': user.id,
                        'name': user.name,
                        'email': user.email,
                        'is_manager': user.has_group('rental_quotation.group_rental_quotation_manager'),
                        'is_approver': user.has_group('rental_quotation.group_rental_quotation_approver'),
                        'session_id': request.session.sid,
                    }
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Invalid credentials'
                }
                
        except Exception as e:
            _logger.error(f"Error in mobile_login: {str(e)}")
            return {
                'status': 'error',
                'message': 'Login failed'
            }
    
    @http.route('/api/rental/auth/user-info', type='json', auth='user', methods=['GET'])
    def get_user_info(self, **kwargs):
        """Get current user information"""
        try:
            user = request.env.user
            
            return {
                'status': 'success',
                'data': {
                    'user_id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'is_manager': user.has_group('rental_quotation.group_rental_quotation_manager'),
                    'is_approver': user.has_group('rental_quotation.group_rental_quotation_approver'),
                    'company_id': user.company_id.id,
                    'company_name': user.company_id.name,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_user_info: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }