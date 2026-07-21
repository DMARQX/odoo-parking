# Phase 4-6 Detailed Analysis & Implementation Guide
## Stock Integration, Purchase Approval & Job Completion

---

## 🎯 Overview

These three phases form the critical path for completing the core maintenance workflow. Together, they enable:
- Stock management from warehouse to job site
- Purchase requisition and approval
- Job completion and tenant handover

---

## PHASE 4: Stock Integration - DETAILED ANALYSIS

### 📋 Current State
- Material requests created in `maintenance.job.material.request`
- State: draft → approved → issued → received
- No integration with Odoo stock module
- Manual material tracking

### 🎯 Target State
- Automatic stock picking creation
- Warehouse location management
- Serial/lot number tracking
- Real-time stock level updates
- Contractor receipt confirmation

### 📊 Data Model

```
Stock Picking Flow:
┌─────────────────────────────────────────────────────┐
│ Maintenance Job Material Request (Approved)         │
└────────────┬────────────────────────────────────────┘
             │ trigger_picking()
             ↓
┌─────────────────────────────────────────────────────┐
│ Stock Picking (stock.picking)                       │
│ - state: draft → assigned → done                    │
│ - picking_type: outgoing                            │
│ - location_id: Main Warehouse                       │
│ - location_dest_id: Job Site Location               │
│ - move_lines: [products with qty, lot/serial]      │
└────────────┬────────────────────────────────────────┘
             │ confirm_picking()
             ↓
┌─────────────────────────────────────────────────────┐
│ Material Issue Updated                              │
│ - delivery_date: Picking date                       │
│ - received_date: Confirmation date                  │
│ - received_by: Contractor                           │
│ - proof_image: Receipt photo                        │
└─────────────────────────────────────────────────────┘
```

### 🗄️ Database Changes

**New Field Additions to `maintenance.job.material.request`**:
```python
# Stock Integration Fields
stock_picking_id = fields.Many2one(
    'stock.picking',
    string='Stock Picking',
    readonly=True,
    help='Associated warehouse stock picking'
)

picking_state = fields.Selection(
    [('draft', 'Draft'), 
     ('assigned', 'Assigned'), 
     ('done', 'Done'),
     ('cancelled', 'Cancelled')],
    related='stock_picking_id.state',
    store=True
)

delivery_date = fields.Datetime(
    string='Delivery Date',
    readonly=True
)

received_date = fields.Datetime(
    string='Received Date',
    readonly=True
)

received_by = fields.Many2one(
    'res.partner',
    string='Received By',
    readonly=True,
    help='Contractor who received materials'
)

proof_image = fields.Binary(
    string='Delivery Proof',
    help='Photo of delivered materials'
)

proof_image_filename = fields.Char()
```

**New Model: `warehouse.location.mapping`**:
```python
class WarehouseLocationMapping(models.Model):
    _name = 'warehouse.location.mapping'
    _description = 'Warehouse to Job Site Location Mapping'
    
    project_id = fields.Many2one(
        'rs.project',
        string='Project',
        required=True
    )
    
    warehouse_location_id = fields.Many2one(
        'stock.location',
        string='Main Warehouse Location',
        required=True,
        help='Source location for material picking'
    )
    
    job_site_location_id = fields.Many2one(
        'stock.location',
        string='Job Site Location',
        required=True,
        help='Destination location for materials at job site'
    )
    
    is_default = fields.Boolean(
        string='Default Location',
        default=False
    )
```

### 🔧 Implementation Steps

**Step 1: Create Stock Locations**
```python
# In data/warehouse_location_data.xml
<record id="location_main_warehouse" model="stock.location">
    <field name="name">Main Warehouse</field>
    <field name="location_id" ref="stock.stock_location_locations_virtual_parent"/>
    <field name="usage">internal</field>
</record>

<record id="location_job_site" model="stock.location">
    <field name="name">Job Site - Work in Progress</field>
    <field name="location_id" ref="stock.stock_location_locations_virtual_parent"/>
    <field name="usage">internal</field>
</record>
```

**Step 2: Create Picking Type**
```python
# In data/warehouse_picking_type_data.xml
<record id="picking_type_maintenance" model="stock.picking.type">
    <field name="name">Maintenance Materials</field>
    <field name="code">outgoing</field>
    <field name="warehouse_id" ref="stock.warehouse0"/>
    <field name="default_location_src_id" ref="location_main_warehouse"/>
    <field name="default_location_dest_id" ref="location_job_site"/>
</record>
```

**Step 3: Implement Picking Creation Method**
```python
@api.model
def create_stock_picking(self, material_request_id):
    """Create stock.picking for approved material request"""
    material_request = self.browse(material_request_id)
    
    if material_request.stock_picking_id:
        return material_request.stock_picking_id
    
    # Get warehouse locations
    mapping = self.env['warehouse.location.mapping'].search([
        ('project_id', '=', material_request.job_order_id.property_id.rs_project_id.id),
        ('is_default', '=', True)
    ], limit=1)
    
    if not mapping:
        raise UserError("Warehouse location mapping not configured for this project")
    
    # Create stock.picking
    picking = self.env['stock.picking'].create({
        'picking_type_id': self.env.ref('nthub_realestate.picking_type_maintenance').id,
        'location_id': mapping.warehouse_location_id.id,
        'location_dest_id': mapping.job_site_location_id.id,
        'partner_id': material_request.job_order_id.contractor_id.id,
        'origin': material_request.name,
    })
    
    # Create move lines for each material
    for line in material_request.material_line_ids:
        self.env['stock.move'].create({
            'picking_id': picking.id,
            'product_id': line.product_id.id,
            'product_uom_qty': line.qty,
            'product_uom': line.product_id.uom_id.id,
            'name': line.product_id.name,
        })
    
    # Update material request
    material_request.stock_picking_id = picking.id
    
    return picking

def action_create_picking(self):
    """Action button to create stock picking"""
    for record in self:
        record.create_stock_picking(record.id)
    return {
        'type': 'ir.actions.client',
        'tag': 'reload',
    }
```

**Step 4: Contractor Receipt Workflow**
```python
def action_confirm_receipt(self, **post):
    """Contractor confirms material receipt"""
    material_request = self.env['maintenance.job.material.request'].sudo().browse(
        int(post.get('material_request_id'))
    )
    
    # Validate contractor ownership
    if material_request.job_order_id.contractor_id.id != request.env.user.partner_id.id:
        raise AccessError("Not authorized to confirm receipt")
    
    # Update picking state
    material_request.stock_picking_id.action_done()
    
    # Update material request
    material_request.update({
        'received_date': fields.Datetime.now(),
        'received_by': request.env.user.partner_id.id,
        'proof_image': post.get('proof_image_binary'),
        'proof_image_filename': post.get('proof_image_filename'),
    })
    
    # Post message to chatter
    material_request.message_post(
        body=f"Materials received by {request.env.user.partner_id.name}",
        message_type='notification'
    )
    
    return request.redirect(f'/my/job_order/{material_request.job_order_id.id}')
```

### 🖥️ Portal Updates

**Contractor View - Material Receipt Confirmation**:
```html
<template id="portal_material_request_detail">
    <div class="card">
        <div class="card-header">
            <h5>Material Request: <t t-esc="material_request.name"/></h5>
        </div>
        <div class="card-body">
            <!-- Picking Status -->
            <div class="alert alert-info">
                <strong>Stock Status:</strong>
                <t t-if="material_request.picking_state == 'draft'">
                    <span class="badge bg-secondary">Picking Created</span>
                </t>
                <t t-if="material_request.picking_state == 'assigned'">
                    <span class="badge bg-warning">Ready for Pickup</span>
                </t>
                <t t-if="material_request.picking_state == 'done'">
                    <span class="badge bg-success">Delivered</span>
                </t>
            </div>
            
            <!-- Material List -->
            <table class="table">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Quantity</th>
                        <th>Unit</th>
                        <th>Lot/Serial</th>
                    </tr>
                </thead>
                <tbody>
                    <t t-foreach="material_request.stock_picking_id.move_line_ids" t-as="line">
                        <tr>
                            <td t-esc="line.product_id.name"/>
                            <td t-esc="line.qty_done"/>
                            <td t-esc="line.product_uom_id.name"/>
                            <td t-esc="line.lot_name or line.lot_id.name"/>
                        </tr>
                    </t>
                </tbody>
            </table>
            
            <!-- Receipt Confirmation Form -->
            <t t-if="material_request.picking_state == 'assigned'">
                <form method="POST" t-att-action="'/my/material_request/' + str(material_request.id) + '/confirm_receipt'" enctype="multipart/form-data">
                    <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
                    <input type="hidden" name="material_request_id" t-att-value="material_request.id"/>
                    
                    <div class="mb-3">
                        <label for="proof_image" class="form-label">
                            Proof of Delivery (Photo)
                            <span class="text-danger">*</span>
                        </label>
                        <input type="file" class="form-control" name="proof_image" id="proof_image" accept="image/*" required="1"/>
                        <small class="text-muted">Upload photo of delivered materials</small>
                    </div>
                    
                    <div class="mb-3">
                        <label for="notes" class="form-label">Notes</label>
                        <textarea class="form-control" name="notes" rows="3" placeholder="Any issues or notes about delivery..."></textarea>
                    </div>
                    
                    <button type="submit" class="btn btn-success">
                        <i class="fa fa-check me-2"/>Confirm Receipt
                    </button>
                </form>
            </t>
        </div>
    </div>
</template>
```

### ✅ Testing Checklist

- [ ] Warehouse location creation
- [ ] Stock picking auto-generation
- [ ] Move line creation for multiple materials
- [ ] Lot/serial number assignment
- [ ] Contractor receipt workflow
- [ ] Photo upload validation
- [ ] Stock level updates
- [ ] Integration with job order view
- [ ] Low stock alerts
- [ ] Multiple warehouse support

### 📱 Contractor Portal Routes

```python
@http.route(['/my/material_request/<int:material_request_id>/confirm_receipt'], 
            type='http', auth="user", website=True, methods=['POST'])
@contractor_only
def material_confirm_receipt(self, material_request_id, **post):
    """Confirm material receipt"""
    # Implementation as above
    pass

@http.route(['/my/job_order/<int:job_order_id>/materials'], 
            type='http', auth="user", website=True)
@contractor_only
def job_materials_list(self, job_order_id, **kw):
    """List pending material deliveries for job"""
    # Implementation
    pass
```

---

## PHASE 5: Purchase Approval Workflow - DETAILED ANALYSIS

### 📋 Current State
- Material requests created manually
- No approval workflow
- No purchase requisition tracking
- Manual vendor selection

### 🎯 Target State
- Auto-generated purchase requisitions
- Multi-level approval workflow
- Vendor selection and comparison
- Purchase order creation
- Delivery tracking

### 🔄 Approval Workflow States

```
DRAFT
  ↓
SUBMITTED (awaits 1st approver)
  ├→ REJECTED → Draft (modify and resubmit)
  ↓
LEVEL1_APPROVED (awaits 2nd approver) [if required by rules]
  ├→ REJECTED → Draft
  ↓
LEVEL2_APPROVED (awaits 3rd approver) [if required by rules]
  ├→ REJECTED → Draft
  ↓
LEVEL3_APPROVED (final approval)
  ├→ REJECTED → Draft
  ↓
PO_CREATED (Purchase Order generated)
  ↓
RECEIVED (materials received)
  ↓
INVOICED (invoice matched)
  ↓
CLOSED
```

### 📊 Data Model

**New Model: `maintenance.purchase.requisition`**:
```python
class MaintenancePurchaseRequisition(models.Model):
    _name = 'maintenance.purchase.requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Maintenance Material Purchase Requisition'
    
    name = fields.Char(
        string='Requisition Number',
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('maint.purchase.req')
    )
    
    # Reference Fields
    material_request_id = fields.Many2one(
        'maintenance.job.material.request',
        string='Material Request',
        required=True,
        readonly=True
    )
    
    job_order_id = fields.Many2one(
        related='material_request_id.job_order_id',
        store=True
    )
    
    # Financial Fields
    estimated_amount = fields.Monetary(
        string='Estimated Amount',
        required=True,
        currency_field='company_currency_id'
    )
    
    actual_amount = fields.Monetary(
        string='Actual Amount (PO)',
        store=True
    )
    
    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True
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
    
    # Approvers
    required_approvals = fields.Integer(
        string='Required Approval Levels',
        compute='_compute_required_approvals',
        store=True
    )
    
    approver1_id = fields.Many2one(
        'res.users',
        string='Level 1 Approver (Supervisor)',
        compute='_compute_approvers',
        store=True
    )
    
    approver1_date = fields.Datetime(
        string='Level 1 Approval Date',
        readonly=True
    )
    
    approver2_id = fields.Many2one(
        'res.users',
        string='Level 2 Approver (Manager)',
        readonly=True
    )
    
    approver2_date = fields.Datetime(
        string='Level 2 Approval Date',
        readonly=True
    )
    
    approver3_id = fields.Many2one(
        'res.users',
        string='Level 3 Approver (Finance)',
        readonly=True
    )
    
    approver3_date = fields.Datetime(
        string='Level 3 Approval Date',
        readonly=True
    )
    
    # Rejection Tracking
    rejection_count = fields.Integer(
        default=0,
        readonly=True
    )
    
    last_rejection_reason = fields.Text(
        string='Last Rejection Reason',
        readonly=True
    )
    
    # Vendor Information
    vendor_id = fields.Many2one(
        'res.partner',
        string='Selected Vendor',
        domain="[('supplier_rank', '>', 0)]"
    )
    
    vendor_quote_ids = fields.One2many(
        'maintenance.vendor.quote',
        'requisition_id',
        string='Vendor Quotes'
    )
    
    # Dates
    created_date = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True
    )
    
    requested_delivery_date = fields.Date(
        string='Requested Delivery Date',
        required=True
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
    
    # Methods
    @api.depends('estimated_amount')
    def _compute_required_approvals(self):
        """Determine required approval levels based on amount"""
        for record in self:
            amount = record.estimated_amount
            if amount <= 500:
                record.required_approvals = 1
            elif amount <= 2000:
                record.required_approvals = 2
            elif amount <= 10000:
                record.required_approvals = 3
            else:
                record.required_approvals = 4
    
    @api.depends('job_order_id')
    def _compute_approvers(self):
        """Assign default approvers based on job order"""
        for record in self:
            # Get supervisor from job order or use default
            supervisor = record.job_order_id.supervisor_id or self.env.user
            record.approver1_id = supervisor.id
    
    def action_submit(self):
        """Submit requisition for approval"""
        self.state = 'submitted'
        self.message_post(
            body='Requisition submitted for approval',
            message_type='notification'
        )
        # Send email to approver1
        self._notify_approver('approver1_id')
    
    def action_approve_level1(self, approval_date=None):
        """Level 1 approval"""
        if self.env.user.id != self.approver1_id.id:
            raise AccessError("Only assigned approver can approve")
        
        self.state = 'level1_approved'
        self.approver1_date = approval_date or fields.Datetime.now()
        
        if self.required_approvals > 1:
            self.state = 'level2_approved'
            self._notify_approver('approver2_id')
        else:
            self.state = 'level3_approved'
            self._create_purchase_order()
        
        self.message_post(
            body=f'Approved by {self.env.user.name}',
            message_type='notification'
        )
    
    def action_reject(self, reason):
        """Reject requisition"""
        self.rejection_count += 1
        self.last_rejection_reason = reason
        self.state = 'draft'
        self.message_post(
            body=f'Rejected by {self.env.user.name}: {reason}',
            message_type='notification'
        )
    
    def _create_purchase_order(self):
        """Create purchase order from approved requisition"""
        po_lines = []
        for line in self.material_request_id.material_line_ids:
            po_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_qty': line.qty,
                'product_uom': line.product_id.uom_id.id,
                'price_unit': line.unit_price or 0,
            }))
        
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor_id.id,
            'requisition_id': self.id,
            'date_planned': self.requested_delivery_date,
            'order_line': po_lines,
        })
        
        self.po_id = po.id
        self.state = 'po_created'
        self.actual_amount = po.amount_total
    
    def _notify_approver(self, approver_field):
        """Send approval notification"""
        approver = getattr(self, approver_field)
        if approver:
            template = self.env.ref('nthub_realestate.email_purchase_approval')
            template.send_mail(self.id, force_send=True)
```

**New Model: `maintenance.vendor.quote`**:
```python
class MaintenanceVendorQuote(models.Model):
    _name = 'maintenance.vendor.quote'
    _description = 'Vendor Price Quote'
    
    requisition_id = fields.Many2one(
        'maintenance.purchase.requisition',
        required=True,
        ondelete='cascade'
    )
    
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True
    )
    
    total_amount = fields.Monetary(
        string='Quote Amount',
        required=True,
        currency_field='company_currency_id'
    )
    
    delivery_days = fields.Integer(
        string='Delivery Days',
        default=5
    )
    
    payment_terms = fields.Char(
        string='Payment Terms',
        default='Net 30'
    )
    
    is_selected = fields.Boolean(
        string='Selected',
        default=False
    )
    
    notes = fields.Text(string='Notes')
    
    company_currency_id = fields.Many2one(
        'res.currency',
        related='requisition_id.company_currency_id',
        store=True
    )
    
    def action_select_quote(self):
        """Select this quote as the vendor"""
        self.is_selected = True
        self.requisition_id.vendor_id = self.vendor_id.id
        # Deselect other quotes
        self.requisition_id.vendor_quote_ids.filtered(
            lambda x: x.id != self.id
        ).write({'is_selected': False})
```

### 🔧 Implementation Steps

**Step 1: Create Sequence**
```xml
<record id="seq_maint_purchase_req" model="ir.sequence">
    <field name="name">Maintenance Purchase Requisition</field>
    <field name="code">maint.purchase.req</field>
    <field name="prefix">REQ/</field>
    <field name="padding">5</field>
</record>
```

**Step 2: Create Approval Rules**
```python
class MaintenancePurchaseApprovalRule(models.Model):
    _name = 'maintenance.purchase.approval.rule'
    
    name = fields.Char(required=True)
    amount_min = fields.Monetary(required=True)
    amount_max = fields.Monetary(required=True)
    approver_ids = fields.Many2many('res.users', string='Required Approvers')
    sequence = fields.Integer(default=10)
```

**Step 3: Create Email Templates**
```xml
<record id="email_purchase_approval" model="mail.template">
    <field name="name">Purchase Requisition Approval Request</field>
    <field name="model_id" ref="model_maintenance_purchase_requisition"/>
    <field name="email_to">${object.approver1_id.email}</field>
    <field name="subject">Approval Required: ${object.name}</field>
    <field name="body_html">
        <![CDATA[
            <p>Dear ${object.approver1_id.name},</p>
            <p>A new purchase requisition requires your approval:</p>
            <p>
                <strong>Requisition:</strong> ${object.name}<br/>
                <strong>Amount:</strong> ${object.estimated_amount} AED<br/>
                <strong>Material:</strong> ${object.material_request_id.material_line_ids[0].product_id.name if object.material_request_id.material_line_ids else 'N/A'}<br/>
                <strong>Job Order:</strong> ${object.job_order_id.name}
            </p>
            <p>
                <a href="${object.get_portal_url()}" class="btn btn-primary">
                    Review & Approve
                </a>
            </p>
        ]]>
    </field>
</record>
```

### ✅ Testing Checklist

- [ ] Requisition auto-generation from material request
- [ ] Approval level calculation based on amount
- [ ] Email notifications to approvers
- [ ] Level 1, 2, 3 approval workflow
- [ ] Rejection and resubmission
- [ ] Vendor quote comparison
- [ ] Purchase order creation
- [ ] Portal approval interface
- [ ] Audit trail in chatter
- [ ] Multi-currency support

---

## PHASE 6: Job Completion & Handover - DETAILED ANALYSIS

### 📋 Current State
- Job orders in progress
- No formal completion workflow
- Manual handover process
- No quality checks

### 🎯 Target State
- Structured completion workflow
- Quality inspection checklist
- Handover documents
- Tenant approval process
- Rating system

### 🔄 Workflow

```
IN_PROGRESS
  ↓
COMPLETED (contractor marks complete)
  ├→ quality_checklist_required()
  ├→ generate_completion_form()
  ├→ generate_handover_report()
  ↓
READY_FOR_INSPECTION (tenant can review)
  ├→ tenant_requests_rework()
  ├→ contractor_reopen() → IN_PROGRESS
  ↓
APPROVED_BY_TENANT (tenant approves)
  ├→ rate_contractor() [1-5 stars]
  ├→ add_feedback()
  ↓
CLOSED
```

### 📊 Data Model

**Extend `job.order.form`**:
```python
# Add fields to track completion
completion_status = fields.Selection(
    [('in_progress', 'In Progress'),
     ('completed', 'Completed'),
     ('ready_for_inspection', 'Ready for Inspection'),
     ('approved', 'Approved by Tenant'),
     ('closed', 'Closed')],
    default='in_progress',
    tracking=True
)

completion_date = fields.Datetime(
    string='Completion Date',
    readonly=True
)

completion_notes = fields.Text(
    string='Completion Notes'
)

approved_by_tenant = fields.Boolean(
    string='Approved by Tenant',
    readonly=True
)

approval_date = fields.Datetime(
    string='Tenant Approval Date',
    readonly=True
)

contractor_rating = fields.Float(
    string='Contractor Rating',
    digits=(2, 1),
    readonly=True,
    help='Rating from 1 to 5 stars'
)

tenant_feedback = fields.Text(
    string='Tenant Feedback',
    readonly=True
)

has_defects = fields.Boolean(
    string='Has Defects Reported',
    default=False
)

defect_count = fields.Integer(
    string='Number of Defects',
    compute='_compute_defect_count'
)
```

**New Model: `job.order.completion.checklist`**:
```python
class JobOrderCompletionChecklist(models.Model):
    _name = 'job.order.completion.checklist'
    _description = 'Job Completion Quality Checklist'
    
    name = fields.Char(required=True)
    maintenance_type = fields.Selection(
        [('electrical', 'Electrical'),
         ('mechanical', 'Mechanical'),
         ('low_current', 'Low Current'),
         ('civil', 'Civil'),
         ('general', 'General'),
         ('other', 'Other')],
        required=True
    )
    
    checklist_items = fields.One2many(
        'job.order.completion.item',
        'checklist_id',
        string='Checklist Items'
    )
    
    is_active = fields.Boolean(default=True)

class JobOrderCompletionItem(models.Model):
    _name = 'job.order.completion.item'
    _description = 'Checklist Item'
    
    checklist_id = fields.Many2one(
        'job.order.completion.checklist',
        required=True,
        ondelete='cascade'
    )
    
    description = fields.Char(required=True)
    is_required = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
```

**New Model: `job.order.completion.result`**:
```python
class JobOrderCompletionResult(models.Model):
    _name = 'job.order.completion.result'
    _description = 'Job Completion Assessment'
    
    job_order_id = fields.Many2one(
        'job.order.form',
        required=True,
        ondelete='cascade'
    )
    
    checklist_id = fields.Many2one(
        'job.order.completion.checklist',
        required=True
    )
    
    completion_date = fields.Datetime(
        default=fields.Datetime.now
    )
    
    item_results = fields.One2many(
        'job.order.checklist.result',
        'completion_result_id',
        string='Item Results'
    )
    
    overall_status = fields.Selection(
        [('passed', 'Passed'),
         ('failed', 'Failed'),
         ('pending_rework', 'Pending Rework')],
        compute='_compute_overall_status'
    )
    
    completion_photos = fields.Many2many(
        'ir.attachment',
        'job_completion_photos_rel',
        string='Completion Photos'
    )
    
    contractor_notes = fields.Text()
    
    def _compute_overall_status(self):
        for record in self:
            failed_items = record.item_results.filtered(lambda x: x.status == 'failed')
            if failed_items:
                record.overall_status = 'failed'
            else:
                record.overall_status = 'passed'

class JobOrderChecklistResult(models.Model):
    _name = 'job.order.checklist.result'
    _description = 'Individual Checklist Item Result'
    
    completion_result_id = fields.Many2one(
        'job.order.completion.result',
        required=True,
        ondelete='cascade'
    )
    
    item_id = fields.Many2one(
        'job.order.completion.item',
        required=True
    )
    
    status = fields.Selection(
        [('passed', 'Passed'),
         ('failed', 'Failed'),
         ('n/a', 'Not Applicable')],
        required=True
    )
    
    notes = fields.Text()
    photo_id = fields.Many2one(
        'ir.attachment',
        string='Supporting Photo'
    )
```

**New Model: `job.order.defect`**:
```python
class JobOrderDefect(models.Model):
    _name = 'job.order.defect'
    _description = 'Job Order Defect Report'
    
    job_order_id = fields.Many2one(
        'job.order.form',
        required=True,
        ondelete='cascade'
    )
    
    description = fields.Text(required=True)
    severity = fields.Selection(
        [('minor', 'Minor'),
         ('major', 'Major'),
         ('critical', 'Critical')],
        default='minor'
    )
    
    reported_date = fields.Datetime(
        default=fields.Datetime.now
    )
    
    reported_by = fields.Many2one(
        'res.partner',
        string='Reported By'
    )
    
    status = fields.Selection(
        [('reported', 'Reported'),
         ('acknowledged', 'Acknowledged'),
         ('in_repair', 'In Repair'),
         ('resolved', 'Resolved'),
         ('closed', 'Closed')],
        default='reported'
    )
    
    rework_job_order_id = fields.Many2one(
        'job.order.form',
        string='Rework Job Order'
    )
    
    photos = fields.Many2many(
        'ir.attachment',
        string='Defect Photos'
    )
```

### 🔧 Implementation Steps

**Step 1: Create Completion Checklists (Data)**
```xml
<record id="checklist_electrical_basic" model="job.order.completion.checklist">
    <field name="name">Electrical Work - Basic Checklist</field>
    <field name="maintenance_type">electrical</field>
</record>

<record id="checklist_item_1" model="job.order.completion.item">
    <field name="checklist_id" ref="checklist_electrical_basic"/>
    <field name="description">All electrical connections secure</field>
    <field name="is_required">True</field>
    <field name="sequence">10</field>
</record>

<record id="checklist_item_2" model="job.order.completion.item">
    <field name="checklist_id" ref="checklist_electrical_basic"/>
    <field name="description">All safety switches functioning</field>
    <field name="is_required">True</field>
    <field name="sequence">20</field>
</record>
```

**Step 2: Implement Completion Methods**
```python
def action_mark_complete(self):
    """Contractor marks job as complete"""
    if self.state != 'in_progress':
        raise UserError("Can only complete in-progress jobs")
    
    self.state = 'completed'
    self.completion_date = fields.Datetime.now()
    self.message_post(
        body=f'Job marked as complete by {self.env.user.name}',
        message_type='notification'
    )

def action_create_completion_checklist(self):
    """Auto-generate checklist based on maintenance type"""
    checklist = self.env['job.order.completion.checklist'].search([
        ('maintenance_type', '=', self.x_request_type),
        ('is_active', '=', True)
    ], limit=1)
    
    if not checklist:
        raise UserError(f"No checklist configured for {self.x_request_type}")
    
    completion = self.env['job.order.completion.result'].create({
        'job_order_id': self.id,
        'checklist_id': checklist.id,
    })
    
    # Pre-create result lines
    for item in checklist.checklist_items:
        self.env['job.order.checklist.result'].create({
            'completion_result_id': completion.id,
            'item_id': item.id,
            'status': 'n/a',
        })
    
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'job.order.completion.result',
        'res_id': completion.id,
        'view_mode': 'form',
        'views': [(False, 'form')],
    }

def action_ready_for_inspection(self):
    """Mark job ready for tenant inspection"""
    self.completion_status = 'ready_for_inspection'
    # Send notification to tenant
    self._notify_tenant_inspection_ready()

def action_approve(self):
    """Tenant approves completed work"""
    self.completion_status = 'approved'
    self.approved_by_tenant = True
    self.approval_date = fields.Datetime.now()

def action_report_defect(self, description, severity='minor'):
    """Tenant reports a defect"""
    defect = self.env['job.order.defect'].create({
        'job_order_id': self.id,
        'description': description,
        'severity': severity,
        'reported_by': self.env.user.partner_id.id,
    })
    
    # Auto-create rework job order
    rework_job = self.copy({
        'name': f"{self.name} - Rework",
        'parent_job_order_id': self.id,
        'state': 'assigned',
    })
    
    defect.rework_job_order_id = rework_job.id
    
    return rework_job
```

### 🖥️ Tenant Portal - Job Approval

```html
<template id="portal_job_completion_view">
    <div class="card">
        <div class="card-header bg-success text-white">
            <h5>Job Completion Review</h5>
        </div>
        <div class="card-body">
            <!-- Completion Status -->
            <div class="alert alert-info">
                <strong>Status:</strong>
                <t t-if="job_order.completion_status == 'completed'">
                    <span class="badge bg-primary">Completed - Awaiting Your Review</span>
                </t>
                <t t-if="job_order.completion_status == 'ready_for_inspection'">
                    <span class="badge bg-warning">Ready for Your Inspection</span>
                </t>
                <t t-if="job_order.completion_status == 'approved'">
                    <span class="badge bg-success">Approved</span>
                </t>
            </div>
            
            <!-- Completion Photos -->
            <div class="mb-4">
                <h6>Completion Photos</h6>
                <div class="row g-2">
                    <t t-foreach="job_order.completion_photos" t-as="photo">
                        <div class="col-md-3">
                            <img t-att-src="photo.image_url" class="img-thumbnail" style="width: 100%; height: 200px; object-fit: cover;"/>
                        </div>
                    </t>
                </div>
            </div>
            
            <!-- Completion Checklist Results -->
            <div class="mb-4">
                <h6>Quality Checklist</h6>
                <table class="table">
                    <tbody>
                        <t t-foreach="job_order.completion_results[0].item_results" t-as="result">
                            <tr>
                                <td width="60%">
                                    <strong t-esc="result.item_id.description"/>
                                </td>
                                <td>
                                    <t t-if="result.status == 'passed'">
                                        <span class="badge bg-success">✓ Passed</span>
                                    </t>
                                    <t t-if="result.status == 'failed'">
                                        <span class="badge bg-danger">✗ Failed</span>
                                    </t>
                                    <t t-if="result.status == 'n/a'">
                                        <span class="badge bg-secondary">N/A</span>
                                    </t>
                                </td>
                            </tr>
                            <t t-if="result.notes">
                                <tr>
                                    <td colspan="2" class="text-muted ps-4">
                                        <small t-esc="result.notes"/>
                                    </td>
                                </tr>
                            </t>
                        </t>
                    </tbody>
                </table>
            </div>
            
            <!-- Contractor Notes -->
            <t t-if="job_order.completion_notes">
                <div class="mb-4">
                    <h6>Contractor Notes</h6>
                    <p t-esc="job_order.completion_notes"/>
                </div>
            </t>
            
            <!-- Action Buttons -->
            <div class="mb-4">
                <t t-if="job_order.completion_status in ['ready_for_inspection', 'completed']">
                    <!-- Approve Button -->
                    <form method="POST" t-att-action="'/my/job_order/' + str(job_order.id) + '/approve'" class="d-inline">
                        <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
                        <button type="submit" class="btn btn-success">
                            <i class="fa fa-check me-2"/>Approve Work
                        </button>
                    </form>
                    
                    <!-- Report Defect Button -->
                    <button type="button" class="btn btn-warning" data-bs-toggle="modal" data-bs-target="#defectModal">
                        <i class="fa fa-exclamation-triangle me-2"/>Report Defect
                    </button>
                </t>
            </div>
            
            <!-- Rating & Feedback (if approved) -->
            <t t-if="job_order.completion_status == 'approved' and not job_order.contractor_rating">
                <div class="card border-info">
                    <div class="card-body">
                        <h6>Rate Your Experience</h6>
                        <form method="POST" t-att-action="'/my/job_order/' + str(job_order.id) + '/rate'">
                            <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
                            
                            <!-- Star Rating -->
                            <div class="mb-3">
                                <label class="form-label">Contractor Rating</label>
                                <div id="rating-stars" class="mb-2">
                                    <t t-foreach="[1, 2, 3, 4, 5]" t-as="star">
                                        <i class="fa fa-star" t-att-data-value="star" style="cursor: pointer; font-size: 1.5rem; color: #ddd;" onclick="setRating(this)"></i>
                                    </t>
                                </div>
                                <input type="hidden" name="rating" id="rating-input"/>
                                <small class="text-muted">Click to rate contractor performance</small>
                            </div>
                            
                            <!-- Feedback -->
                            <div class="mb-3">
                                <label for="feedback" class="form-label">Feedback (Optional)</label>
                                <textarea class="form-control" name="feedback" rows="4" placeholder="Share your experience..."></textarea>
                            </div>
                            
                            <button type="submit" class="btn btn-primary">Submit Rating</button>
                        </form>
                    </div>
                </div>
            </t>
        </div>
    </div>
    
    <!-- Defect Report Modal -->
    <div class="modal fade" id="defectModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Report a Defect</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <form method="POST" t-att-action="'/my/job_order/' + str(job_order.id) + '/report_defect'" enctype="multipart/form-data">
                    <div class="modal-body">
                        <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
                        
                        <div class="mb-3">
                            <label for="defect_description" class="form-label">Description <span class="text-danger">*</span></label>
                            <textarea class="form-control" id="defect_description" name="description" rows="4" required="1" placeholder="Describe the defect..."></textarea>
                        </div>
                        
                        <div class="mb-3">
                            <label for="defect_severity" class="form-label">Severity <span class="text-danger">*</span></label>
                            <select class="form-select" id="defect_severity" name="severity" required="1">
                                <option value="">-- Select Severity --</option>
                                <option value="minor">Minor</option>
                                <option value="major">Major</option>
                                <option value="critical">Critical</option>
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label for="defect_photo" class="form-label">Photo (Optional)</label>
                            <input type="file" class="form-control" id="defect_photo" name="photo" accept="image/*"/>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-danger">Report Defect</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
    
    <script>
        function setRating(element) {
            const rating = element.getAttribute('data-value');
            document.getElementById('rating-input').value = rating;
            
            // Update star colors
            const stars = document.querySelectorAll('#rating-stars i');
            stars.forEach((star, index) => {
                if (index < rating) {
                    star.style.color = '#ffc107';
                } else {
                    star.style.color = '#ddd';
                }
            });
        }
    </script>
</template>
```

### ✅ Testing Checklist

- [ ] Mark job as complete
- [ ] Auto-generate completion checklist
- [ ] Tenant view completed job
- [ ] Tenant approve work
- [ ] Tenant report defects
- [ ] Auto-create rework job order
- [ ] Rating and feedback submission
- [ ] Email notifications to contractor
- [ ] Defect tracking and resolution
- [ ] Completion documents generation

---

## 📊 Integrated Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 4-6 INTEGRATED WORKFLOW                               │
└─────────────────────────────────────────────────────────────┘

1. MATERIAL REQUEST APPROVED (Phase 4 Start)
   │
   ├→ Create Stock Picking
   │  ├→ Source: Main Warehouse
   │  ├→ Dest: Job Site
   │  └→ Move Lines: Products with Qty, Lot/Serial
   │
   └→ CREATE PURCHASE REQUISITION (Phase 5 Start)
      │
      ├→ Auto-calculate approval levels by amount
      │
      ├→ Submit for Approval
      │  ├→ Level 1: Supervisor Review
      │  ├→ Level 2: Manager Review (if needed)
      │  ├→ Level 3: Finance Review (if needed)
      │  └→ Rejection allowed at each level
      │
      └→ CREATE PURCHASE ORDER
         │
         ├→ Select Vendor (from quotes)
         │
         ├→ Confirm Stock Picking
         │  │
         │  └→ Contractor Receives Materials
         │     ├→ Confirms receipt
         │     ├→ Uploads photo proof
         │     └→ Stock levels updated
         │
         └→ CONTRACTOR PERFORMS WORK (Phase 6 Start)
            │
            ├→ Complete Job
            │
            ├→ Generate Completion Checklist
            │  ├→ Quality items per maintenance type
            │  ├→ Contractor fills checklist
            │  └→ Upload completion photos
            │
            ├→ Ready for Inspection
            │
            └→ TENANT REVIEW & APPROVAL
               ├→ View completion photos
               ├→ Review quality checklist
               ├→ Approve or report defects
               │  └→ Defects → Rework Job Order
               ├→ Rate contractor (1-5 stars)
               ├→ Provide feedback
               │
               └→ JOB CLOSED
```

---

## 💡 Recommendations

### Phase 4 Implementation Order:
1. Create warehouse locations
2. Implement stock picking creation
3. Update contractor portal for receipt
4. Test stock movements
5. Deploy to staging

### Phase 5 Implementation Order:
1. Create requisition model
2. Implement approval rules
3. Create email templates
4. Implement vendor quotes
5. PO creation logic
6. Deploy to staging

### Phase 6 Implementation Order:
1. Create completion models
2. Generate checklists
3. Update tenant portal
4. Implement defect tracking
5. Rating & feedback system
6. Deploy to staging

---

This completes the detailed analysis for Phases 4-6. Ready to begin implementation?

