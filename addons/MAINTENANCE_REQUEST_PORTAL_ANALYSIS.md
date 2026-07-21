# Maintenance Request Portal - Workflow Analysis

## Current Status

The tenant portal currently supports creating and viewing maintenance requests, but the workflow is **incomplete** relative to the actual maintenance request model.

---

## 1. Current Maintenance Request Model - Key Fields

### Basic Information
- **name**: Auto-generated sequence (REQUEST/001, etc.)
- **partner_id**: Tenant (required)
- **x_unit_area**: Unit/Area selection (optional - should be required for portal)
- **x_building_id**: Auto-populated from unit (related field, readonly)
- **x_tenant_mobile**: Auto-populated from partner (readonly)
- **x_tenant_email**: Auto-populated from partner (readonly)

### Request Details
- **request_date**: When request was created (default: now)
- **x_request_type**: Selection field with 6 options:
  - Electrical
  - Mechanical
  - Low Current
  - Civil
  - General
  - Other
  - **Current Portal Issue**: NOT captured in form!

- **priority**: Severity level:
  - Low, Normal, High, Urgent
  - **Current Portal Issue**: NOT captured in form!

- **description**: Problem description (required)
- **attachment_ids**: File uploads via M2M relation

### Status Workflow
- **x_status**: Core status field (default: 'draft')
  ```
  draft → submitted → under_review → job_ordered → in_progress → approved_by_tenant → closed
  └→ cancelled
  ```

- **Related Job Order**: x_job_order_id (Many2one relation)
- **Cancellation Reason**: Text field for cancellation tracking

---

## 2. Maintenance Request Workflow - Complete Lifecycle

### Stage 1: Draft (Initial Creation)
- **When**: Tenant creates request via portal
- **What happens**:
  - Name auto-generated via sequence
  - Status = 'draft'
  - Fields populated: x_unit_area, description, attachments
  - **MISSING in portal**: x_request_type, priority

### Stage 2: Submit (action_submit)
- **Trigger**: action_submit() button
- **Changes**: draft → submitted
- **Chatter**: Posts "Maintenance request submitted for review"
- **Portal Integration**: NOT YET - No button in portal

### Stage 3: Under Review (action_under_review)
- **Trigger**: Internal staff reviews
- **Changes**: submitted → under_review
- **Chatter**: Posts "Maintenance request is under review"
- **Portal Integration**: NOT YET - Tenant should see status change

### Stage 4: Create Job Order (action_create_job_order)
- **Trigger**: Supervisor creates job order
- **Validation**: x_unit_area must be set
- **Mapping**: Request type → Job type
  ```
  electrical/mechanical/low_current/civil → fault
  general → new
  other → other
  ```
- **Creates**: New maintenance.job.order with:
  - maintenance_request_id link
  - All unit/tenant info
  - Priority preserved
  - Status: job_ordered
- **Portal Integration**: NOT YET - Tenant should see job created

### Stage 5: In Progress (Contractor Work)
- **Changes**: Status = 'in_progress'
- **Who updates**: Contractor via contractor portal
- **Portal Integration**: NOT YET - Tenant should see work started

### Stage 6: Approval (action_approve - if exists)
- **Changes**: Status = 'approved_by_tenant'
- **Who updates**: Tenant approves completed work
- **Portal Integration**: NOT YET - Tenant should have approval button

### Stage 7: Closed
- **Changes**: Status = 'closed'
- **Portal Integration**: NOT YET - Automatic or manual?

### Alternative: Cancelled (action_cancel)
- **Trigger**: action_cancel() → wizard modal
- **Input**: Cancellation reason
- **Changes**: Any status → cancelled + reason stored
- **Chatter**: Posts cancellation reason
- **Portal Integration**: NOT YET - Tenant should have cancel option

---

## 3. What's MISSING in Current Portal

### A. Form Input Fields - CRITICAL GAPS

**Current Portal Captures:**
```
✓ Description (required)
✓ maintenance_type_ids (checkboxes)
✓ Attachments (implied)
```

**Missing in Portal - SHOULD CAPTURE:**
```
✗ x_request_type (electrical, mechanical, low_current, civil, general, other)
  └─ Required by model
  └─ CRITICAL for job type mapping

✗ priority (low, normal, high, urgent)
  └─ Required by model
  └─ Important for scheduling

✗ x_unit_area (Unit/Area selection)
  └─ Currently optional in model but SHOULD be required for portal
  └─ Needed to link maintenance request to property

✗ request_date (default: now - acceptable as default)
```

**Note**: maintenance_type_ids is captured but NOT in the model fields. It's a Many2many relation but seems disconnected from actual workflow.

### B. Workflow Actions - MISSING UI

**Current Portal Provides:**
```
✓ Create request (form submission)
✓ View requests (list)
✓ View request details
```

**Missing Tenant Portal Actions:**
```
✗ Submit button (action_submit)
  └─ Moves from draft → submitted
  └─ Triggers review process

✗ Cancel button (action_cancel)
  └─ Opens wizard modal for cancellation reason
  └─ Needed if tenant wants to cancel

✗ Approve/Accept button (if status = completed)
  └─ After contractor finishes work
  └─ Tenant should approve before closing

✗ View Job Order (if x_job_order_id exists)
  └─ Once job is created, tenant should see job details
  └─ Link to contractor portal updates

✗ View Contractor Info (if job assigned)
  └─ Who is assigned?
  └─ What are they doing?
```

### C. Status Display & Tracking

**Current Portal Shows:**
```
✓ Status in list view (implied by state calculation)
```

**Missing Visualization:**
```
✗ Clear status badges/timeline
✗ Last update date
✗ Assigned contractor info
✗ Job order reference/link
✗ Chatter messages (request updates)
```

---

## 4. Recommended Portal Enhancements - Priority Order

### PRIORITY 1: Fix Form Completeness (CRITICAL)
**Add to maintenance request creation form:**

1. **Request Type** (required dropdown)
   ```
   - Electrical
   - Mechanical  
   - Low Current
   - Civil
   - General
   - Other
   ```

2. **Priority** (required dropdown)
   ```
   - Low
   - Normal
   - High
   - Urgent
   ```

3. **Unit / Area Selection** (make required)
   ```
   - Browse available rental units
   - Auto-fill building from unit selection
   ```

**Reason**: These are required fields in the model and necessary for job creation workflow.

### PRIORITY 2: Add Submit Workflow (HIGH)
**Add to maintenance request detail page:**

1. **Submit Button** (if status = 'draft')
   - POST to `/my/maintenance_request/<id>/submit`
   - Changes status: draft → submitted
   - Shows success message
   - Updates in chatter

2. **Reopen Button** (if status = 'cancelled')
   - POST to `/my/maintenance_request/<id>/reopen`
   - Changes status: cancelled → draft
   - Clears cancellation reason

**Reason**: Workflow requires explicit submission; draft status indicates incomplete requests.

### PRIORITY 3: Add Cancellation Support (MEDIUM)
**Add to maintenance request detail page:**

1. **Cancel Button** (if status != 'closed')
   - Opens modal form asking for cancellation reason
   - POST to `/my/maintenance_request/<id>/cancel`
   - Moves to cancelled status
   - Stores reason

**Reason**: Tenants need ability to withdraw requests.

### PRIORITY 4: Add Job Order Integration (MEDIUM)
**Add to maintenance request detail page:**

If x_job_order_id exists:
```
1. Job Order Card (readonly)
   - Job Order Reference (#JOB/001)
   - Status (sent_to_contractor, in_progress, completed, etc)
   - Assigned Contractor Name
   - Start Date / Expected End Date
   - View Job Details button → links to job detail page

2. Contractor Info Card
   - Name
   - Contact Mobile
   - Contact Email
```

**Reason**: Tenant needs visibility into what's happening after job creation.

### PRIORITY 5: Add Status Timeline (LOW)
**Add to maintenance request detail page:**

Visual timeline showing progression:
```
✓ Created (date)
→ Submitted (date) 
→ Under Review (date)
→ Job Ordered #JOB/001 (date)
→ In Progress (date)
→ Ready for Approval (date)
→ Approved (date)
→ Closed (date)
```

**Reason**: Better user experience and transparency.

---

## 5. Implementation Plan

### Changes Required

#### A. Model Changes (None needed)
- Maintenance request model already has all fields
- Just need to use them properly in portal

#### B. Controller Changes (portal.py)

**1. Update form submission (PRIORITY 1)**
```python
# In portal_create_maintenance_request()
# Add to request.env['rental.maintenance.request'].sudo().create():
- 'x_request_type': post.get('request_type', 'general')  # required
- 'priority': post.get('priority', 'normal')  # required  
- 'x_unit_area': int(post.get('unit_area_id'))  # required
# Validate x_unit_area before creating
```

**2. Add submit action route (PRIORITY 2)**
```python
@http.route(['/my/maintenance_request/<int:request_id>/submit'], 
            type='http', auth="user", website=True, methods=['POST'])
@tenant_only
def portal_submit_maintenance_request(self, request_id, **post):
    maint_req = self._get_accessible_maintenance_request(request_id)
    if maint_req.x_status == 'draft':
        maint_req.action_submit()
    return request.redirect(f'/my/maintenance_request/{request_id}?message=submitted')
```

**3. Add cancel action route (PRIORITY 3)**
```python
@http.route(['/my/maintenance_request/<int:request_id>/cancel'], 
            type='http', auth="user", website=True, methods=['POST'])
@tenant_only
def portal_cancel_maintenance_request(self, request_id, **post):
    maint_req = self._get_accessible_maintenance_request(request_id)
    reason = post.get('cancellation_reason', 'No reason provided')
    # Write directly or use action_cancel
    maint_req.write({
        'x_status': 'cancelled',
        'cancellation_reason': reason
    })
    return request.redirect(f'/my/maintenance_request/{request_id}?message=cancelled')
```

**4. Add reopen action route (PRIORITY 2)**
```python
@http.route(['/my/maintenance_request/<int:request_id>/reopen'], 
            type='http', auth="user", website=True, methods=['POST'])
@tenant_only
def portal_reopen_maintenance_request(self, request_id, **post):
    maint_req = self._get_accessible_maintenance_request(request_id)
    if maint_req.x_status == 'cancelled':
        maint_req.action_reopen()
    return request.redirect(f'/my/maintenance_request/{request_id}?message=reopened')
```

#### C. Template Changes (portal views)

**1. Update creation form template (PRIORITY 1)**
- Add request_type dropdown
- Add priority dropdown
- Add unit_area_id dropdown (query available units for this tenant)

**2. Update detail view template (PRIORITY 2-4)**
- Add Submit button (if draft)
- Add Reopen button (if cancelled)
- Add Cancel button with modal (if not closed/already assigned)
- Add Job Order card (if x_job_order_id exists)
- Add Contractor info card (if assigned)
- Add status timeline

**3. Consider adding modals**
- Cancel reason modal
- Job details modal (if applicable)

---

## 6. Data Flow Comparison

### Current Portal Flow (Incomplete)
```
Tenant Portal
    ↓
Create Request Form
    ├─ description (required)
    ├─ maintenance_type_ids
    └─ attachments
    ↓
rental.maintenance.request created
    ├─ status: draft
    ├─ partner_id: set
    ├─ contract_id: set
    └─ ✗ MISSING: x_request_type, priority, x_unit_area
    ↓
View in list/detail
    ↓
END (no workflow progression)
```

### Expected Complete Flow
```
Tenant Portal
    ↓
Create Request Form
    ├─ description (required) ✓
    ├─ x_request_type (required) ← ADD
    ├─ priority (required) ← ADD
    ├─ x_unit_area (required) ← ADD
    └─ attachments ✓
    ↓
rental.maintenance.request created
    └─ status: draft
    ↓
[Submit] Button
    └─ action_submit() → status: submitted
    ↓
Internal Review
    └─ status: under_review (staff action)
    ↓
[Create Job Order] Button
    └─ action_create_job_order() → creates maintenance.job.order
    └─ status: job_ordered
    ↓
Contractor Portal (assignment & work)
    └─ status: in_progress
    ↓
Tenant Portal - [Approve] Button
    └─ status: approved_by_tenant
    ↓
[Close] Button
    └─ status: closed
    ↓
OR [Cancel] Button (anytime)
    └─ status: cancelled + reason
```

---

## 7. Database Considerations

### Current Maintenance Request Creation via Portal
```sql
INSERT INTO rental_maintenance_request (
    name,                    -- auto-generated sequence
    partner_id,             -- tenant
    x_status,              -- 'draft'
    request_date,          -- now()
    description,           -- from form
    contract_id,           -- ← LINKED (legacy field)
    maintenance_type_ids,  -- from form
    attachment_ids,        -- from form
    
    -- ✗ MISSING:
    x_request_type,        -- should be set from form
    priority,              -- should be set from form
    x_unit_area,           -- should be set from form
    x_building_id          -- auto-computed from unit
)
```

### After Implementation
```sql
-- All fields will be populated, including:
- x_request_type: 'electrical' | 'mechanical' | etc
- priority: 'low' | 'normal' | 'high' | 'urgent'
- x_unit_area: unit_id
- x_building_id: building_id (auto-computed)
```

---

## 8. Validation Rules to Implement

### On Form Submission
1. ✓ description: required, non-empty
2. ✗ x_request_type: required, valid selection
3. ✗ priority: required, valid selection
4. ✗ x_unit_area: required, must be accessible to tenant
5. ✓ attachments: optional

### On Submit Action
1. Status must be 'draft'

### On Cancel Action
1. Status must not be 'closed'
2. Cancellation reason: required, non-empty

---

## 9. Security Considerations

### Current Protections
- ✓ @tenant_only decorator on all routes
- ✓ Access check: contract.partner_id == user.partner_id

### Additional Needed
- Validate x_unit_area belongs to tenant's rental units
- Validate cancellation is only by request creator
- Validate submit/cancel operations by request status

---

## Summary

**The tenant portal needs significant enhancements to support the full maintenance request workflow:**

1. **Form completeness** (Priority 1): Add x_request_type, priority, x_unit_area
2. **Workflow buttons** (Priority 2): Submit, Reopen, Cancel
3. **Job tracking** (Priority 3): Display job order and contractor info when assigned
4. **Status visibility** (Priority 4): Clear timeline and current status
5. **Error handling** (Priority 5): Proper validation and user feedback

**Estimated complexity**: Medium (5-8 hours total development + testing)

**Key files to modify**:
- `/nthub_realestate/controllers/portal.py` - Add 3-4 new routes
- `/nthub_realestate/views/portal_views.xml` - Update form and detail templates
- `/nthub_realestate/models/rental_maintenance.py` - No changes needed (already complete)
