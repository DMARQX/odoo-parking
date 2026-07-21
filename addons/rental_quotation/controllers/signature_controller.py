# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
import base64
import json
import logging

_logger = logging.getLogger(__name__)

class DigitalSignatureController(http.Controller):
    
    @http.route('/web/sign/<string:access_token>', type='http', auth='public', website=True)
    def digital_sign_document(self, access_token, **kwargs):
        """Public page for digital signature"""
        
        # Find signer by access token
        signer = request.env['digital.signature.signer'].sudo().search([
            ('access_token', '=', access_token)
        ], limit=1)
        
        if not signer:
            return request.render('rental_quotation.signature_error', {
                'error_message': _('Invalid signature link or link has expired.')
            })
        
        # Check if already signed
        if signer.status == 'signed':
            return request.render('rental_quotation.signature_already_signed', {
                'signer': signer,
                'signature_request': signer.request_id
            })
        
        # Check if expired
        if signer.request_id.expires_on < fields.Datetime.now():
            return request.render('rental_quotation.signature_expired', {
                'signer': signer,
                'signature_request': signer.request_id
            })
        
        # Update viewed status
        if signer.status == 'sent':
            signer.sudo().write({
                'status': 'viewed',
                'viewed_date': fields.Datetime.now()
            })
        
        # Prepare context for template
        context = {
            'signer': signer,
            'signature_request': signer.request_id,
            'document_url': f'/web/content/digital.signature.request/{signer.request_id.id}/document_content/{signer.request_id.document_filename}',
        }
        
        return request.render('rental_quotation.digital_signature_page', context)
    
    @http.route('/web/sign/submit', type='json', auth='public', methods=['POST'], csrf=False)
    def submit_digital_signature(self, **kwargs):
        """Submit digital signature"""
        try:
            access_token = kwargs.get('access_token')
            signature_data = kwargs.get('signature_data')
            signature_method = kwargs.get('signature_method', 'canvas')
            ip_address = request.httprequest.environ.get('REMOTE_ADDR')
            user_agent = request.httprequest.environ.get('HTTP_USER_AGENT')
            
            if not access_token or not signature_data:
                return {
                    'status': 'error',
                    'message': _('Missing required signature data.')
                }
            
            # Find signer
            signer = request.env['digital.signature.signer'].sudo().search([
                ('access_token', '=', access_token)
            ], limit=1)
            
            if not signer:
                return {
                    'status': 'error',
                    'message': _('Invalid signature link.')
                }
            
            # Check if can still sign
            if signer.status not in ['sent', 'viewed']:
                return {
                    'status': 'error',
                    'message': _('Document cannot be signed at this time.')
                }
            
            # Check expiry
            if signer.request_id.expires_on < fields.Datetime.now():
                return {
                    'status': 'error',
                    'message': _('Signature request has expired.')
                }
            
            # Update signer IP and location
            signer.sudo().write({
                'ip_address': ip_address,
                'location': kwargs.get('location', '')
            })
            
            # Process signature
            signature = signer.sudo().action_sign_document(
                signature_data=signature_data,
                signature_method=signature_method
            )
            
            # Update signature with additional data
            signature.sudo().write({
                'signer_ip': ip_address,
                'signer_user_agent': user_agent
            })
            
            return {
                'status': 'success',
                'message': _('Document signed successfully!'),
                'signature_id': signature.id,
                'verification_code': signature.verification_code
            }
            
        except Exception as e:
            _logger.error(f"Error in submit_digital_signature: {str(e)}")
            return {
                'status': 'error',
                'message': _('An error occurred while processing your signature. Please try again.')
            }
    
    @http.route('/web/sign/reject', type='json', auth='public', methods=['POST'], csrf=False)
    def reject_signature(self, **kwargs):
        """Reject signature request"""
        try:
            access_token = kwargs.get('access_token')
            rejection_reason = kwargs.get('reason', '')
            
            if not access_token:
                return {
                    'status': 'error',
                    'message': _('Invalid request.')
                }
            
            # Find signer
            signer = request.env['digital.signature.signer'].sudo().search([
                ('access_token', '=', access_token)
            ], limit=1)
            
            if not signer:
                return {
                    'status': 'error',
                    'message': _('Invalid signature link.')
                }
            
            # Update signer status
            signer.sudo().write({
                'status': 'rejected',
                'ip_address': request.httprequest.environ.get('REMOTE_ADDR'),
            })
            
            # Update signature request status
            signer.request_id.sudo().write({
                'status': 'cancelled'
            })
            
            # Log rejection reason
            signer.request_id.sudo().message_post(
                body=_('Signature rejected by %s. Reason: %s') % (signer.name, rejection_reason)
            )
            
            return {
                'status': 'success',
                'message': _('Signature request has been rejected.')
            }
            
        except Exception as e:
            _logger.error(f"Error in reject_signature: {str(e)}")
            return {
                'status': 'error',
                'message': _('An error occurred. Please try again.')
            }
    
    @http.route('/web/sign/verify/<string:verification_code>', type='http', auth='public', website=True)
    def verify_signature(self, verification_code, **kwargs):
        """Verify digital signature"""
        
        # Find signature by verification code
        signature = request.env['digital.signature'].sudo().search([
            ('verification_code', '=', verification_code)
        ], limit=1)
        
        if not signature:
            return request.render('rental_quotation.signature_verification_error', {
                'error_message': _('Invalid verification code.')
            })
        
        # Get certificate data
        certificate_data = signature.get_signature_certificate()
        
        context = {
            'signature': signature,
            'certificate_data': certificate_data,
            'verification_successful': True
        }
        
        return request.render('rental_quotation.signature_verification_page', context)
    
    @http.route('/web/sign/download/<string:verification_code>', type='http', auth='public')
    def download_signature_certificate(self, verification_code, **kwargs):
        """Download signature certificate"""
        
        signature = request.env['digital.signature'].sudo().search([
            ('verification_code', '=', verification_code)
        ], limit=1)
        
        if not signature:
            return request.not_found()
        
        # Generate certificate PDF
        certificate_pdf = signature._generate_signature_certificate_pdf()
        
        filename = f"signature_certificate_{signature.verification_code}.pdf"
        
        return request.make_response(
            certificate_pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', len(certificate_pdf)),
            ]
        )

class DigitalSignatureAPI(http.Controller):
    
    @http.route('/api/signature/requests', type='json', auth='user', methods=['GET'])
    def get_signature_requests(self, **kwargs):
        """Get signature requests for API"""
        try:
            user = request.env.user
            
            # Build domain
            domain = []
            if not user.has_group('rental_quotation.group_rental_quotation_manager'):
                domain.append(('requester_id', '=', user.id))
            
            # Apply filters
            if kwargs.get('status'):
                domain.append(('status', '=', kwargs['status']))
            if kwargs.get('document_type'):
                domain.append(('document_type', '=', kwargs['document_type']))
            
            requests = request.env['digital.signature.request'].search(domain, limit=50)
            
            result = []
            for req in requests:
                result.append({
                    'id': req.id,
                    'name': req.name,
                    'document_reference': req.document_reference,
                    'document_type': req.document_type,
                    'status': req.status,
                    'total_signers': req.total_signers,
                    'signed_count': req.signed_count,
                    'completion_percentage': req.completion_percentage,
                    'expires_on': req.expires_on.isoformat() if req.expires_on else None,
                    'created_date': req.create_date.isoformat() if req.create_date else None,
                })
            
            return {
                'status': 'success',
                'data': result,
                'count': len(result)
            }
            
        except Exception as e:
            _logger.error(f"Error in get_signature_requests: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    @http.route('/api/signature/requests/<int:request_id>/send', type='json', auth='user', methods=['POST'])
    def send_signature_request(self, request_id, **kwargs):
        """Send signature request via API"""
        try:
            signature_request = request.env['digital.signature.request'].browse(request_id)
            
            if not signature_request.exists():
                return {
                    'status': 'error',
                    'message': 'Signature request not found'
                }
            
            # Check permissions
            if signature_request.requester_id != request.env.user and not request.env.user.has_group('rental_quotation.group_rental_quotation_manager'):
                return {
                    'status': 'error',
                    'message': 'Access denied'
                }
            
            signature_request.action_send_for_signature()
            
            return {
                'status': 'success',
                'message': 'Signature request sent successfully',
                'data': {
                    'id': signature_request.id,
                    'status': signature_request.status,
                    'signers_count': signature_request.total_signers
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in send_signature_request: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }