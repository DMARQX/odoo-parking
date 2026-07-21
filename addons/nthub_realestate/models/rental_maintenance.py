from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import ValidationError


class RentalMaintenanceRequest(models.Model):
    _name = 'rental.maintenance.request'
    _description = 'Rental Maintenance Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'request_date desc, id desc'

    # ==================== BASIC INFORMATION ====================
    name = fields.Char(
        string='Request Reference',
        required=True,
        tracking=True,
        readonly=True,
        copy=False,
        default='NEW'
    )

    request_date = fields.Datetime(
        string='Request Date',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True
    )

    # ==================== TENANT & LOCATION INFO ====================
    contract_id = fields.Many2one(
        'rental.contract',
        string='Rental Contract',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Tenant',
        related='contract_id.partner_id',
        store=True,
        readonly=True
    )

    x_unit_area = fields.Many2one(
        'sub.property',
        string='Unit / Area',
        related='contract_id.rs_project_unit',
        store=True,
        readonly=True
    )

    x_building_id = fields.Many2one(
        'rs.project',
        string='Building / Property',
        related='contract_id.rs_project',
        store=True,
        readonly=True
    )

    x_tenant_mobile = fields.Char(
        string='Contact Mobile',
        related='partner_id.mobile',
        readonly=True
    )

    x_tenant_email = fields.Char(
        string='Contact Email',
        related='partner_id.email',
        readonly=True
    )

    # ==================== REQUEST DETAILS ====================
    x_request_type = fields.Selection([
        ('electrical', 'Electrical'),
        ('mechanical', 'Mechanical'),
        ('low_current', 'Low Current'),
        ('civil', 'Civil'),
        ('general', 'General'),
        ('other', 'Other'),
    ], string='Request Type', required=True, tracking=True)

    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal', tracking=True)

    description = fields.Text(
        string='Description of Problem',
        required=True,
        tracking=True
    )

    # ==================== ATTACHMENTS & PHOTOS ====================
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'maintenance_request_attachments_rel',
        'request_id',
        'attachment_id',
        string='Attachments'
    )

    # ==================== JOB ORDER LINKAGE ====================
    x_job_order_id = fields.Many2one(
        'maintenance.job.order',
        string='Linked Job Order',
        ondelete='set null',
        readonly=True,
        copy=False
    )

    x_job_assigned_to = fields.Char(
        string='Job Assigned To',
        readonly=True
    )

    x_job_assigned_time = fields.Datetime(
        string='Job Assigned Time',
        readonly=True,
        copy=False
    )

    x_job_logged_by = fields.Many2one(
        'res.users',
        string='Job Logged By',
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True
    )

    # ==================== JOB ORDER TRACKING INFO (FR-7, FR-8) ====================
    x_job_assigned_by = fields.Many2one(
        'res.users',
        string='Job Assigned By',
        readonly=True,
        copy=False
    )

    approved_by_tenant_date = fields.Datetime(
        string='Tenant Approval Date',
        readonly=True,
        copy=False
    )

    # ==================== STATUS & WORKFLOW ====================
    x_status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('job_ordered', 'Job Ordered'),
        ('in_progress', 'In Progress'),
        ('pending_supervisor_approval', 'Pending Supervisor Approval'),
        ('pending_tenant_approval', 'Pending Tenant Approval'),
        ('approved_by_tenant', 'Approved by Tenant'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # ==================== CANCELLATION ====================
    cancellation_reason = fields.Text(
        string='Cancellation Reason',
        tracking=True
    )

    # ==================== TENANT APPROVAL/REJECTION ====================
    tenant_rejection_reason = fields.Text(
        string='Tenant Rejection Reason',
        tracking=True,
        help='Reason provided by tenant when rejecting the work completion'
    )

    # ==================== COMPANY ====================
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    # ==================== COMPUTED FIELDS ====================
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate sequence for name"""
        for vals in vals_list:
            if vals.get('name', 'NEW') == 'NEW':
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.request') or 'MR/000001'
        return super().create(vals_list)

    def action_submit(self):
        """Submit the maintenance request"""
        self.write({'x_status': 'submitted'})
        self.message_post(body=_('Request has been submitted for review.'))

    def action_under_review(self):
        """Move the maintenance request to under review status"""
        self.write({'x_status': 'under_review'})
        self.message_post(body=_('Request is now under review.'))

    def action_create_job_order(self):
        """Create a job order from this maintenance request"""
        self.ensure_one()
        if self.x_job_order_id:
            raise ValidationError(_('Job order already created for this request.'))

        job_order = self.env['maintenance.job.order'].create({
            'maintenance_request_id': self.id,
            'job_type': 'fault',
            'priority': self.priority,
            'job_description': self.description,
        })

        self.write({
            'x_job_order_id': job_order.id,
            'x_status': 'job_ordered',
            'x_job_assigned_time': fields.Datetime.now(),
        })
        self.message_post(body=_('Job order %s created.') % job_order.name)

    def action_view_job_order(self):
        """Open the related Job Order"""
        self.ensure_one()
        return {
            'name': _('Job Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.job.order',
            'view_mode': 'form',
            'res_id': self.x_job_order_id.id,
            'target': 'current',
        }

    def action_cancel(self):
        """Cancel the maintenance request"""
        self.ensure_one()
        if not self.cancellation_reason:
            raise ValidationError(_('Please provide a cancellation reason.'))
        self.write({'x_status': 'cancelled'})
        self.message_post(body=_('Request has been cancelled. Reason: %s') % self.cancellation_reason)

    def action_mark_completed(self):
        """Mark request as completed"""
        self.write({'x_status': 'completed'})
        self.message_post(body=_('Request marked as completed.'))

    def action_close(self):
        """Close the maintenance request"""
        self.write({'x_status': 'closed'})
        self.message_post(body=_('Request has been closed.'))

    def action_tenant_approve(self):
        """Tenant approves the completed work"""
        self.ensure_one()
        # Close maintenance request
        self.write({
            'x_status': 'closed'
        })
        # Close related job order if exists
        if self.x_job_order_id:
            self.x_job_order_id.write({
                'state': 'closed',
                'job_end_datetime': fields.Datetime.now()
            })
            self.x_job_order_id.message_post(body=_('Job approved and closed by tenant.'))
        
        self.message_post(body=_('Work approved by tenant. Request completed.'))
        return True

    def action_tenant_reject(self, rejection_reason):
        """Tenant rejects the completed work with reason"""
        self.ensure_one()
        if not rejection_reason:
            raise ValidationError(_('Please provide a rejection reason.'))
        
        # Update state back to previous and add rejection reason
        self.write({
            'x_status': 'pending_supervisor_approval',
            'tenant_rejection_reason': rejection_reason
        })
        
        # Update job order state if exists
        if self.x_job_order_id:
            self.x_job_order_id.write({
                'state': 'pending_supervisor_approval'
            })
            self.x_job_order_id.message_post(
                body=_('Work rejected by tenant. Reason: %s') % rejection_reason
            )
        
        self.message_post(body=_('Work rejected by tenant. Reason: %s') % rejection_reason)
        return True







class MaintenanceType(models.Model):
    _name = 'maintenance.type'
    _description = 'Maintenance Request Type'
    _order = 'name'

    name = fields.Char(string='Type', required=True, translate=True)
    active = fields.Boolean(default=True)


# ============================================================================
# MAINTENANCE JOB ORDER MODEL - Core execution workflow
# ============================================================================
class MaintenanceJobOrder(models.Model):
    """
    Main Job Order model for Saqifa maintenance execution.
    Linked from maintenance.request to track full lifecycle:
    Draft → Sent to Contractor → In Progress → Completed by Contractor →
    Pending Supervisor Approval → Pending Tenant Approval → Closed
    """
    _name = 'maintenance.job.order'
    _description = 'Maintenance Job Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc, id desc'

    # ========== A. HEADER INFORMATION ==========
    name = fields.Char(
        string='Job Order #',
        required=True,
        readonly=True,
        copy=False,
        default='NEW',
        tracking=True
    )

    date = fields.Date(
        string='Job Order Date',
        default=fields.Date.today,
        readonly=True,
        tracking=True
    )

    maintenance_request_id = fields.Many2one(
        'rental.maintenance.request',
        string='Linked Tenant Request',
        ondelete='cascade',
        tracking=True,
        help='Origin maintenance request from tenant'
    )

    x_unit_area = fields.Many2one(
        'sub.property',
        string='Unit / Area',
        related='maintenance_request_id.x_unit_area',
        store=True,
        readonly=True
    )

    ordered_by_id = fields.Many2one(
        'res.partner',
        string='Ordered By',
        related='maintenance_request_id.partner_id',
        store=True,
        readonly=True,
        help='Tenant who submitted the request'
    )

    ordered_mobile = fields.Char(
        string='Mobile',
        related='ordered_by_id.mobile',
        readonly=True
    )

    ordered_email = fields.Char(
        string='Email',
        related='ordered_by_id.email',
        readonly=True
    )

    job_logged_by = fields.Many2one(
        'res.users',
        string='Job Logged By',
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True
    )

    assigned_contractor_id = fields.Many2one(
        'res.partner',
        string='Assigned Contractor',
        tracking=True,
        domain="[('is_contractor', '=', True)]",
        help='Contractor assigned to execute this job'
    )

    job_assigned_datetime = fields.Datetime(
        string='Job Assigned Date/Time',
        readonly=True,
        copy=False
    )

    job_type = fields.Selection([
        ('new', 'New'),
        ('fault', 'Fault'),
        ('site_visit', 'Site Visit'),
        ('other', 'Other'),
    ], string='Type of Job', required=True, default='fault', tracking=True)

    job_type_other = fields.Char(
        string='Other Type Description',
        tracking=True
    )

    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal', tracking=True)

    x_company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent_to_contractor', 'Sent to Contractor'),
        ('in_progress', 'In Progress'),
        ('completed_by_contractor', 'Completed by Contractor'),
        ('pending_supervisor_approval', 'Supervisor Approve'),
        ('pending_tenant_approval', 'Tenant Approve'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    cancellation_reason = fields.Text(
        string='Cancellation Reason',
        tracking=True
    )

    # ========== PURCHASE ORDER TRACKING ==========
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'x_maintenance_job_id',
        string='Purchase Orders',
        readonly=True,
        help='Purchase orders created for this maintenance job'
    )

    purchase_order_count = fields.Integer(
        string='Purchase Order Count',
        compute='_compute_purchase_order_count',
        store=True,
        help='Number of purchase orders created'
    )

    has_purchase_orders = fields.Boolean(
        string='Has Purchase Orders',
        compute='_compute_has_purchase_orders',
        store=True,
        help='Indicates if purchase orders have been created'
    )

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        """Compute the number of purchase orders"""
        for record in self:
            record.purchase_order_count = len(record.purchase_order_ids)

    @api.depends('purchase_order_ids')
    def _compute_has_purchase_orders(self):
        """Compute if purchase orders exist"""
        for record in self:
            record.has_purchase_orders = bool(record.purchase_order_ids)

    # ========== STOCK PICKING TRACKING ==========
    stock_picking_ids = fields.One2many(
        'stock.picking',
        'x_job_order_id',
        string='Stock Pickings / التحويلات',
        readonly=True,
        help='Stock pickings/transfers created for material delivery'
    )

    stock_picking_count = fields.Integer(
        string='Stock Picking Count',
        compute='_compute_stock_picking_count',
        help='Number of stock pickings/transfers'
    )

    @api.depends('stock_picking_ids')
    def _compute_stock_picking_count(self):
        """Compute the number of stock pickings"""
        for record in self:
            record.stock_picking_count = len(record.stock_picking_ids)

    def action_view_stock_pickings(self):
        """Open list view of stock pickings related to this job order"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Transfers / تحويلات المواد'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('x_job_order_id', '=', self.id)],
            'context': {'default_x_job_order_id': self.id},
        }

    # ========== B. JOB DESCRIPTION & EXECUTION ==========
    job_reference = fields.Char(
        string='Job Reference',
        readonly=True,
        copy=False,
        help='Internal ticket/reference'
    )

    job_description = fields.Text(
        string='Job Description',
        tracking=True,
        help='Detailed work order'
    )

    technician_id = fields.Char(
        string='Technician Name',
        tracking=True,
        help='On contractor side'
    )

    corrective_action = fields.Text(
        string='Corrective Action',
        tracking=True,
        help='What was done by the contractor'
    )

    additional_resources = fields.Text(
        string='Additional Resources Needed',
        tracking=True,
        help='Manpower/equipment needed'
    )

    requested_material_text = fields.Text(
        string='Requested Material (Summary)',
        tracking=True,
        help='Free-text summary; detailed in Material Sheet'
    )

    # ========== C. CONTRACTOR SUPERVISOR & TENANT SIGN OFF ==========
    supervisor_remarks = fields.Text(
        string='Supervisor Remarks',
        tracking=True,
        help='After work completion'
    )

    supervisor_id = fields.Many2one(
        'res.partner',
        string='Supervisor',
        tracking=True,
        domain="[('is_contractor_supervisor', '=', True)]"
    )

    supervisor_signature = fields.Binary(
        string='Supervisor Signature',
        help='Digital signature'
    )

    supervisor_sign_datetime = fields.Datetime(
        string='Supervisor Sign Date/Time',
        readonly=True,
        copy=False
    )

    tenant_remarks = fields.Text(
        string='Tenant Remarks',
        tracking=True
    )

    tenant_manager_id = fields.Many2one(
        'res.partner',
        string='Tenant / Tenant Manager',
        domain="[('id', '=', ordered_by_id)]",
        tracking=True
    )

    tenant_signature = fields.Binary(
        string='Tenant Signature',
        help='Digital signature'
    )

    tenant_sign_datetime = fields.Datetime(
        string='Tenant Sign Date/Time',
        readonly=True,
        copy=False
    )

    # ========== D. JOB COMPLETION CONFIRMATION ==========
    job_start_datetime = fields.Datetime(
        string='Job Start Date/Time',
        tracking=True,
        help='When technician started'
    )

    job_end_datetime = fields.Datetime(
        string='Job Completion Date/Time',
        tracking=True,
        help='When technician completed'
    )

    manager_name = fields.Many2one(
        'res.users',
        string='Manager Name',
        tracking=True
    )

    manager_signature = fields.Binary(
        string='Manager Signature'
    )

    manager_sign_date = fields.Date(
        string='Manager Sign Date'
    )

    # ========== E. MATERIAL LINES (One2many) ==========
    requested_material_ids = fields.One2many(
        'maintenance.job.request.line',
        'job_order_id',
        string='Requested Materials'
    )
    
    # Alias for compatibility with views
    material_request_line_ids = fields.One2many(
        'maintenance.job.request.line',
        'job_order_id',
        string='Requested Materials'
    )

    issued_material_ids = fields.One2many(
        'maintenance.job.issue.line',
        'job_order_id',
        string='Issued Materials'
    )

    purchase_material_ids = fields.One2many(
        'maintenance.job.purchase.line',
        'job_order_id',
        string='Materials to Purchase'
    )

    # ========== ALIASES FOR BACKWARD COMPATIBILITY ==========
    material_issue_line_ids = fields.One2many(
        'maintenance.job.issue.line',
        'job_order_id',
        string='Issued Materials (Alias)'
    )

    material_purchase_line_ids = fields.One2many(
        'maintenance.job.purchase.line',
        'job_order_id',
        string='Materials to Purchase (Alias)'
    )

    # ========== ACTIONS / BUTTONS ==========
    def action_send_to_contractor(self):
        """Send job to contractor - Backend action"""
        self.ensure_one()
        if not self.assigned_contractor_id:
            raise ValidationError(_('Please assign a contractor before sending.'))
        
        self.write({
            'state': 'sent_to_contractor',
            'job_assigned_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_('Job order sent to contractor: %s') % self.assigned_contractor_id.name)

    def action_issue_materials(self):
        """Create stock picking for material issuance"""
        self.ensure_one()
        if not self.issued_material_ids:
            raise ValidationError(_('No materials to issue. Add materials to the issued list first.'))
        
        # Get default picking type for internal transfers
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.x_company_id.id)
        ], limit=1)
        
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)
            
        if not picking_type:
            raise ValidationError(_('No internal picking type found. Please configure warehouse operations.'))
        
        # Create stock picking
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'origin': self.name,
            'company_id': self.x_company_id.id,
            'x_job_order_id': self.id,  # Link picking to job order
        }
        picking = self.env['stock.picking'].create(picking_vals)
        
        # Create stock moves for each issued material
        for issue_line in self.issued_material_ids:
            if not issue_line.product_id:
                continue
                
            move_vals = {
                'name': f"{self.name}: {issue_line.product_id.name}",
                'product_id': issue_line.product_id.id,
                'product_uom_qty': issue_line.issue_qty,
                'product_uom': issue_line.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'company_id': self.x_company_id.id,
            }
            move = self.env['stock.move'].create(move_vals)
            issue_line.move_id = move.id
        
        # Confirm the picking
        picking.action_confirm()
        
        self.message_post(
            body=_('Stock picking created: %s') % picking.name,
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock Picking',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        """Cancel job order"""
        self.ensure_one()
        if self.state == 'closed':
            raise ValidationError(_('Cannot cancel a closed job order.'))
        if not self.cancellation_reason:
            raise ValidationError(_('Please provide a cancellation reason.'))
        
        self.write({'state': 'cancelled'})
        self.message_post(body=_('Job order cancelled. Reason: %s') % self.cancellation_reason)

    def action_purchase_approval_request(self):
        """
        NEW WORKFLOW: Create ONE vendor quote with ALL products
        Creates single quote record, user will attach multiple vendor PDFs
        """
        self.ensure_one()
        
        # Check if quote already exists for this job order
        existing_quote = self.env['maintenance.vendor.quote'].search([
            ('job_order_id', '=', self.id),
            ('state', 'not in', ['rejected', 'cancelled'])
        ], limit=1)
        
        if existing_quote:
            # Return action to view existing quote
            return {
                'type': 'ir.actions.act_window',
                'name': _('Existing Quote Request / طلب عرض أسعار موجود'),
                'res_model': 'maintenance.vendor.quote',
                'res_id': existing_quote.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        if not self.purchase_material_ids:
            raise ValidationError(_('No materials to purchase. Add items to purchase list first.\nلا توجد مواد للشراء. أضف عناصر لقائمة الشراء أولاً.'))
        
        # Validate that we have products with quantities
        valid_lines = self.purchase_material_ids.filtered(lambda l: l.product_id and l.quantity > 0)
        
        if not valid_lines:
            raise ValidationError(_('No valid purchase lines found. Please ensure products and quantities are filled.\nلم يتم العثور على خطوط شراء صالحة. تأكد من ملء المنتجات والكميات.'))
        
        # Create ONE vendor quote with ALL products (regardless of supplier)
        vendor_quote_obj = self.env['maintenance.vendor.quote']
        
        quote_vals = {
            'job_order_id': self.id,
            'delivery_days': 7,
            'payment_terms': 'Net 30',
            'notes': _('Materials required for Job Order: %s') % self.name,
        }
        
        vendor_quote = vendor_quote_obj.create(quote_vals)
        
        # Create quote lines from ALL purchase materials
        for line in valid_lines:
            quote_line_vals = {
                'quote_id': vendor_quote.id,
                'product_id': line.product_id.id,
                'description': line.product_id.name,
                'quantity': line.quantity,
                'unit_price': line.product_id.standard_price or 0.0,
            }
            self.env['maintenance.vendor.quote.line'].create(quote_line_vals)
            
            # Update purchase line notes
            line.write({
                'notes': _('Quote Request created: %s') % vendor_quote.name,
                'status': 'rfq_sent'
            })
        
        # Update job order message
        self.message_post(
            body=_('Quote Request %s created with %d products.<br/>'
                   'Next Steps:<br/>'
                   '1. Attach vendor quote PDFs<br/>'
                   '2. Send to owner for approval<br/>'
                   '3. Select winning vendor after approval') % (vendor_quote.name, len(valid_lines)),
            message_type='notification'
        )
        
        # Return action to view created quote
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quote Request / طلب عرض أسعار'),
            'res_model': 'maintenance.vendor.quote',
            'res_id': vendor_quote.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_tenant_approval(self):
        """Tenant approval of completed job"""
        self.ensure_one()
        if self.state != 'pending_supervisor_approval':
            raise ValidationError(_('Job order must be approved by supervisor first.'))
        
        self.write({
            'state': 'pending_tenant_approval',
            'tenant_sign_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_('Job order approved by tenant. Ready for final closure.'))

    def action_supervisor_approval(self):
        """Supervisor approval of completed work"""
        self.ensure_one()
        if self.state != 'completed_by_contractor':
            raise ValidationError(_('Job order must be completed by contractor first.'))
        
        self.write({
            'state': 'pending_supervisor_approval',
            'supervisor_sign_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_('Job order approved by supervisor. Waiting for tenant approval.'))

    def action_start_work(self):
        """Contractor starts work"""
        self.ensure_one()
        if self.state != 'sent_to_contractor':
            raise ValidationError(_('Job order is not assigned to contractor.'))
        
        self.write({
            'state': 'in_progress',
            'job_start_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_('Work started by contractor'))

    def action_mark_completed(self):
        """Mark work as completed by contractor"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise ValidationError(_('Job must be in progress to mark as completed.'))
        
        self.write({
            'state': 'completed_by_contractor',
            'job_end_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_('Work completed by contractor. Waiting for supervisor approval.'))
    
    def action_materials_received(self):
        """Mark materials as received and move to next state"""
        self.ensure_one()
        if not self.has_purchase_orders:
            raise ValidationError(_('No purchase orders found for this job order.'))
        
        # Check if all POs are confirmed/done
        pending_pos = self.purchase_order_ids.filtered(lambda po: po.state not in ['purchase', 'done'])
        if pending_pos:
            pending_names = ', '.join(pending_pos.mapped('name'))
            raise ValidationError(_('The following purchase orders are not confirmed yet: %s') % pending_names)
        
        # Update state to allow contractor to start work
        if self.state in ['draft', 'sent_to_contractor']:
            self.write({
                'state': 'sent_to_contractor' if self.state == 'draft' else 'in_progress',
            })
            self.message_post(body=_('Materials received from purchase orders. Ready to proceed with work.'))
        else:
            self.message_post(body=_('Materials confirmed as received from purchase orders.'))
    
    def action_confirm_purchase_orders(self):
        """Confirm all related purchase orders"""
        self.ensure_one()
        if not self.has_purchase_orders:
            raise ValidationError(_('No purchase orders found for this job order.'))
        
        # Confirm all related POs
        for po in self.purchase_order_ids.filtered(lambda p: p.state in ['draft', 'sent']):
            po.button_confirm()
        
        # Reception status will be computed automatically when purchase_line_id is set
        self.message_post(body=_('All purchase orders have been confirmed.'))
        
        # Return action to view purchase orders
        return self.action_view_purchase_orders()

    def action_close_job_order(self):
        """Close job order (final step after tenant approval)"""
        self.ensure_one()
        if self.state != 'pending_tenant_approval':
            raise ValidationError(_('Job order must be approved by tenant first.'))
        
        self.write({
            'state': 'closed',
            'manager_sign_date': fields.Date.today(),
        })
        self.message_post(body=_('Job order closed successfully'))

    def action_map_materials(self):
        """Open wizard to map contractor material requests to products"""
        self.ensure_one()
        
        # Create wizard record with context
        wizard = self.env['maintenance.material.mapping.wizard'].create({
            'job_order_id': self.id
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Map Materials to Products',
            'res_model': 'maintenance.material.mapping.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def create_issued_material_from_request(self, request_line, product, quantity):
        """Create issued material line from material request"""
        self.env['maintenance.job.issue.line'].create({
            'job_order_id': self.id,
            'request_line_id': request_line.id,
            'product_id': product.id,
            'issue_qty': quantity,
            'notes': f"Mapped from request: {request_line.description}",
        })
        # Reception status will be computed automatically when move_id is set
        # Update state to in_progress when materials are mapped
        if self.state != 'in_progress':
            self.write({'state': 'in_progress'})
        self.message_post(body=_('Materials mapped - Job in progress'))

    def create_purchase_material_from_request(self, request_line, product, quantity, supplier=None):
        """Create purchase material line from material request"""
        self.env['maintenance.job.purchase.line'].create({
            'job_order_id': self.id,
            'request_line_id': request_line.id,
            'product_id': product.id,
            'quantity': quantity,
            'supplier_id': supplier.id if supplier else False,
            'target_date': fields.Date.today(),
            'notes': f"Mapped from request: {request_line.description}",
        })
        # Reception status will be computed automatically when purchase_line_id is set
        # Update state to in_progress instead of closed
        if self.state != 'in_progress':
            self.write({'state': 'in_progress'})
        self.message_post(body=_('Materials mapped - Job in progress'))

    def action_supervisor_approval(self):
        """Supervisor approval of completed job"""
        self.ensure_one()
        if self.state != 'completed_by_contractor':
            raise ValidationError(_('Job must be completed by contractor first.'))
        
        self.write({
            'state': 'pending_supervisor_approval',
            'supervisor_sign_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_('Supervisor approval submitted'))

    def action_close_job_order(self):
        """Close job order - Saqifa manager action"""
        self.ensure_one()
        self.write({'state': 'closed'})
        self.message_post(body=_('Job order closed'))

    def action_view_purchase_orders(self):
        """Smart button action to view related purchase orders"""
        self.ensure_one()
        
        if not self.purchase_order_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('No purchase orders found for this job order.'),
                    'type': 'warning',
                }
            }
        
        if len(self.purchase_order_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Purchase Order',
                'res_model': 'purchase.order',
                'res_id': self.purchase_order_ids[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Purchase Orders',
                'res_model': 'purchase.order',
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.purchase_order_ids.ids)],
                'context': {'default_x_maintenance_job_id': self.id},
                'target': 'current',
            }

    # ========== CONTRACTOR PORTAL ACTIONS ==========
    def action_start_work(self):
        """Contractor starts work"""
        self.ensure_one()
        self.write({
            'state': 'in_progress',
            'job_start_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_('Work started by contractor'))

    def action_request_materials(self):
        """Contractor requests materials - opens form"""
        self.ensure_one()
        # TODO: Open wizard for material request input
        pass

    def action_mark_completed(self):
        """Contractor marks work as complete"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise ValidationError(_('Job must be in progress.'))
        
        self.write({
            'state': 'completed_by_contractor',
            'job_end_datetime': fields.Datetime.now(),
        })
        self.message_post(body=_('Work completed by contractor - pending approvals'))

    @api.model_create_multi
    def create(self, vals_list):
        """Generate job order sequence"""
        for vals in vals_list:
            if vals.get('name', 'NEW') == 'NEW':
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.job.order') or 'JO/000001'
        return super().create(vals_list)


# ============================================================================
# NOTE: Material line models (E1, E2, E3) are now defined in separate files:
# - maintenance_job_request_line.py (E1: Contractor Input)
# - maintenance_job_issue_line.py (E2: Issued Materials)
# - maintenance_job_purchase_line.py (E3: Purchase Materials)
# ============================================================================
