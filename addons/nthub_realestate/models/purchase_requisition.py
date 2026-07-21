from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
from datetime import datetime, timedelta


class MaintenancePurchaseRequisition(models.Model):
    """Purchase Requisition for Job Order Materials"""
    _name = 'maintenance.purchase.requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Maintenance Material Purchase Requisition'
    _rec_name = 'name'
    _order = 'create_date DESC'

    name = fields.Char(
        string='Requisition Number',
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('maint.purchase.req'),
        tracking=True
    )

    # References
    job_order_id = fields.Many2one(
        'maintenance.job.order',
        string='Job Order',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    project_id = fields.Many2one(
        'rs.project',
        string='Project',
        tracking=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        tracking=True,
        help='Main product (optional - can have multiple products in vendor quotes)'
    )

    # Financial
    estimated_qty = fields.Float(
        string='Estimated Quantity',
        default=1.0,
        help='Estimated total quantity (optional - detailed quantities in vendor quotes)'
    )

    estimated_unit_price = fields.Monetary(
        string='Estimated Unit Price',
        currency_field='company_currency_id',
        help='Estimated price (optional - actual prices from vendor quotes)'
    )

    estimated_amount = fields.Monetary(
        string='Estimated Total Amount',
        compute='_compute_estimated_amount',
        store=True,
        currency_field='company_currency_id'
    )

    actual_amount = fields.Monetary(
        string='Actual Amount (PO)',
        readonly=True,
        currency_field='company_currency_id'
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
        readonly=True
    )

    # Status
    state = fields.Selection(
        [('draft', 'Draft'),
         ('submitted', 'Submitted for Review'),
         ('level1_approved', 'Level 1 Approved'),
         ('level2_approved', 'Level 2 Approved'),
         ('level3_approved', 'Level 3 Approved'),
         ('po_created', 'PO Created'),
         ('received', 'Materials Received'),
         ('invoiced', 'Invoiced'),
         ('closed', 'Closed'),
         ('rejected', 'Rejected'),
         ('cancelled', 'Cancelled')],
        string='State',
        default='draft',
        tracking=True
    )

    # Approvals
    required_approval_levels = fields.Integer(
        string='Required Approval Levels',
        compute='_compute_required_approvals',
        store=True
    )

    approver1_id = fields.Many2one(
        'res.users',
        string='Level 1 Approver',
        compute='_compute_approvers',
        store=True,
        help='Usually Supervisor'
    )

    approver1_date = fields.Datetime(
        string='Level 1 Approval Date',
        readonly=True
    )

    approver2_id = fields.Many2one(
        'res.users',
        string='Level 2 Approver',
        readonly=True,
        help='Usually Manager'
    )

    approver2_date = fields.Datetime(
        string='Level 2 Approval Date',
        readonly=True
    )

    approver3_id = fields.Many2one(
        'res.users',
        string='Level 3 Approver',
        readonly=True,
        help='Usually Finance Lead'
    )

    approver3_date = fields.Datetime(
        string='Level 3 Approval Date',
        readonly=True
    )

    rejection_count = fields.Integer(
        default=0,
        readonly=True,
        tracking=True
    )

    last_rejection_reason = fields.Text(
        readonly=True,
        tracking=True
    )

    # Vendor
    vendor_id = fields.Many2one(
        'res.partner',
        string='Selected Vendor',
        domain="[('supplier_rank', '>', 0)]",
        tracking=True
    )

    vendor_quote_ids = fields.One2many(
        'maintenance.vendor.quote',
        'requisition_id',
        string='Vendor Quotes'
    )

    vendor_quote_count = fields.Integer(
        string='Number of Quotes',
        compute='_compute_vendor_quote_count',
        store=True
    )

    # Dates
    created_date = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True
    )

    request_date = fields.Date(
        string='Request Date',
        default=fields.Date.today,
        readonly=True
    )

    requested_delivery_date = fields.Date(
        string='Requested Delivery Date',
        default=lambda self: (datetime.now() + timedelta(days=7)).date(),
        help='Target delivery date (default: 7 days from now)'
    )

    # Links
    po_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        readonly=True
    )

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.depends('estimated_qty', 'estimated_unit_price')
    def _compute_estimated_amount(self):
        for record in self:
            record.estimated_amount = record.estimated_qty * (record.estimated_unit_price or 0)

    @api.depends('vendor_quote_ids')
    def _compute_vendor_quote_count(self):
        """Count vendor quotes"""
        for rec in self:
            rec.vendor_quote_count = len(rec.vendor_quote_ids)

    @api.depends('estimated_amount')
    def _compute_required_approvals(self):
        """Calculate required approval levels based on amount"""
        for record in self:
            amount = record.estimated_amount
            if amount <= 500:
                record.required_approval_levels = 1
            elif amount <= 2000:
                record.required_approval_levels = 2
            elif amount <= 10000:
                record.required_approval_levels = 3
            else:
                record.required_approval_levels = 4

    @api.depends('job_order_id')
    def _compute_approvers(self):
        """Assign default approvers"""
        for record in self:
            # Get supervisor from job order or use current user's manager
            supervisor = record.job_order_id.job_logged_by or self.env.user
            record.approver1_id = supervisor.id

    def action_submit(self):
        """Submit requisition for approval"""
        if self.state != 'draft':
            raise UserError('Only draft requisitions can be submitted')

        self.state = 'submitted'
        self.message_post(
            body='Requisition submitted for approval',
            message_type='notification'
        )
        self._notify_approver('approver1_id')

    def action_approve_level1(self):
        """Level 1 approval"""
        if self.env.user.id != self.approver1_id.id and not self.env.user.has_group('base.group_system'):
            raise AccessError('Only assigned approver can approve')

        if self.required_approval_levels > 1:
            self.state = 'level1_approved'
            self.approver1_date = fields.Datetime.now()
            self.message_post(
                body=f'Level 1 approved by {self.env.user.name}',
                message_type='notification'
            )
            self._notify_approver('approver2_id')
        else:
            self.state = 'level3_approved'
            self.approver1_date = fields.Datetime.now()
            self._create_purchase_order()

    def action_approve_level2(self):
        """Level 2 approval"""
        if self.env.user.id != self.approver2_id.id and not self.env.user.has_group('base.group_system'):
            raise AccessError('Only assigned approver can approve')

        if self.required_approval_levels > 2:
            self.state = 'level2_approved'
            self.approver2_date = fields.Datetime.now()
            self.message_post(
                body=f'Level 2 approved by {self.env.user.name}',
                message_type='notification'
            )
            self._notify_approver('approver3_id')
        else:
            self.state = 'level3_approved'
            self.approver2_date = fields.Datetime.now()
            self._create_purchase_order()

    def action_approve_level3(self):
        """Level 3 approval - final"""
        if self.env.user.id != self.approver3_id.id and not self.env.user.has_group('base.group_system'):
            raise AccessError('Only assigned approver can approve')

        self.state = 'level3_approved'
        self.approver3_date = fields.Datetime.now()
        self.message_post(
            body=f'Final approval by {self.env.user.name}',
            message_type='notification'
        )
        self._create_purchase_order()

    def action_reject(self, reason):
        """Reject requisition"""
        self.rejection_count += 1
        self.last_rejection_reason = reason
        self.state = 'rejected'
        self.message_post(
            body=f'Rejected by {self.env.user.name}: {reason}',
            message_type='notification'
        )

    def _create_purchase_order(self):
        """Create purchase order from approved requisition"""
        if not self.vendor_id:
            raise UserError('Please select a vendor before creating PO')

        po_line = self.env['purchase.order.line'].create({
            'product_id': self.product_id.id,
            'product_qty': self.estimated_qty,
            'product_uom': self.product_id.uom_po_id.id,
            'price_unit': self.estimated_unit_price,
        })

        po = self.env['purchase.order'].create({
            'partner_id': self.vendor_id.id,
            'order_line': [(6, 0, [po_line.id])],
            'date_planned': self.requested_delivery_date,
            'notes': f'Job Order: {self.job_order_id.name}\nRequisition: {self.name}',
        })

        po.button_confirm()

        self.po_id = po.id
        self.state = 'po_created'
        self.actual_amount = po.amount_total

        self.message_post(
            body=f'Purchase order created: {po.name}',
            message_type='notification'
        )

    def action_cancel(self):
        """Cancel requisition"""
        self.state = 'cancelled'
        self.message_post(
            body='Requisition cancelled',
            message_type='notification'
        )

    def _notify_approver(self, approver_field):
        """Send approval notification email"""
        approver = getattr(self, approver_field)
        if approver and approver.email:
            template = self.env.ref(
                'nthub_realestate.email_purchase_approval',
                raise_if_not_found=False
            )
            if template:
                template.send_mail(self.id, force_send=True)


class MaintenanceVendorQuote(models.Model):
    """Vendor Price Quotes for Material Purchases - Enhanced with Multi-Vendor PDF Comparison"""
    _name = 'maintenance.vendor.quote'
    _description = 'Vendor Price Quote'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date DESC'

    name = fields.Char(
        string='Quote Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'New',
        tracking=True
    )

    requisition_id = fields.Many2one(
        'maintenance.purchase.requisition',
        string='Purchase Requisition',
        required=False,
        ondelete='cascade',
        tracking=True
    )
    
    job_order_id = fields.Many2one(
        'maintenance.job.order',
        string='Job Order',
        ondelete='cascade',
        tracking=True,
        help='Direct link to job order'
    )
    
    project_id = fields.Many2one(
        'rs.project',
        string='Project',
        compute='_compute_project_id',
        store=True,
        readonly=True
    )

    # REMOVED: vendor_id is no longer required at quote level
    # Vendor selection happens AFTER owner approval
    selected_vendor_id = fields.Many2one(
        'res.partner',
        string='Selected Vendor',
        domain="[('supplier_rank', '>', 0)]",
        tracking=True,
        help='Vendor selected after owner approval'
    )
    
    # Quote Lines - ALL products regardless of vendor
    quote_line_ids = fields.One2many(
        'maintenance.vendor.quote.line',
        'quote_id',
        string='Materials List'
    )
    
    # NEW: Vendor Quote Attachments - Multiple PDFs from different vendors
    vendor_attachment_ids = fields.One2many(
        'maintenance.vendor.quote.attachment',
        'quote_id',
        string='Vendor Quotes (PDFs)'
    )
    
    vendor_attachment_count = fields.Integer(
        string='Vendor Quotes Count',
        compute='_compute_vendor_attachment_count'
    )

    total_amount = fields.Monetary(
        string='Estimated Amount',
        compute='_compute_total_amount',
        store=True,
        currency_field='company_currency_id',
        tracking=True
    )
    
    # Selected vendor's final amount (after approval)
    final_amount = fields.Monetary(
        string='Final Amount',
        currency_field='company_currency_id',
        tracking=True,
        help='Final amount from selected vendor quote'
    )

    delivery_days = fields.Integer(
        string='Delivery Days',
        default=5,
        tracking=True
    )

    payment_terms = fields.Char(
        string='Payment Terms',
        default='Net 30',
        tracking=True
    )
    
    warranty_period = fields.Char(
        string='Warranty Period',
        tracking=True
    )
    
    # Legacy Attachments (kept for compatibility)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'vendor_quote_attachment_rel',
        'quote_id',
        'attachment_id',
        string='Other Documents'
    )
    
    # Enhanced Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_owner_approval', 'Pending Owner Approval'),
        ('owner_approved', 'Owner Approved'),
        ('vendor_selected', 'Vendor Selected'),
        ('po_created', 'PO Created'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)
    
    # For backward compatibility - computed from selected_vendor_id
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        related='selected_vendor_id',
        store=True,
        readonly=True
    )

    is_selected = fields.Boolean(
        string='Selected by Owner',
        default=False,
        tracking=True
    )
    
    # Dates
    quote_date = fields.Date(
        string='Quote Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )
    
    validity_date = fields.Date(
        string='Valid Until',
        tracking=True
    )
    
    approval_date = fields.Date(
        string='Approval Date',
        readonly=True
    )
    
    sent_to_owner_date = fields.Datetime(
        string='Sent to Owner Date',
        readonly=True
    )

    notes = fields.Text(string='Internal Notes')
    vendor_notes = fields.Text(string='Vendor Notes')
    owner_notes = fields.Text(string='Owner Notes', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason', readonly=True)

    company_currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_company_currency_id',
        store=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    # Owner info for portal access
    owner_partner_id = fields.Many2one(
        'res.partner',
        string='Property Owner',
        compute='_compute_owner_partner_id',
        store=True
    )
    
    @api.depends('vendor_attachment_ids')
    def _compute_vendor_attachment_count(self):
        for record in self:
            record.vendor_attachment_count = len(record.vendor_attachment_ids)
    
    @api.depends('project_id', 'project_id.partner_id')
    def _compute_owner_partner_id(self):
        """Get owner from project"""
        for quote in self:
            if quote.project_id and quote.project_id.partner_id:
                quote.owner_partner_id = quote.project_id.partner_id
            else:
                quote.owner_partner_id = False
    
    @api.depends('requisition_id', 'job_order_id', 'requisition_id.project_id', 'job_order_id.maintenance_request_id', 'job_order_id.x_unit_area')
    def _compute_project_id(self):
        """Compute project from requisition or job order"""
        for quote in self:
            if quote.requisition_id and quote.requisition_id.project_id:
                quote.project_id = quote.requisition_id.project_id
            elif quote.job_order_id:
                # Get project from job order
                job_order = quote.job_order_id
                if job_order.maintenance_request_id and job_order.maintenance_request_id.contract_id:
                    quote.project_id = job_order.maintenance_request_id.contract_id.rs_project
                elif job_order.x_unit_area:
                    quote.project_id = job_order.x_unit_area.rs_project
                else:
                    quote.project_id = False
            else:
                quote.project_id = False
    
    @api.depends('requisition_id', 'requisition_id.company_currency_id')
    def _compute_company_currency_id(self):
        """Compute currency from requisition or company"""
        for quote in self:
            if quote.requisition_id and quote.requisition_id.company_currency_id:
                quote.company_currency_id = quote.requisition_id.company_currency_id
            else:
                quote.company_currency_id = quote.env.company.currency_id
    
    # Created Purchase Order
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        readonly=True
    )
    
    # Approval tracking
    approved_by_owner_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        tracking=True
    )
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('vendor.quote') or 'New'
        return super(MaintenanceVendorQuote, self).create(vals)
    
    @api.depends('quote_line_ids.subtotal')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.quote_line_ids.mapped('subtotal'))
    
    # ==================== NEW WORKFLOW ACTIONS ====================
    
    def action_send_to_owner(self):
        """Send quote to owner for approval - NEW WORKFLOW"""
        for record in self:
            if not record.quote_line_ids:
                raise UserError(_('Please add at least one material line before sending to owner.'))
            if not record.vendor_attachment_ids:
                raise UserError(_('Please attach at least one vendor quote PDF before sending to owner.'))
            
            record.write({
                'state': 'pending_owner_approval',
                'sent_to_owner_date': fields.Datetime.now()
            })
            # Send notification to owner
            record._send_owner_notification()
            
            record.message_post(
                body=_('Quote sent to owner for approval. Attached vendor quotes: %s') % 
                     ', '.join(record.vendor_attachment_ids.mapped('vendor_id.name')),
                message_type='notification'
            )
    
    def action_owner_approve(self):
        """Owner approves - called from portal or backend"""
        for record in self:
            if record.state != 'pending_owner_approval':
                raise UserError(_('Only quotes pending owner approval can be approved.'))
            
            record.write({
                'state': 'owner_approved',
                'approval_date': fields.Date.today(),
                'approved_by_owner_id': record.env.user.id,
            })
            
            record.message_post(
                body=_('Owner approved the quote. Please select the vendor to proceed.'),
                message_type='notification'
            )
    
    def action_owner_reject(self, rejection_reason=''):
        """Owner rejects the quote"""
        for record in self:
            record.write({
                'state': 'rejected',
                'rejection_reason': rejection_reason or _('Rejected by owner')
            })
            record.message_post(
                body=_('Quote rejected by owner. Reason: %s') % (rejection_reason or 'Not specified'),
                message_type='notification'
            )
    
    def action_select_vendor(self):
        """Select vendor after owner approval - opens wizard with only owner-approved vendors"""
        self.ensure_one()
        if self.state != 'owner_approved':
            raise UserError(_('Owner must approve the quote before selecting a vendor.'))
        
        # Filter only owner-approved vendor attachments
        approved_attachments = self.vendor_attachment_ids.filtered(lambda a: a.is_owner_approved)
        
        if not approved_attachments:
            # If no specific approvals, show all (backward compatibility)
            approved_attachments = self.vendor_attachment_ids
        
        # Pre-create product assignment lines for multiple vendor mode
        assignment_vals = []
        for line in self.quote_line_ids:
            if line.product_id:
                assignment_vals.append((0, 0, {
                    'quote_line_id': line.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity or 1.0,
                    'unit_price': line.unit_price or 0.0,
                }))
        
        # If no quote lines, check if there's a default product we can use
        if not assignment_vals:
            # Try to get products from job order material requests
            if self.job_order_id and self.job_order_id.purchase_material_ids:
                for mat in self.job_order_id.purchase_material_ids:
                    if mat.product_id:
                        assignment_vals.append((0, 0, {
                            'product_id': mat.product_id.id,
                            'quantity': mat.qty or 1.0,
                            'unit_price': mat.product_id.standard_price or 0.0,
                        }))
        
        # Return action to open vendor selection wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Vendor - Owner Approved Quotes Only'),
            'res_model': 'vendor.quote.select.vendor.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_quote_id': self.id,
                'default_vendor_attachment_ids': [(6, 0, approved_attachments.ids)],
                'default_product_assignment_ids': assignment_vals,
            }
        }
    
    def action_confirm_vendor_selection(self, vendor_id, final_amount=0):
        """Confirm vendor selection and create PO"""
        self.ensure_one()
        if not vendor_id:
            raise UserError(_('Please select a vendor.'))
        
        self.write({
            'selected_vendor_id': vendor_id,
            'final_amount': final_amount,
            'state': 'vendor_selected',
        })
        
        # Create Purchase Order
        po = self._create_purchase_order()
        
        self.write({'state': 'po_created'})
        
        self.message_post(
            body=_('Vendor %s selected. Purchase Order %s created.') % 
                 (self.selected_vendor_id.name, po.name),
            message_type='notification'
        )
        
        return po
    
    # ==================== LEGACY ACTIONS (kept for compatibility) ====================
    
    def action_submit_to_owner(self):
        """Legacy: Submit quote to owner for approval"""
        return self.action_send_to_owner()
    
    def action_approve_by_owner(self, owner_notes=''):
        """Legacy: Owner approves this quote"""
        self.write({'owner_notes': owner_notes})
        return self.action_owner_approve()
    
    def action_reject(self, rejection_reason=''):
        """Owner rejects this quote"""
        return self.action_owner_reject(rejection_reason)

    def action_select_quote(self):
        """Legacy: Select this quote as the vendor"""
        return self.action_select_vendor()
    
    def _create_purchase_order(self):
        """Create Purchase Order from approved quote with selected vendor"""
        self.ensure_one()
        
        if not self.selected_vendor_id:
            raise UserError(_('Please select a vendor before creating purchase order.'))
        
        po_vals = {
            'partner_id': self.selected_vendor_id.id,
            'origin': f"{self.name}" + (f" - {self.job_order_id.name}" if self.job_order_id else ""),
            'date_order': fields.Datetime.now(),
            'currency_id': self.company_currency_id.id,
            'notes': self.notes,
            'x_maintenance_job_id': self.job_order_id.id if self.job_order_id else False,
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.name,
                'product_qty': line.quantity,
                'product_uom': line.product_id.uom_po_id.id,
                'price_unit': line.unit_price or line.product_id.standard_price,
                'date_planned': fields.Datetime.now(),
            }) for line in self.quote_line_ids]
        }
        
        po = self.env['purchase.order'].create(po_vals)
        self.write({'purchase_order_id': po.id})
        
        # Update job order if linked
        if self.job_order_id:
            # Link purchase lines to job order purchase material lines
            for po_line in po.order_line:
                matching_mat_line = self.job_order_id.purchase_material_ids.filtered(
                    lambda l: l.product_id.id == po_line.product_id.id
                )
                if matching_mat_line:
                    matching_mat_line[0].write({
                        'purchase_line_id': po_line.id,
                        'status': 'po_confirmed'
                    })
        
        if self.requisition_id:
            self.requisition_id.write({'po_id': po.id})
        
        return po
    
    def _create_purchase_order_for_vendor(self, vendor_id, amount=0, attachment=None):
        """Create Purchase Order for a specific vendor with ALL products (legacy)"""
        self.ensure_one()
        
        vendor = self.env['res.partner'].browse(vendor_id)
        if not vendor.exists():
            raise UserError(_('Invalid vendor.'))
        
        po_vals = {
            'partner_id': vendor_id,
            'origin': f"{self.name}" + (f" - {self.job_order_id.name}" if self.job_order_id else ""),
            'date_order': fields.Datetime.now(),
            'currency_id': self.company_currency_id.id,
            'notes': f"Vendor Quote: {attachment.display_name if attachment else ''}\nAmount: {amount}",
            'x_maintenance_job_id': self.job_order_id.id if self.job_order_id else False,
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.name,
                'product_qty': line.quantity,
                'product_uom': line.product_id.uom_po_id.id,
                'price_unit': line.unit_price or line.product_id.standard_price,
                'date_planned': fields.Datetime.now(),
            }) for line in self.quote_line_ids]
        }
        
        po = self.env['purchase.order'].create(po_vals)
        
        # Link attachment to PO
        if attachment:
            attachment.write({'purchase_order_id': po.id})
        
        return po
    
    def _create_purchase_order_for_vendor_with_items(self, vendor_id, attachment=None, items=None):
        """Create Purchase Order for a specific vendor with SPECIFIC products from items dict"""
        self.ensure_one()
        
        vendor = self.env['res.partner'].browse(vendor_id)
        if not vendor.exists():
            raise UserError(_('Invalid vendor.'))
        
        if not items:
            raise UserError(_('No products specified for this vendor.'))
        
        # Build PO lines from items dict
        po_lines = []
        for item in items:
            product = item['product']
            if not product:
                continue
            
            # Get product name
            product_name = product.display_name or product.name or 'Product'
            
            # Get UOM
            uom_id = product.uom_po_id.id if product.uom_po_id else product.uom_id.id
            
            # Get price and quantity from item
            price = item.get('unit_price', 0) or product.standard_price or 0.0
            qty = item.get('quantity', 1) or 1.0
            
            po_lines.append((0, 0, {
                'product_id': product.id,
                'name': product_name,
                'product_qty': qty,
                'product_uom': uom_id,
                'price_unit': price,
                'date_planned': fields.Datetime.now(),
            }))
        
        if not po_lines:
            raise UserError(_('No valid products found for this vendor.'))
        
        po_vals = {
            'partner_id': vendor_id,
            'origin': f"{self.name}" + (f" - {self.job_order_id.name}" if self.job_order_id else ""),
            'date_order': fields.Datetime.now(),
            'currency_id': self.company_currency_id.id,
            'notes': f"Vendor Quote: {attachment.display_name if attachment else ''}\nProducts assigned to this vendor",
            'x_maintenance_job_id': self.job_order_id.id if self.job_order_id else False,
            'order_line': po_lines,
        }
        
        po = self.env['purchase.order'].create(po_vals)
        
        # Link attachment to PO
        if attachment:
            attachment.write({'purchase_order_id': po.id})
        
        return po
        
        return po

    def action_view_purchase_requisition(self):
        """Open the linked purchase requisition"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Requisition',
            'res_model': 'maintenance.purchase.requisition',
            'res_id': self.requisition_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_purchase_order(self):
        """Open the linked purchase order"""
        self.ensure_one()
        if not self.purchase_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Order',
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _send_owner_notification(self):
        """Send notification to owner about new quote"""
        self.ensure_one()
        template = self.env.ref('nthub_realestate.email_template_vendor_quote_submitted', raise_if_not_found=False)
        if template and self.project_id and self.project_id.partner_id:
            template.send_mail(self.id, force_send=True)
    
    def _send_approval_notification(self):
        """Send notification to vendor about quote approval"""
        self.ensure_one()
        template = self.env.ref('nthub_realestate.email_template_vendor_quote_approved', raise_if_not_found=False)
        if template and self.vendor_id:
            template.send_mail(self.id, force_send=True)
    
    def _send_rejection_notification(self):
        """Send notification to vendor about quote rejection"""
        self.ensure_one()
        template = self.env.ref('nthub_realestate.email_template_vendor_quote_rejected', raise_if_not_found=False)
        if template and self.vendor_id:
            template.send_mail(self.id, force_send=True)
    
    def get_portal_url(self):
        """Get portal URL for this quote"""
        self.ensure_one()
        return f'/my/purchase_requisition/{self.requisition_id.id}/quotes'


class MaintenanceVendorQuoteLine(models.Model):
    """Lines for Vendor Quotes"""
    _name = 'maintenance.vendor.quote.line'
    _description = 'Vendor Quote Line'
    _order = 'quote_id, sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    
    quote_id = fields.Many2one(
        'maintenance.vendor.quote',
        string='Quote',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )
    
    description = fields.Text(string='Description')
    
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
        digits='Product Unit of Measure'
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        readonly=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='quote_id.company_currency_id',
        store=True,
        readonly=True
    )
    
    unit_price = fields.Monetary(
        string='Unit Price',
        required=True,
        currency_field='currency_id'
    )
    
    subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id'
    )
    
    notes = fields.Text(string='Notes')
    
    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.unit_price = self.product_id.standard_price


class MaintenanceVendorQuoteAttachment(models.Model):
    """
    Vendor Quote Attachments - Each line represents a quote PDF from a different vendor
    عروض أسعار الموردين - كل سطر يمثل عرض PDF من مورد مختلف
    """
    _name = 'maintenance.vendor.quote.attachment'
    _description = 'Vendor Quote Attachment / مرفق عرض سعر المورد'
    _rec_name = 'display_name'
    _order = 'quote_amount ASC'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    quote_id = fields.Many2one(
        'maintenance.vendor.quote',
        string='Price Quote Request / طلب عرض الأسعار',
        required=True,
        ondelete='cascade'
    )
    
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor / المورد',
        required=True,
        domain="[('supplier_rank', '>', 0)]"
    )
    
    # Direct file upload - Binary field instead of Many2one to ir.attachment
    quote_file = fields.Binary(
        string='Quote PDF / ملف العرض',
        attachment=True,
        help='Upload vendor quote PDF file directly'
    )
    
    quote_filename = fields.Char(
        string='File Name / اسم الملف'
    )
    
    # Keep attachment_id for backward compatibility and portal access
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Attachment Record',
        compute='_compute_attachment_id',
        store=True
    )
    
    attachment_url = fields.Char(
        string='Download URL',
        compute='_compute_attachment_url'
    )
    
    quote_amount = fields.Monetary(
        string='Quote Amount / مبلغ العرض',
        currency_field='currency_id',
        help='Total amount quoted by vendor'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='quote_id.company_currency_id',
        store=True,
        readonly=True
    )
    
    delivery_days = fields.Integer(
        string='Delivery Days / أيام التسليم'
    )
    
    payment_terms = fields.Char(
        string='Payment Terms / شروط الدفع'
    )
    
    warranty_period = fields.Char(
        string='Warranty / الضمان'
    )
    
    notes = fields.Text(
        string='Notes / ملاحظات'
    )
    
    is_owner_approved = fields.Boolean(
        string='Owner Approved / موافقة المالك',
        default=False,
        help='This vendor quote was approved by the owner'
    )
    
    is_selected = fields.Boolean(
        string='Selected / مختار',
        default=False,
        help='This vendor was selected after owner approval'
    )
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order / أمر الشراء',
        readonly=True,
        help='The purchase order created for this vendor'
    )

    @api.depends('vendor_id', 'quote_amount', 'currency_id')
    def _compute_display_name(self):
        for record in self:
            if record.vendor_id:
                amount_str = f"{record.quote_amount:,.2f}" if record.quote_amount else "0.00"
                currency = record.currency_id.symbol if record.currency_id else 'SAR'
                record.display_name = f"{record.vendor_id.name} - {amount_str} {currency}"
            else:
                record.display_name = "New Vendor Quote"
    
    @api.depends('quote_file')
    def _compute_attachment_id(self):
        """Find the ir.attachment created for the binary field"""
        for record in self:
            if record.quote_file and record.id:
                attachment = self.env['ir.attachment'].sudo().search([
                    ('res_model', '=', 'maintenance.vendor.quote.attachment'),
                    ('res_id', '=', record.id),
                    ('res_field', '=', 'quote_file')
                ], limit=1)
                record.attachment_id = attachment.id if attachment else False
            else:
                record.attachment_id = False
    
    @api.depends('attachment_id')
    def _compute_attachment_url(self):
        for record in self:
            if record.attachment_id:
                record.attachment_url = f'/web/content/{record.attachment_id.id}?download=true'
            else:
                record.attachment_url = False


class VendorQuoteSelectVendorWizard(models.TransientModel):
    """Wizard for selecting vendor(s) after owner approval - supports multiple vendors with product assignment"""
    _name = 'vendor.quote.select.vendor.wizard'
    _description = 'Select Vendor Wizard / معالج اختيار المورد'

    quote_id = fields.Many2one(
        'maintenance.vendor.quote',
        string='Quote',
        required=True
    )
    
    selection_mode = fields.Selection([
        ('single', 'Single Vendor / مورد واحد'),
        ('multiple', 'Multiple Vendors / موردين متعددين'),
    ], string='Selection Mode / نوع الاختيار', default='single', required=True)
    
    vendor_count = fields.Integer(
        string='Vendor Count',
        compute='_compute_vendor_count'
    )
    
    @api.depends('vendor_attachment_ids')
    def _compute_vendor_count(self):
        for record in self:
            record.vendor_count = len(record.vendor_attachment_ids)
    
    vendor_attachment_ids = fields.Many2many(
        'maintenance.vendor.quote.attachment',
        'wizard_vendor_attach_rel',
        'wizard_id',
        'attachment_id',
        string='Available Vendor Quotes / عروض الموردين المتاحة',
        readonly=True
    )
    
    # For single vendor selection
    selected_attachment_id = fields.Many2one(
        'maintenance.vendor.quote.attachment',
        string='Selected Vendor Quote / عرض المورد المختار',
        domain="[('id', 'in', vendor_attachment_ids)]"
    )
    
    # For multiple vendor selection with product assignment
    product_assignment_ids = fields.One2many(
        'vendor.quote.product.assignment.wizard',
        'wizard_id',
        string='Product Assignments / تخصيص المنتجات'
    )
    
    final_amount = fields.Monetary(
        string='Final Amount / المبلغ النهائي',
        compute='_compute_final_amount',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='quote_id.company_currency_id'
    )
    
    @api.depends('selection_mode', 'selected_attachment_id', 'product_assignment_ids.subtotal')
    def _compute_final_amount(self):
        for record in self:
            if record.selection_mode == 'single' and record.selected_attachment_id:
                record.final_amount = record.selected_attachment_id.quote_amount
            elif record.selection_mode == 'multiple' and record.product_assignment_ids:
                record.final_amount = sum(record.product_assignment_ids.mapped('subtotal'))
            else:
                record.final_amount = 0
    
    def action_confirm(self):
        """Confirm vendor selection - single or multiple with product assignment"""
        self.ensure_one()
        
        if self.selection_mode == 'single':
            if not self.selected_attachment_id:
                raise UserError(_('Please select a vendor quote.'))
            
            # Mark selected attachment
            self.selected_attachment_id.write({'is_selected': True})
            
            # Create PO with selected vendor
            po = self.quote_id.action_confirm_vendor_selection(
                vendor_id=self.selected_attachment_id.vendor_id.id,
                final_amount=self.selected_attachment_id.quote_amount
            )
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Purchase Order'),
                'res_model': 'purchase.order',
                'res_id': po.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            # Multiple vendors selection with product assignment
            if not self.product_assignment_ids:
                raise UserError(_('No products to assign.'))
            
            # Check all products have vendor assigned and get product from quote_line if needed
            valid_assignments = []
            for assignment in self.product_assignment_ids:
                if not assignment.vendor_attachment_id:
                    raise UserError(_('Please assign vendors to all products.'))
                
                # Get product - try product_id first, then quote_line_id
                product = assignment.product_id
                if not product and assignment.quote_line_id:
                    product = assignment.quote_line_id.product_id
                
                if product:
                    valid_assignments.append({
                        'assignment': assignment,
                        'product': product,
                        'quantity': assignment.quantity or 1.0,
                        'unit_price': assignment.unit_price or product.standard_price or 0.0,
                        'vendor_attachment': assignment.vendor_attachment_id,
                    })
            
            if not valid_assignments:
                raise UserError(_('No valid products found.'))
            
            # Group products by vendor
            vendor_products = {}
            for item in valid_assignments:
                vendor_attach = item['vendor_attachment']
                if vendor_attach.id not in vendor_products:
                    vendor_products[vendor_attach.id] = {
                        'attachment': vendor_attach,
                        'items': []
                    }
                vendor_products[vendor_attach.id]['items'].append(item)
            
            # Mark selected attachments
            selected_attachments = self.env['maintenance.vendor.quote.attachment']
            for item in valid_assignments:
                selected_attachments |= item['vendor_attachment']
            selected_attachments.write({'is_selected': True})
            
            # Create PO for each vendor with their assigned products
            pos = self.env['purchase.order']
            for vendor_data in vendor_products.values():
                attachment = vendor_data['attachment']
                items = vendor_data['items']
                
                po = self.quote_id._create_purchase_order_for_vendor_with_items(
                    vendor_id=attachment.vendor_id.id,
                    attachment=attachment,
                    items=items
                )
                pos |= po
            
            # Update quote
            vendor_names = ', '.join(selected_attachments.mapped('vendor_id.name'))
            self.quote_id.write({
                'state': 'po_created',
                'final_amount': self.final_amount,
                'notes': (self.quote_id.notes or '') + f'\n\nMultiple vendors selected: {vendor_names}'
            })
            
            self.quote_id.message_post(
                body=_('Multiple vendors selected: %s. %d Purchase Orders created.') % 
                     (vendor_names, len(pos)),
                message_type='notification'
            )
            
            # Return list view of created POs
            return {
                'type': 'ir.actions.act_window',
                'name': _('Purchase Orders'),
                'res_model': 'purchase.order',
                'domain': [('id', 'in', pos.ids)],
                'view_mode': 'list,form',
                'target': 'current',
            }


class VendorQuoteProductAssignmentWizard(models.TransientModel):
    """Wizard line for assigning products to specific vendors"""
    _name = 'vendor.quote.product.assignment.wizard'
    _description = 'Product Assignment Wizard Line / سطر تخصيص المنتج'
    
    wizard_id = fields.Many2one(
        'vendor.quote.select.vendor.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    quote_line_id = fields.Many2one(
        'maintenance.vendor.quote.line',
        string='Quote Line'
    )
    
    # Store product_id directly (not related) to preserve it
    product_id = fields.Many2one(
        'product.product',
        string='Product / المنتج'
    )
    
    # Computed display name for product
    product_display = fields.Char(
        string='Product Name',
        compute='_compute_product_display',
        store=True
    )
    
    quantity = fields.Float(
        string='Quantity / الكمية',
        default=1.0,
        digits='Product Unit of Measure'
    )
    
    unit_price = fields.Monetary(
        string='Unit Price / سعر الوحدة',
        currency_field='currency_id'
    )
    
    subtotal = fields.Monetary(
        string='Subtotal / المجموع',
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id'
    )
    
    @api.depends('product_id')
    def _compute_product_display(self):
        for line in self:
            line.product_display = line.product_id.display_name if line.product_id else ''
    
    currency_id = fields.Many2one(
        'res.currency',
        related='wizard_id.currency_id'
    )
    
    # Available vendors from wizard
    available_vendor_ids = fields.Many2many(
        'maintenance.vendor.quote.attachment',
        related='wizard_id.vendor_attachment_ids',
        string='Available Vendors'
    )
    
    vendor_attachment_id = fields.Many2one(
        'maintenance.vendor.quote.attachment',
        string='Vendor / المورد',
        domain="[('id', 'in', available_vendor_ids)]"
    )
    
    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price

