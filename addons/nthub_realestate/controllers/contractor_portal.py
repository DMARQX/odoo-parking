# -*- coding: utf-8 -*-
from functools import wraps
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, UserError


# =========================================================================
# 1. SECURITY DECORATOR
# =========================================================================
def contractor_only(f):
    """Decorator to ensure the logged-in user is a contractor."""
    @wraps(f)
    def wrap(self, *args, **kw):
        if request.env.user.share:
            partner = request.env.user.partner_id
            if not partner.supplier_rank > 0:  # Contractors are suppliers
                request.session.logout(keep_db=True)
                return request.render('website.403', {
                    'message': _('Access to this section is restricted to contractors.')
                })
        return f(self, *args, **kw)
    return wrap


class ContractorPortal(CustomerPortal):
    """Contractor Portal - Phase 4 Implementation"""

    def _prepare_home_portal_values(self, counters):
        """Adds counters for contractor jobs to the portal home page."""
        values = super()._prepare_home_portal_values(counters)
        partner_id = request.env.user.partner_id.id
        
        # Check if user is contractor (supplier)
        if not request.env.user.partner_id.supplier_rank > 0 and request.env.user.share:
            values['contractor_job_count'] = 0
            return values
        
        # Count jobs assigned to this contractor
        values['contractor_job_count'] = request.env['maintenance.job.order'].sudo().search_count([
            ('assigned_contractor_id', '=', partner_id)
        ])
        
        return values

    # =========================================================================
    # 2. CONTRACTOR PORTAL ROUTES
    # =========================================================================
    
    @http.route(['/my/contractor/jobs'], type='http', auth="user", website=True)
    @contractor_only
    def portal_contractor_jobs(self, sortby=None, filterby=None, **kw):
        """FR-5: Displays the list of jobs assigned to this contractor."""
        contractor = request.env.user.partner_id
        
        # Base domain
        domain = [('assigned_contractor_id', '=', contractor.id)]
        
        # Apply filters
        if filterby == 'pending':
            domain.append(('state', '=', 'sent_to_contractor'))
        elif filterby == 'in_progress':
            domain.append(('state', '=', 'in_progress'))
        elif filterby == 'completed':
            domain.append(('state', 'in', ['completed_by_contractor', 'pending_tenant_approval', 'pending_supervisor_approval', 'closed']))
        
        # Sort options
        sort_order = 'create_date desc'
        if sortby == 'date_asc':
            sort_order = 'create_date asc'
        elif sortby == 'priority':
            sort_order = 'priority desc, create_date desc'
        
        # Search jobs
        jobs = request.env['maintenance.job.order'].sudo().search(domain, order=sort_order)
        
        # Calculate statistics
        total_count = len(jobs)
        pending_count = request.env['maintenance.job.order'].sudo().search_count([
            ('assigned_contractor_id', '=', contractor.id),
            ('state', '=', 'sent_to_contractor')
        ])
        in_progress_count = request.env['maintenance.job.order'].sudo().search_count([
            ('assigned_contractor_id', '=', contractor.id),
            ('state', '=', 'in_progress')
        ])
        completed_count = request.env['maintenance.job.order'].sudo().search_count([
            ('assigned_contractor_id', '=', contractor.id),
            ('state', 'in', ['completed_by_contractor', 'pending_tenant_approval', 'pending_supervisor_approval', 'closed'])
        ])
        
        values = {
            'jobs': jobs,
            'page_name': 'contractor_jobs',
            'total_count': total_count,
            'pending_count': pending_count,
            'in_progress_count': in_progress_count,
            'completed_count': completed_count,
            'sortby': sortby or 'date_desc',
            'filterby': filterby or 'all',
        }
        return request.render("nthub_realestate.portal_contractor_jobs", values)

    @http.route(['/my/contractor/job/<int:job_id>'], type='http', auth="user", website=True)
    @contractor_only
    def portal_contractor_job_detail(self, job_id=None, **kw):
        """FR-5: Displays job detail page for contractor."""
        try:
            job = request.env['maintenance.job.order'].sudo().browse(job_id)
            if not job.exists() or job.assigned_contractor_id.id != request.env.user.partner_id.id:
                raise AccessError(_("Access Denied."))
        except (AccessError, ValueError):
            return request.redirect('/my/contractor/jobs')
        
        values = {
            'job': job,
            'page_name': 'contractor_job_detail',
            'maintenance_request': job.maintenance_request_id,
            'material_requests': job.material_request_ids,
            'material_issues': job.material_issue_ids,
            'material_purchases': job.material_purchase_ids,
        }
        return request.render("nthub_realestate.portal_contractor_job_detail", values)

    @http.route(['/my/contractor/job/<int:job_id>/start'], type='http', auth="user", website=True, methods=['POST'])
    @contractor_only
    def portal_contractor_start_job(self, job_id, **post):
        """FR-5: Contractor starts work on job."""
        try:
            job = request.env['maintenance.job.order'].sudo().browse(job_id)
            if not job.exists() or job.assigned_contractor_id.id != request.env.user.partner_id.id:
                raise AccessError(_("Access Denied."))
            
            if job.state != 'sent_to_contractor':
                raise UserError(_("Job cannot be started in current state."))
            
            # Start the job
            job.write({
                'state': 'in_progress',
                'work_start_datetime': fields.Datetime.now(),
            })
            job.message_post(
                body=_('Work started by contractor: %s') % request.env.user.partner_id.name,
                subject=_('Work Started')
            )
            
            return request.redirect('/my/contractor/job/%s?message=started' % job_id)
            
        except (AccessError, UserError) as e:
            return request.redirect('/my/contractor/job/%s?error=%s' % (job_id, str(e)))

    @http.route(['/my/contractor/job/<int:job_id>/request_materials'], type='http', auth="user", website=True, methods=['POST'])
    @contractor_only
    def portal_contractor_request_materials(self, job_id, **post):
        """FR-5: Contractor submits material request."""
        try:
            job = request.env['maintenance.job.order'].sudo().browse(job_id)
            if not job.exists() or job.assigned_contractor_id.id != request.env.user.partner_id.id:
                raise AccessError(_("Access Denied."))
            
            if job.state not in ['sent_to_contractor', 'in_progress']:
                raise UserError(_("Cannot request materials in current state."))
            
            # Get form data
            description = post.get('description_text', '').strip()
            qty = float(post.get('requested_qty', 1.0))
            material_type = post.get('type_of_material', 'general')
            priority = post.get('request_priority', 'routine')
            remark = post.get('remark', '').strip()
            
            if not description:
                raise UserError(_("Material description is required."))
            
            # Create material request line
            request.env['maintenance.job.request.line'].sudo().create({
                'job_order_id': job.id,
                'description_text': description,
                'requested_qty': qty,
                'type_of_material': material_type,
                'request_priority': priority,
                'remark': remark,
                'state': 'requested',
            })
            
            job.message_post(
                body=_('Material requested by contractor: %s (Qty: %s)') % (description, qty),
                subject=_('Material Request')
            )
            
            return request.redirect('/my/contractor/job/%s?message=material_requested' % job_id)
            
        except (AccessError, UserError) as e:
            return request.redirect('/my/contractor/job/%s?error=%s' % (job_id, str(e)))

    @http.route(['/my/contractor/job/<int:job_id>/complete'], type='http', auth="user", website=True, methods=['POST'])
    @contractor_only
    def portal_contractor_complete_job(self, job_id, **post):
        """FR-5: Contractor marks job as completed."""
        try:
            job = request.env['maintenance.job.order'].sudo().browse(job_id)
            if not job.exists() or job.assigned_contractor_id.id != request.env.user.partner_id.id:
                raise AccessError(_("Access Denied."))
            
            if job.state != 'in_progress':
                raise UserError(_("Job must be in progress to complete."))
            
            # Get corrective action
            corrective_action = post.get('corrective_action', '').strip()
            if not corrective_action:
                raise UserError(_("Corrective action is required to complete the job."))
            
            # Complete the job
            job.write({
                'state': 'completed_by_contractor',
                'work_end_datetime': fields.Datetime.now(),
                'corrective_action': corrective_action,
            })
            
            job.message_post(
                body=_('Job completed by contractor: %s\nCorrective Action: %s') % (
                    request.env.user.partner_id.name,
                    corrective_action
                ),
                subject=_('Work Completed')
            )
            
            return request.redirect('/my/contractor/job/%s?message=completed' % job_id)
            
        except (AccessError, UserError) as e:
            return request.redirect('/my/contractor/job/%s?error=%s' % (job_id, str(e)))

    @http.route(['/my/contractor/job/<int:job_id>/request_approval'], type='http', auth="user", website=True, methods=['POST'])
    @contractor_only
    def portal_contractor_request_approval(self, job_id, **post):
        """FR-5: Contractor requests supervisor approval after completion."""
        try:
            job = request.env['maintenance.job.order'].sudo().browse(job_id)
            if not job.exists() or job.assigned_contractor_id.id != request.env.user.partner_id.id:
                raise AccessError(_("Access Denied."))
            
            if job.state != 'completed_by_contractor':
                raise UserError(_("Job must be completed before requesting approval."))
            
            # Request approval
            job.write({
                'state': 'pending_supervisor_approval',
            })
            
            job.message_post(
                body=_('Supervisor approval requested by contractor: %s') % request.env.user.partner_id.name,
                subject=_('Approval Requested')
            )
            
            # TODO: Send notification email to supervisor
            
            return request.redirect('/my/contractor/job/%s?message=approval_requested' % job_id)
            
        except (AccessError, UserError) as e:
            return request.redirect('/my/contractor/job/%s?error=%s' % (job_id, str(e)))

    @http.route(['/my/contractor/job/<int:job_id>/cancel'], type='http', auth="user", website=True, methods=['POST'])
    @contractor_only
    def portal_contractor_cancel_job(self, job_id, **post):
        """FR-5: Contractor cancels job with reason."""
        try:
            job = request.env['maintenance.job.order'].sudo().browse(job_id)
            if not job.exists() or job.assigned_contractor_id.id != request.env.user.partner_id.id:
                raise AccessError(_("Access Denied."))
            
            if job.state not in ['sent_to_contractor', 'in_progress']:
                raise UserError(_("Job cannot be cancelled in current state."))
            
            # Get cancellation reason
            cancel_reason = post.get('cancel_reason', '').strip()
            if not cancel_reason:
                raise UserError(_("Cancellation reason is required."))
            
            # Cancel the job
            job.write({
                'state': 'cancelled',
            })
            
            job.message_post(
                body=_('Job cancelled by contractor: %s\nReason: %s') % (
                    request.env.user.partner_id.name,
                    cancel_reason
                ),
                subject=_('Job Cancelled')
            )
            
            return request.redirect('/my/contractor/jobs?message=cancelled')
            
        except (AccessError, UserError) as e:
            return request.redirect('/my/contractor/job/%s?error=%s' % (job_id, str(e)))
