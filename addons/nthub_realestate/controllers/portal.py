from functools import wraps
import base64
from odoo import http, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError


# =========================================================================
# 1. SECURITY DECORATOR
# =========================================================================
def tenant_only(f):
    """Decorator to ensure the logged-in user is a tenant."""

    @wraps(f)
    def wrap(self, *args, **kw):
        if request.env.user.share:
            partner = request.env.user.partner_id
            if not partner.is_tenant:
                request.session.logout(keep_db=True)
                return request.render('website.403')
        return f(self, *args, **kw)

    return wrap


class RentalPortal(CustomerPortal):
    """Extends the Customer Portal to manage Rental Contracts."""

    def _prepare_home_portal_values(self, counters):
        """Adds counters for contracts and maintenance to the portal home page."""
        values = super()._prepare_home_portal_values(counters)
        partner_id = request.env.user.partner_id.id
        if not request.env.user.partner_id.is_tenant and request.env.user.share:
            values['rental_count'] = 0
            values['maintenance_count'] = 0
            return values
        values['rental_count'] = request.env['rental.contract'].sudo().search_count([('partner_id', '=', partner_id)])
        values['maintenance_count'] = request.env['rental.maintenance.request'].sudo().search_count([
            ('partner_id', '=', partner_id)
        ])
        return values

    # =========================================================================
    # 2. PORTAL ROUTES
    # =========================================================================
    @http.route(['/my/rental_contracts'], type='http', auth="user", website=True)
    @tenant_only
    def portal_my_rental_contracts(self, **kw):
        """Displays the list of rental contracts."""
        partner = request.env.user.partner_id
        contracts = request.env['rental.contract'].sudo().search([('partner_id', '=', partner.id)])
        values = {
            'contracts': contracts, 'page_name': 'rental_contract',
            'total_count': len(contracts),
            'active_count': sum(1 for c in contracts if c.state == 'confirmed'),
            'draft_count': sum(1 for c in contracts if c.state == 'draft'),
            'expired_count': sum(1 for c in contracts if c.date_to and c.date_to < fields.Date.today()),
        }
        return request.render("nthub_realestate.portal_my_rental_contracts", values)

    @http.route(['/my/rental_contract/<int:contract_id>'], type='http', auth="user", website=True)
    @tenant_only
    def portal_view_rental_contract(self, contract_id=None, **kw):
        """Displays the contract detail page AND the maintenance form."""
        try:
            contract = request.env['rental.contract'].sudo().browse(contract_id)
            if not contract.exists() or contract.partner_id.id != request.env.user.partner_id.id:
                raise AccessError("Access Denied.")
        except (AccessError, ValueError):
            return request.redirect('/my/rental_contracts')

        values = {
            'contract': contract,
            'installments': contract.rental_line_ids,
            'maintenance_requests': contract.maintenance_request_ids,
            'company_currency': contract.company_id.currency_id,
            'page_name': 'rental_contract',
        }
        return request.render("nthub_realestate.portal_rental_contract_view", values)

    # This is the route that handles the form submission. Note the URL.
    @http.route(['/my/rental_contract/<int:contract_id>/maintenance_request'], type='http', auth="user", website=True,
                methods=['POST'])
    @tenant_only
    def portal_create_maintenance_request(self, contract_id, **post):
        """Handles the creation of a maintenance request."""
        try:
            contract = request.env['rental.contract'].browse(contract_id)
            if not contract.exists() or contract.partner_id.id != request.env.user.partner_id.id:
                raise AccessError("Access Denied.")
        except (AccessError, ValueError):
            return request.redirect('/my/rental_contracts')

        if post.get('name') and post.get('description') and post.get('x_request_type'):
            # Create maintenance request
            maintenance_vals = {
                'name': post.get('name'),
                'description': post.get('description'),
                'x_request_type': post.get('x_request_type'),
                'priority': post.get('priority', 'normal'),
                'contract_id': contract.id,
                'x_status': 'submitted',  # Auto-submit from portal
            }
            
            new_request = request.env['rental.maintenance.request'].sudo().create(maintenance_vals)
            
            # Handle file attachments
            if request.httprequest.files:
                Attachments = request.env['ir.attachment'].sudo()
                for file_name, file_data in request.httprequest.files.items():
                    file = file_data.read()
                    if file:
                        Attachments.create({
                            'name': file_data.filename,
                            'datas': base64.b64encode(file),
                            'res_model': 'rental.maintenance.request',
                            'res_id': new_request.id,
                            'type': 'binary',
                        })
            
            return request.redirect(f'/my/rental_contract/{contract.id}?message=success')

        return request.redirect(f'/my/rental_contract/{contract_id}?error=missing_fields')

    @http.route(['/my/maintenance_requests'], type='http', auth="user", website=True)
    @tenant_only
    def portal_my_maintenance_requests(self, **kw):
        """Displays all maintenance requests for the tenant."""
        partner = request.env.user.partner_id
        maintenance_requests = request.env['rental.maintenance.request'].sudo().search([
            ('partner_id', '=', partner.id)
        ], order='create_date desc')
        
        values = {
            'maintenance_requests': maintenance_requests,
            'page_name': 'maintenance_requests',
            'total_count': len(maintenance_requests),
            'new_count': sum(1 for r in maintenance_requests if r.x_status == 'draft'),
            'in_progress_count': sum(1 for r in maintenance_requests if r.x_status == 'in_progress'),
            'done_count': sum(1 for r in maintenance_requests if r.x_status == 'closed'),
        }
        return request.render("nthub_realestate.portal_my_maintenance_requests", values)

    @http.route(['/my/maintenance_request/<int:request_id>'], type='http', auth="user", website=True)
    def portal_view_maintenance_request(self, request_id, **kw):
        """Displays the details of a single maintenance request."""
        try:
            maintenance_request_obj = request.env['rental.maintenance.request'].sudo().browse(request_id)
            if not maintenance_request_obj.exists() or maintenance_request_obj.contract_id.partner_id.id != request.env.user.partner_id.id:
                raise AccessError("Access Denied.")
        except (AccessError, ValueError):
            return request.redirect('/my/rental_contracts')

        # Get related job order and materials
        job_order = request.env['maintenance.job.order'].sudo().search([
            ('maintenance_request_id', '=', maintenance_request_obj.id)
        ], limit=1)
        
        materials_needed = []
        if job_order:
            # Get materials from job order lines (E-1: Contractor Input - Requested Materials)
            if hasattr(job_order, 'material_request_line_ids') and job_order.material_request_line_ids:
                for line in job_order.material_request_line_ids:
                    materials_needed.append({
                        'product': None,  # maintenance.job.request.line has no product_id field
                        'quantity': line.quantity if hasattr(line, 'quantity') else 0,
                        'description': line.description or '',
                        'is_available': line.type_of_material == 'stock' if hasattr(line, 'type_of_material') else False,
                        'reception_status': line.reception_status if hasattr(line, 'reception_status') else 'pending'
                    })
            elif hasattr(job_order, 'requested_material_ids') and job_order.requested_material_ids:
                for line in job_order.requested_material_ids:
                    materials_needed.append({
                        'product': None,  # No product field in this model
                        'quantity': line.quantity,
                        'description': line.description or '',
                        'is_available': line.type_of_material == 'stock',
                        'reception_status': line.reception_status if hasattr(line, 'reception_status') else 'pending'
                    })
        
        return request.render("nthub_realestate.portal_maintenance_request_view", {
            'maintenance_request_obj': maintenance_request_obj,
            'job_order': job_order,
            'materials_needed': materials_needed,
            'page_name': 'rental_contract'
        })
    
    @http.route(['/my/maintenance_request/<int:request_id>/tenant_action'], type='http', auth="user", website=True, methods=['POST'])
    @tenant_only
    def portal_tenant_maintenance_action(self, request_id, **post):
        """Handle tenant approval/rejection of maintenance request."""
        try:
            maintenance_request_obj = request.env['rental.maintenance.request'].sudo().browse(request_id)
            if not maintenance_request_obj.exists() or maintenance_request_obj.contract_id.partner_id.id != request.env.user.partner_id.id:
                raise AccessError("Access Denied.")
        except (AccessError, ValueError):
            return request.redirect('/my/rental_contracts')

        action = post.get('action')
        rejection_reason = post.get('rejection_reason', '').strip()
        
        if action == 'approve':
            # Use the new action_tenant_approve method
            maintenance_request_obj.action_tenant_approve()
            message = "Maintenance request approved successfully! Job order has been closed."
            
        elif action == 'reject':
            # Reject and send back to supervisor using new method
            if not rejection_reason:
                return request.redirect(f'/my/maintenance_request/{request_id}?error=rejection_reason_required')
            
            maintenance_request_obj.action_tenant_reject(rejection_reason)
            message = "Maintenance request rejected and sent back for review."
        
        return request.redirect(f'/my/maintenance_request/{request_id}?message={message}')

    @http.route(['/my/maintenance_request/<int:request_id>/supervisor_approve'], type='http', auth="user", website=True, methods=['POST'])
    @tenant_only
    def portal_tenant_supervisor_approve(self, request_id, **post):
        """Tenant approves supervisor approval - move to pending_tenant_approval."""
        try:
            maintenance_request_obj = request.env['rental.maintenance.request'].sudo().browse(request_id)
            if not maintenance_request_obj.exists() or maintenance_request_obj.contract_id.partner_id.id != request.env.user.partner_id.id:
                raise AccessError("Access Denied.")
        except (AccessError, ValueError):
            return request.redirect('/my/rental_contracts')
        
        # Get related job order
        job_order = request.env['maintenance.job.order'].sudo().search([
            ('maintenance_request_id', '=', maintenance_request_obj.id)
        ], limit=1)
        
        if job_order and job_order.state == 'pending_supervisor_approval':
            # Move to pending_tenant_approval
            job_order.write({'state': 'pending_tenant_approval'})
            maintenance_request_obj.write({'x_status': 'pending_tenant_approval'})
            message = "تمت الموافقة بنجاح! تم نقل الطلب إلى مرحلة موافقة المستأجر"
        else:
            message = "لا يمكن الموافقة على هذا الطلب في الوقت الحالي"
        
        return request.redirect(f'/my/maintenance_request/{request_id}?message={message}')

    @http.route(['/my/maintenance_request/<int:request_id>/supervisor_reject'], type='http', auth="user", website=True, methods=['POST'])
    @tenant_only
    def portal_tenant_supervisor_reject(self, request_id, **post):
        """Tenant rejects supervisor approval - write rejection reason."""
        try:
            maintenance_request_obj = request.env['rental.maintenance.request'].sudo().browse(request_id)
            if not maintenance_request_obj.exists() or maintenance_request_obj.contract_id.partner_id.id != request.env.user.partner_id.id:
                raise AccessError("Access Denied.")
        except (AccessError, ValueError):
            return request.redirect('/my/rental_contracts')
        
        rejection_reason = post.get('rejection_reason', '').strip()
        
        if not rejection_reason:
            return request.redirect(f'/my/maintenance_request/{request_id}?error=يرجى كتابة سبب الرفض')
        
        # Get related job order
        job_order = request.env['maintenance.job.order'].sudo().search([
            ('maintenance_request_id', '=', maintenance_request_obj.id)
        ], limit=1)
        
        if job_order and job_order.state == 'pending_supervisor_approval':
            # Move back to in_progress or completed_by_contractor
            job_order.write({
                'state': 'in_progress',
                'tenant_rejection_reason': rejection_reason
            })
            maintenance_request_obj.write({'x_status': 'in_progress'})
            
            # Post message to chatter
            job_order.message_post(
                body=f"تم رفض الموافقة من قبل المستأجر. السبب: {rejection_reason}",
                message_type='comment'
            )
            
            message = "تم رفض الطلب وإرجاعه للمراجعة"
        else:
            message = "لا يمكن رفض هذا الطلب في الوقت الحالي"
        
        return request.redirect(f'/my/maintenance_request/{request_id}?message={message}')

# =========================================================================
# 5. VENDOR QUOTES PORTAL (OLD - DISABLED)
# NOTE: New vendor quotes workflow moved to owner_portal.py
# The routes below are kept commented for reference only
# =========================================================================
# from odoo.addons.portal.controllers.portal import pager as portal_pager
# 
# class VendorQuotePortal(http.Controller):
#     """DEPRECATED - Use owner_portal.py instead for vendor quote routes."""
#     pass