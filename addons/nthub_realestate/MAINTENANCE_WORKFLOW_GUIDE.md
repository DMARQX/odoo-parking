# Maintenance Request & Job Order Workflow Guide

## System Overview

The maintenance management system consists of two interconnected models:
1. **Rental Maintenance Request** (`rental.maintenance.request`) - Tenant-submitted requests
2. **Maintenance Job Order** (`maintenance.job.order`) - Saqifa's execution workflow

---

## Rental Maintenance Request Workflow (FR-1)

### States & Transitions

```
Draft → Submitted → Under Review → Job Ordered → In Progress → Approved by Tenant → Closed → Cancelled
```

### State Details

| State | Code | Description | Who Can Access |
|-------|------|-------------|----------------|
| Draft | `draft` | Initial state when request is created | Tenant, Saqifa |
| Submitted | `submitted` | Tenant has submitted for review | Tenant, Saqifa |
| Under Review | `under_review` | Saqifa is reviewing the request | Saqifa |
| Job Ordered | `job_ordered` | Job Order has been created | Saqifa |
| In Progress | `in_progress` | Contractor is working on the job | Saqifa, Contractor |
| Approved by Tenant | `approved_by_tenant` | Tenant has signed off | Tenant, Saqifa |
| Closed | `closed` | Request is completed and closed | All (read-only) |
| Cancelled | `cancelled` | Request has been cancelled | All (read-only) |

### Buttons & Actions

| Button | Method | From State | To State | Who Can Use |
|--------|--------|------------|----------|-------------|
| Submit | `action_submit()` | Draft | Submitted | Tenant, Saqifa |
| Under Review | `action_under_review()` | Submitted | Under Review | Saqifa |
| Create Job Order | `action_create_job_order()` | Under Review | Job Ordered | Saqifa |
| Cancel | `action_cancel()` | Any (except Closed) | Cancelled | Tenant, Saqifa |
| Reopen | `action_reopen()` | Cancelled | Draft | Saqifa |

### Required Fields

| # | Field | Technical Name | Type | Required | Default |
|---|-------|----------------|------|----------|---------|
| 1 | Request Reference | `name` | Char | Yes | MR#### (auto) |
| 2 | Ordered By | `partner_id` | Many2one (tenant) | Yes | - |
| 3 | Unit / Area | `x_unit_area` | Many2one (sub.property) | **No** | - |
| 4 | Building | `x_building_id` | Many2one (computed) | No | Auto from unit |
| 5 | Request Date | `request_date` | Datetime | Yes | Now |
| 6 | Request Type | `x_request_type` | Selection | Yes | **'general'** |
| 7 | Priority | `priority` | Selection | Yes | 'normal' |
| 8 | Description | `description` | Text | Yes | - |
| 9 | Status | `x_status` | Selection | Yes | 'draft' |

**Note:** Fields marked with **bold** have been updated to fix validation issues:
- `x_unit_area`: Changed from required=True to required=False (allows portal submissions without unit)
- `x_request_type`: Added default='general' to prevent mandatory field errors

### Request Types

- `electrical` - Electrical Issues
- `mechanical` - Mechanical Issues  
- `low_current` - Low Current Systems
- `civil` - Civil/Structural
- `general` - General Maintenance (default)
- `other` - Other Issues

### Priority Levels

- `low` - Low Priority
- `normal` - Normal Priority (default)
- `high` - High Priority
- `urgent` - Urgent Priority

---

## Maintenance Job Order Workflow (FR-2)

### States & Transitions

```
Draft → Sent to Contractor → In Progress → Completed by Contractor → 
Pending Supervisor Approval → Pending Tenant Approval → Closed → Cancelled
```

### State Details

| State | Code | Description | Who Updates |
|-------|------|-------------|-------------|
| Draft | `draft` | Job order created from request | System |
| Sent to Contractor | `sent_to_contractor` | Assigned to contractor | Saqifa |
| In Progress | `in_progress` | Work has started | Contractor/Saqifa |
| Completed by Contractor | `completed_by_contractor` | Work finished | Contractor/Saqifa |
| Pending Supervisor Approval | `pending_supervisor_approval` | Awaiting Saqifa admin approval | Saqifa Admin |
| Pending Tenant Approval | `pending_tenant_approval` | Awaiting tenant sign-off | Tenant |
| Closed | `closed` | Job fully completed | Saqifa |
| Cancelled | `cancelled` | Job cancelled | Any |

### Buttons & Actions

| Button | Method | From State | To State | Validation | Who |
|--------|--------|------------|----------|------------|-----|
| Send to Contractor | `action_send_to_contractor()` | Draft | Sent to Contractor | Contractor assigned | Saqifa |
| Start Progress | `action_start_progress()` | Sent to Contractor | In Progress | - | Contractor/Saqifa |
| Complete | `action_complete_by_contractor()` | In Progress | Completed by Contractor | - | Contractor/Saqifa |
| Supervisor Approval | `action_approve_job_order()` | Completed by Contractor | Pending Supervisor Approval | Admin group only | **Saqifa Admin** |
| Tenant Approval | `action_tenant_approval()` | Pending Supervisor Approval | Pending Tenant Approval | - | Tenant/Saqifa |
| Close Job Order | `action_close_job_order()` | Pending Tenant/Supervisor Approval | Closed | - | Saqifa |
| Cancel | `action_cancel()` | Any (except Closed) | Cancelled | - | Any |

### Field Groups

#### A. Header Information (14 fields)

| Field | Technical Name | Auto-Filled From Request |
|-------|----------------|-------------------------|
| Job Order # | `name` | No - DD/MM/YY/#### format |
| Job Order Date | `date` | No - Today |
| Linked Tenant Request | `maintenance_request_id` | Yes |
| Unit / Area | `x_unit_area` | Yes |
| Ordered By | `ordered_by_id` | Yes - from partner_id |
| Mobile | `ordered_mobile` | Yes - computed |
| E-mail | `ordered_email` | Yes - computed |
| Job Logged By | `job_logged_by` | Yes - from x_job_logged_by |
| Job Assigned To (Contractor) | `assigned_contractor_id` | No - Manual |
| Job Assigned Time | `job_assigned_datetime` | No - Auto on send |
| Type of Job | `job_type` | Yes - **Mapped from request_type** |
| Priority | `priority` | Yes |
| Company | `x_company_id` | Yes |
| Status | `state` | No - 'draft' |

**Request Type to Job Type Mapping:**
```python
'electrical' → 'fault'
'mechanical' → 'fault'
'low_current' → 'fault'
'civil' → 'fault'
'general' → 'new'
'other' → 'other'
```

#### B. Job Description & Execution (6 fields)

- `job_reference` - Internal reference
- `job_description` - Detailed work order (auto-filled from request description)
- `technician_id` - Technician name
- `corrective_action` - What was done
- `additional_resources` - Extra manpower/equipment needed
- `requested_material_text` - Materials summary

#### C. Contractor Supervisor & Tenant Sign-off (8 fields)

**Supervisor Section:**
- `supervisor_remarks` - Post-work comments
- `supervisor_id` - Supervisor name
- `supervisor_signature` - Digital signature
- `supervisor_sign_datetime` - Sign timestamp

**Tenant Section:**
- `tenant_remarks` - Tenant's feedback
- `tenant_manager_id` - Tenant/Manager
- `tenant_signature` - Digital signature  
- `tenant_sign_datetime` - Sign timestamp

#### D. Job Completion Confirmation (5 fields)

- `job_start_datetime` - When work started
- `job_end_datetime` - When work completed
- `manager_name` - Saqifa manager
- `manager_signature` - Manager signature
- `manager_sign_date` - Sign date

---

## Workflow Connections

### How Maintenance Request Links to Job Order

1. **Creation Link:**
   ```python
   # When Saqifa clicks "Create Job Order" on maintenance request
   maintenance_request.action_create_job_order()
   
   # Creates job_order with:
   job_order = {
       'maintenance_request_id': request.id,  # Link back
       'x_unit_area': request.x_unit_area.id,
       'ordered_by_id': request.partner_id.id,
       'job_type': mapped_from_request_type,
       'priority': request.priority,
       'job_description': request.description,
       # ... other fields
   }
   
   # Updates request:
   request.x_status = 'job_ordered'
   request.x_job_order_id = job_order.id
   ```

2. **State Synchronization:**

| Job Order State | Updates Maintenance Request To |
|-----------------|-------------------------------|
| `sent_to_contractor` | `in_progress` |
| `pending_tenant_approval` | `approved_by_tenant` |
| `closed` | `closed` |

3. **Computed Fields:**
   - `x_job_assigned_to` (on request) → Computed from `job_order.assigned_contractor_id`
   - This shows contractor info on the request automatically

---

## Approval Workflow (FR-7)

### Supervisor Approval
- **Who:** Saqifa Admin users only (base.group_system)
- **When:** After contractor completes work
- **Requirements:** Job state must be 'completed_by_contractor'
- **Captures:** 
  - Supervisor name
  - Signature
  - Timestamp
  - Manager details

### Tenant Approval
- **Who:** Tenant or Saqifa staff
- **When:** After supervisor approval
- **Requirements:** State must be 'pending_supervisor_approval'
- **Captures:**
  - Tenant/Manager
  - Signature
  - Timestamp

### Final Closure
- **Who:** Saqifa
- **When:** After approvals
- **Can close from:** 
  - `pending_tenant_approval` (normal flow)
  - `pending_supervisor_approval` (if tenant approval not needed)

---

## Cancellation Workflow (FR-8)

### Who Can Cancel
- **Maintenance Request:** Tenant or Saqifa
- **Job Order:** Saqifa, Contractor, or Tenant

### When Can Cancel
- **Any time except:** Request/Job is already `closed`

### Cancellation Process

1. Click "Cancel" button
2. Wizard opens requiring cancellation reason
3. Reason saved to `cancellation_reason` field
4. State changes to `cancelled`
5. Message posted to chatter with reason

### Reopening Cancelled Requests
- Only maintenance requests can be reopened
- Changes state back to `draft`
- Clears cancellation reason
- Available to Saqifa only

---

## Portal Integration

### Tenant Portal
- **Route:** `/my/rental_contract/<id>/maintenance_request`
- **Can:** Create maintenance requests
- **Fields shown:** All required fields
- **Default values:**
  - `partner_id` → Current portal user's partner
  - `x_status` → 'draft'
  - `priority` → 'normal'
  - `x_request_type` → 'general'
  - `request_date` → Now

### Contractor Portal
- **Not implemented yet** (FR-2 specifies "no contractor portal")
- Contractors interact through Saqifa staff

---

## Common Issues & Solutions

### Issue 1: "Mandatory field not set - x_request_type"
**Cause:** Field was required but no default value
**Solution:** Added `default='general'` to field definition + removed DB constraint

### Issue 2: "Mandatory field not set - x_unit_area"
**Cause:** Portal submissions might not have unit
**Solution:** Changed `required=False` + removed DB constraint

### Issue 3: Cannot create job order
**Cause:** Unit area must be set
**Validation:** Added check in `action_create_job_order()` to require unit before creating job

### Issue 4: Job order buttons not appearing
**Cause:** State-based visibility + group restrictions
**Solution:** Check user has `base.group_system` for supervisor approval

---

## Sequence Formats

### Maintenance Request
- **Format:** `MR####`
- **Example:** MR0001, MR0002, MR0003
- **Sequence:** `rental.maintenance.request`

### Job Order
- **Format:** `DD/MM/YY/####`
- **Example:** 16/12/25/0001
- **Logic:** Date prefix + 4-digit number
- **Sequence:** `maintenance.job.order`

---

## Database Schema

### Key Relationships

```sql
-- Maintenance Request → Job Order (One-to-One)
rental_maintenance_request.x_job_order_id → maintenance_job_order.id

-- Job Order → Maintenance Request (One-to-One)
maintenance_job_order.maintenance_request_id → rental_maintenance_request.id

-- Request → Tenant
rental_maintenance_request.partner_id → res_partner.id (is_tenant=True)

-- Request → Unit
rental_maintenance_request.x_unit_area → sub_property.id

-- Request → Building (computed)
rental_maintenance_request.x_building_id → rs_project.id (via unit)

-- Job Order → Contractor
maintenance_job_order.assigned_contractor_id → res_partner.id (is_company=True)
```

---

## Testing Checklist

### Maintenance Request Flow
- [ ] Create request from tenant portal
- [ ] Submit request
- [ ] Move to under review
- [ ] Create job order (validates unit required)
- [ ] Verify job order created with correct data
- [ ] Verify request state = 'job_ordered'
- [ ] Cancel request with reason
- [ ] Reopen cancelled request

### Job Order Flow
- [ ] Send job order to contractor (validates contractor assigned)
- [ ] Verify request state = 'in_progress'
- [ ] Start progress
- [ ] Complete by contractor
- [ ] Supervisor approval (admin only)
- [ ] Tenant approval
- [ ] Verify request state = 'approved_by_tenant'
- [ ] Close job order
- [ ] Verify request state = 'closed'

### Cancellation
- [ ] Cancel job order with reason
- [ ] Verify cannot cancel closed job
- [ ] Cancel request from tenant portal
- [ ] Verify reason saved correctly

---

## Code References

### Models
- **File:** `/nthub_realestate/models/rental_maintenance.py`
- **Lines:**
  - RentalMaintenanceRequest: 1-180
  - MaintenanceJobOrder: 280-600
  - Wizards: 250-280, 590-600

### Views
- **File:** `/nthub_realestate/views/maintenance_views.xml`
- **Includes:**
  - Maintenance request form/tree
  - Job order form/tree
  - Wizard forms

### Security
- **File:** `/nthub_realestate/security/ir.model.access.csv`
- **Access Rules:**
  - rental.maintenance.request → All users
  - maintenance.job.order → All users
  - Wizards → All users

---

## API Methods Summary

### RentalMaintenanceRequest

```python
# State Transitions
action_submit() - Draft → Submitted
action_under_review() - Submitted → Under Review
action_create_job_order() - Under Review → Job Ordered (creates job order)
action_cancel() - Any → Cancelled (opens wizard)
action_reopen() - Cancelled → Draft

# Computed Fields
_compute_job_assigned_to() - Reads from linked job order
```

### MaintenanceJobOrder

```python
# State Transitions
action_send_to_contractor() - Draft → Sent to Contractor (updates request)
action_start_progress() - Sent → In Progress
action_complete_by_contractor() - In Progress → Completed
action_approve_job_order() - Completed → Pending Supervisor (admin only)
action_tenant_approval() - Pending Supervisor → Pending Tenant (updates request)
action_close_job_order() - Pending * → Closed (closes request)
action_cancel() - Any → Cancelled (opens wizard)

# Sequence
create() - Generates DD/MM/YY/#### format
```

---

## Change Log

### 2025-12-16
- ✅ Fixed `x_request_type` mandatory field error (added default='general')
- ✅ Removed DB NOT NULL constraint on `x_request_type`
- ✅ Improved workflow state transitions
- ✅ Added validation for unit area before job order creation
- ✅ Enhanced supervisor approval with manager signature capture
- ✅ Fixed tenant approval workflow validation
- ✅ Updated request status when job order state changes
- ✅ Created comprehensive workflow documentation

---

## Support & Maintenance

### Common Admin Tasks

1. **View all pending requests:**
   ```sql
   SELECT name, partner_id, x_status, request_date 
   FROM rental_maintenance_request 
   WHERE x_status IN ('submitted', 'under_review') 
   ORDER BY priority DESC, request_date;
   ```

2. **Find requests without job orders:**
   ```sql
   SELECT name, x_status 
   FROM rental_maintenance_request 
   WHERE x_status = 'job_ordered' AND x_job_order_id IS NULL;
   ```

3. **Check job order completion rate:**
   ```sql
   SELECT state, COUNT(*) 
   FROM maintenance_job_order 
   GROUP BY state;
   ```

### Performance Optimization
- Indexes exist on: `x_status`, `state`, `partner_id`, `maintenance_request_id`
- Use `store=True` on computed fields for faster searches
- Archive old closed requests/jobs to improve query performance

---

**Last Updated:** December 16, 2025  
**Module Version:** 1.0  
**Odoo Version:** 18.0
