from odoo import models, fields, api

class JobOrderForm(models.Model):
    _name = 'job.order.form'
    _description = 'Job Order Form'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ==================== A. HEADER INFORMATION ====================
    name = fields.Char(string="Job Order #", default="New", readonly=True, tracking=True)
    date = fields.Date(string="Job Order Date", default=fields.Date.today, tracking=True)
    maintenance_request_id = fields.Many2one('rental.maintenance.request', string="Linked Tenant Request", tracking=True)
    x_unit_area = fields.Many2one('sub.property', string="Unit/Area", tracking=True)
    ordered_by_id = fields.Many2one('res.partner', string="Ordered By", tracking=True)
    ordered_mobile = fields.Char(string="Mobile", related='ordered_by_id.mobile', readonly=True)
    ordered_email = fields.Char(string="E-mail", related='ordered_by_id.email', readonly=True)
    job_logged_by = fields.Many2one('res.users', string="Job Logged By", default=lambda self: self.env.user, tracking=True)
    assigned_contractor_id = fields.Many2one('res.partner', string="Job Assigned To (Company)", 
                                             domain=[('is_contractor', '=', True)], tracking=True)
    job_assigned_datetime = fields.Datetime(string="Job Assigned Time", tracking=True)
    job_type = fields.Selection([
        ('new', 'New'),
        ('fault', 'Fault'),
        ('site_visit', 'Site Visit'),
        ('other', 'Other')
    ], string="Type of Job", default='fault', tracking=True)
    job_type_other = fields.Char(string="Other Type Description")
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string="Job Priority", default='normal', tracking=True)
    project_id = fields.Many2one('rs.project', string="Project", required=True, tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent_to_contractor', 'Sent to Contractor'),
        ('in_progress', 'In Progress'),
        ('completed_by_contractor', 'Completed by Contractor'),
        ('pending_supervisor_approval', 'Supervisor Approve'),
        ('pending_tenant_approval', 'Tenant Approve'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='draft', tracking=True)
    cancellation_reason = fields.Text(string="Cancellation Reason")

    # ==================== B. JOB DESCRIPTION & EXECUTION ====================
    job_reference = fields.Char(string="Job Reference", tracking=True)
    job_description = fields.Text(string="Job Description", tracking=True)
    technician_id = fields.Char(string="Technician Name")
    corrective_action = fields.Text(string="Corrective Action")
    additional_resources = fields.Text(string="Additional Resources Needed")
    requested_material_text = fields.Text(string="Requested Material (Summary)")

    # ==================== C. CONTRACTOR SUPERVISOR & TENANT SIGN OFF ====================
    supervisor_remarks = fields.Text(string="Supervisor's Remarks")
    supervisor_id = fields.Char(string="Supervisor")
    supervisor_signature = fields.Binary(string="Supervisor's Signature")
    supervisor_sign_datetime = fields.Datetime(string="Supervisor Sign Date/Time")
    
    tenant_remarks = fields.Text(string="Tenant's Manager Remarks")
    tenant_manager_id = fields.Many2one('res.partner', string="Tenant / Tenant's Manager")
    tenant_signature = fields.Binary(string="Tenant's Signature")
    tenant_sign_datetime = fields.Datetime(string="Tenant Sign Date/Time")

    # ==================== D. JOB COMPLETION CONFIRMATION ====================
    job_start_datetime = fields.Datetime(string="Job Start Date/Time", tracking=True)
    job_end_datetime = fields.Datetime(string="Job Completion Date/Time", tracking=True)
    manager_name = fields.Many2one('res.users', string="Manager Name")
    manager_signature = fields.Binary(string="Manager Signature")
    manager_sign_date = fields.Date(string="Manager Sign Date")

    # ==================== E. MATERIAL LINES (O2M Relations) ====================
    # E-1: Contractor Input - Requested Materials
    material_request_line_ids = fields.One2many('maintenance.job.request.line', 'job_order_id', 
                                                string="Requested Materials")
    
    # E-2: Issued Materials from Stock
    material_issue_line_ids = fields.One2many('maintenance.job.issue.line', 'job_order_id', 
                                              string="Issued Materials from Stock")
    
    # E-3: Materials to Purchase
    material_purchase_line_ids = fields.One2many('maintenance.job.purchase.line', 'job_order_id', 
                                                 string="Materials to Purchase")

    # ==================== LEGACY FIELDS (keeping for compatibility) ====================
    location = fields.Char(string="Location")
    contact_number = fields.Char(string="Contact Number")
    requested_by = fields.Char(string="Requested By")
    work_description = fields.Text(string="Work Description")
    assigned_to = fields.Char(string="Assigned To")
    start_datetime = fields.Datetime(string="Request Start Date/Time")
    completion_datetime = fields.Datetime(string="Request Completion Date/Time")
    request_start = fields.Datetime(string="Request Start Date/Time")
    request_completion = fields.Datetime(string="Request Completion Date/Time")
    store_incharge = fields.Char(string="Store Incharge")
    store_incharge_signature = fields.Binary(string="Store Incharge Signature")
    comments = fields.Text(string="Store Incharge Comments")
    record_file = fields.Binary(string="Record File")
    record_file_name = fields.Char(string="File Name")
    record_name = fields.Char(string="Record File Name")
    record_signature = fields.Binary(string="Signature")
    requester_signature = fields.Binary(string="Requester Signature")
    store_signature = fields.Binary(string="Store Incharge Signature")
    store_name = fields.Char(string="Store Incharge Name")
    
    # Old O2M fields (keeping for backward compatibility)
    requested_material_ids = fields.One2many('job.order.material.requested', 'form_id', string="Requested Materials (Old)")
    to_purchase_ids = fields.One2many('job.order.material.purchase', 'form_id', string="To Purchase Materials (Old)")
    used_status_ids = fields.One2many('job.order.material.used', 'form_id', string="Used Material Status")
    data_status_ids = fields.One2many('job.order.material.data', 'form_id', string="Data Material Status")
    stock_update_ids = fields.One2many('job.order.material.stock', 'form_id', string="Stock Updated Status")
    purchase_material_ids = fields.One2many('job.order.material.purchase', 'form_id', string="Materials for Purchase (Old)")
    used_material_ids = fields.One2many('job.order.material.used', 'form_id', string="Used Materials (Old)")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('job.order.form') or 'New'
        return super().create(vals)

    # ==================== BUTTON ACTIONS ====================
    def action_send_to_contractor(self):
        """Send job order to contractor"""
        self.ensure_one()
        self.write({
            'state': 'sent_to_contractor',
            'job_assigned_datetime': fields.Datetime.now(),
            'job_start_datetime': fields.Datetime.now()
        })
        self.message_post(body="Job Order sent to contractor")

    def action_start_work(self):
        """Contractor starts work"""
        self.ensure_one()
        self.write({
            'state': 'in_progress',
            'job_start_datetime': fields.Datetime.now()
        })
        self.message_post(body="Work started by contractor")

    def action_mark_completed(self):
        """Contractor marks work as completed"""
        self.ensure_one()
        self.write({
            'state': 'completed_by_contractor',
            'job_end_datetime': fields.Datetime.now()
        })
        self.message_post(body="Work completed by contractor")

    def action_supervisor_approval(self):
        """Contractor supervisor approves work"""
        self.ensure_one()
        self.write({
            'state': 'pending_tenant_approval',
            'supervisor_sign_datetime': fields.Datetime.now()
        })
        self.message_post(body="Supervisor approved work completion")

    def action_tenant_approval(self):
        """Tenant approves completed work"""
        self.ensure_one()
        self.write({
            'state': 'closed',
            'tenant_sign_datetime': fields.Datetime.now()
        })
        self.message_post(body="Tenant approved work completion")

    def action_approve_job_order(self):
        """Saqifa admin can directly close job order"""
        self.ensure_one()
        self.write({'state': 'closed'})
        self.message_post(body="Job Order closed by admin")

    def action_close_job_order(self):
        """Close job order"""
        self.ensure_one()
        self.write({'state': 'closed'})
        self.message_post(body="Job Order closed")

    def action_cancel(self):
        """Cancel job order"""
        self.ensure_one()
        self.write({'state': 'cancelled'})
        self.message_post(body="Job Order cancelled")

    def action_issue_materials(self):
        """Issue materials from stock - creates stock picking"""
        self.ensure_one()
        # TODO: Implement stock picking creation
        self.message_post(body="Materials issued from stock")

    def action_request_materials(self):
        """Contractor requests materials"""
        self.ensure_one()
        self.message_post(body="Material request submitted")

    def purchase_approval_request(self):
        """Create approval request for material purchase"""
        self.ensure_one()
        # TODO: Create approval.request record
        self.message_post(body="Purchase approval request created")
        
        # Return action to refresh the current record
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'job.order.form',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class JobOrderMaterialRequested(models.Model):
    _name = 'job.order.material.requested'
    _description = 'Requested Material'

    form_id = fields.Many2one('job.order.form', string="Job Order")
    description = fields.Text(string="Description")
    model = fields.Char(string="Model")
    tracking = fields.Char(string="Tracking")
    asset_number = fields.Char(string="Asset #")
    serial_number = fields.Char(string="Serial #")
    quantity = fields.Float(string="Qty")
    is_new = fields.Selection([('new', 'New'), ('used', 'Used')], string="New/Used")
    type_of_material = fields.Selection([
        ('new', 'New'),
        ('used', 'Used'),
        ('consumable', 'Consumable')
    ], string="Type of Material")
    request_priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string="Priority", default='normal')
    notes = fields.Text(string="Notes")
    issue_person = fields.Char(string="Issue Material Person Name")
    signature = fields.Binary(string="Signature")
    date = fields.Date(string="Date")
    qty = fields.Float(string="Qty")
    issue_person_name = fields.Char(string="Issue Material Person Name")


class JobOrderMaterialPurchase(models.Model):
    _name = 'job.order.material.purchase'
    _description = 'To Purchase Material'

    form_id = fields.Many2one('job.order.form', string="Form")
    product_id = fields.Many2one('product.product', string="Product")
    description = fields.Char()
    model = fields.Char()
    qty = fields.Float()
    quotation_1 = fields.Char()
    quotation_2 = fields.Char()
    quotation_3 = fields.Char()
    approval_date = fields.Date()
    material_receiving = fields.Char()
    receiving_status = fields.Selection([
        ('received', 'Received'),
        ('not_received', 'Not Received'),
        ('partial', 'Partially Received')
    ], string="Material Receiving Status")
class JobOrderMaterialUsed(models.Model):
    _name = 'job.order.material.used'
    _description = 'Used Material Status'

    form_id = fields.Many2one('job.order.form', string="Job Order")
    form_id = fields.Many2one('job.order.form', string="Job Order")
    description = fields.Char(string="Description")
    model = fields.Char(string="Model")
    tracking = fields.Char(string="Tracking")
    asset_number = fields.Char(string="Asset #")  # ✅ أضفنا الحقل هنا
    serial_number = fields.Char(string="Serial #")
    qty = fields.Float(string="Qty")
    status = fields.Selection([
        ('scrap', 'Scrap'),
        ('repairable', 'Repairable')
    ], string="Status")
    date = fields.Date(string="Date")
    remarks = fields.Text(string="Remarks")
class JobOrderMaterialData(models.Model):
    _name = 'job.order.material.data'
    _description = 'Data Sending / Receiving Status'

    form_id = fields.Many2one('job.order.form', string="Form")
    description = fields.Char()
    model = fields.Char()
    tracking = fields.Char()
    asset_no = fields.Char()
    qty = fields.Float()
    data_sending = fields.Date()
    data_receiving = fields.Date()
    remarks = fields.Text()
class JobOrderMaterialStock(models.Model):
    _name = 'job.order.material.stock'
    _description = 'Stock Updated Status in Store'

    form_id = fields.Many2one('job.order.form', string="Job Order")
    description = fields.Char(string="Description")
    model = fields.Char(string="Model")
    tracking = fields.Char(string="Tracking")
    asset_number = fields.Char(string="Asset #")
    qty = fields.Float(string="Qty")
    data_sending = fields.Datetime(string="Data Sending")  # ✅ الحقل المطلوب
    data_receiving = fields.Datetime(string="Data Receiving")  # لو في حقل آخر مرتبط
    remarks = fields.Text(string="Remarks")