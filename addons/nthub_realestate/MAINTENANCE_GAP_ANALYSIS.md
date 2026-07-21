# Maintenance System - Gap Analysis & Implementation Plan

## Current System Status ✅ vs Missing ❌

### 1. Maintenance Request Model (`rental.maintenance.request`)

| Field | Status | Notes |
|-------|--------|-------|
| name (MR####) | ✅ Complete | Sequence working |
| partner_id | ✅ Complete | Tenant selection |
| x_unit_area | ✅ Complete | Optional field |
| x_building_id | ✅ Complete | Computed from unit |
| x_tenant_mobile | ✅ Complete | Related field |
| x_tenant_email | ✅ Complete | Related field |
| request_date | ✅ Complete | Auto-filled |
| x_request_type | ✅ Complete | With default='general' |
| priority | ✅ Complete | 4 levels |
| description | ✅ Complete | Required text |
| attachment_ids | ✅ Complete | Using chatter |
| x_status | ✅ Complete | 8 states |
| x_job_assigned_to | ✅ Complete | Computed from job order |
| x_job_assigned_time | ✅ Complete | Set on job creation |
| x_job_logged_by | ✅ Complete | Current user |
| x_job_order_id | ✅ Complete | Link to job order |
| cancellation_reason | ✅ Complete | Text field |
| company_id | ✅ Complete | Multi-company |

**Workflow Buttons:**
- ✅ Submit Request → Changes state to 'submitted'
- ✅ Under Review → Changes state to 'under_review'
- ✅ Create Job Order → Creates job order + changes to 'job_ordered'
- ✅ Cancel → Opens wizard for cancellation
- ✅ Reopen → Returns to draft

**State Transitions:**
- ✅ Draft → Submitted → Under Review → Job Ordered → In Progress → Approved by Tenant → Closed
- ✅ Any → Cancelled (except Closed)

---

### 2. Job Order Model (`maintenance.job.order`)

#### A. Header Information (17 fields)

| Field | Status | Notes |
|-------|--------|-------|
| name (DD/MM/YY/####) | ✅ Complete | Date-based sequence |
| date | ✅ Complete | Today |
| maintenance_request_id | ✅ Complete | Link back |
| x_unit_area | ✅ Complete | From request |
| ordered_by_id | ✅ Complete | Tenant |
| ordered_mobile | ✅ Complete | Related |
| ordered_email | ✅ Complete | Related |
| job_logged_by | ✅ Complete | Current user |
| assigned_contractor_id | ✅ Complete | Manual assignment |
| job_assigned_datetime | ✅ Complete | Set on send |
| job_type | ✅ Complete | 4 types |
| job_type_other | ✅ Complete | Conditional |
| priority | ✅ Complete | From request |
| x_company_id | ✅ Complete | Multi-company |
| state | ✅ Complete | 8 states |
| cancellation_reason | ✅ Complete | Text field |

#### B. Job Description & Execution (6 fields)

| Field | Status | Notes |
|-------|--------|-------|
| job_reference | ✅ Complete | Internal ref |
| job_description | ✅ Complete | From request |
| technician_id | ✅ Complete | Text field |
| corrective_action | ✅ Complete | What was done |
| additional_resources | ✅ Complete | Extra needs |
| requested_material_text | ✅ Complete | Summary field |

#### C. Contractor Supervisor & Tenant Sign-off (8 fields)

| Field | Status | Notes |
|-------|--------|-------|
| supervisor_remarks | ✅ Complete | Post-work comments |
| supervisor_id | ✅ Complete | Supervisor name |
| supervisor_signature | ✅ Complete | Binary field |
| supervisor_sign_datetime | ✅ Complete | Timestamp |
| tenant_remarks | ✅ Complete | Tenant feedback |
| tenant_manager_id | ✅ Complete | Many2one |
| tenant_signature | ✅ Complete | Binary field |
| tenant_sign_datetime | ✅ Complete | Timestamp |

#### D. Job Completion Confirmation (5 fields)

| Field | Status | Notes |
|-------|--------|-------|
| job_start_datetime | ✅ Complete | Work started |
| job_end_datetime | ✅ Complete | Work completed |
| manager_name | ✅ Complete | Saqifa manager |
| manager_signature | ✅ Complete | Binary field |
| manager_sign_date | ✅ Complete | Date field |

**Backend Workflow Buttons:**
- ✅ Send to Contractor → State: 'sent_to_contractor'
- ❌ Issue Materials → **MISSING** (No stock integration)
- ✅ Cancel → Opens wizard
- ❌ Purchase Approval Request → **MISSING** (No purchase workflow)
- ✅ Tenant Approval → State: 'pending_tenant_approval'
- ✅ Supervisor Approval → State: 'pending_supervisor_approval' (admin only)
- ✅ Close Job Order → State: 'closed'

**State Transitions:**
- ✅ Basic workflow implemented
- ✅ Updates linked maintenance request
- ✅ Validation on state changes

---

### 3. Material Management ❌ **COMPLETELY MISSING**

#### E-1: Contractor Material Request Lines (`maintenance.job.request.line`)

| Field | Status | Implementation Needed |
|-------|--------|----------------------|
| job_order_id | ❌ Missing | Link to job order |
| description_text | ❌ Missing | Free-text material request |
| requested_qty | ❌ Missing | Quantity needed |
| requested_uom_id | ❌ Missing | Unit of measure |
| remark | ❌ Missing | Contractor notes |
| attachment_ids | ❌ Missing | Specs/photos |
| type_of_material | ❌ Missing | Selection field |
| request_priority | ❌ Missing | Selection field |

**Missing Methods:**
- ❌ Contractor portal submission
- ❌ Validation logic
- ❌ Notification to inventory team

#### E-2: Issued Materials from Stock (`maintenance.job.issue.line`)

| Field | Status | Implementation Needed |
|-------|--------|----------------------|
| job_order_id | ❌ Missing | Link to job order |
| product_id | ❌ Missing | Odoo product |
| name | ❌ Missing | Custom description |
| issue_qty | ❌ Missing | Quantity issued |
| uom_id | ❌ Missing | Unit of measure |
| serial_no | ❌ Missing | Serial/Lot tracking |
| remark | ❌ Missing | Issue notes |
| move_id | ❌ Missing | **Stock move link** |

**Missing Integration:**
- ❌ Stock picking creation
- ❌ Warehouse → Job location movement
- ❌ Serial/lot tracking
- ❌ Inventory valuation
- ❌ Automatic update to contractor portal

#### E-3: Materials to Purchase (`maintenance.job.purchase.line`)

| Field | Status | Implementation Needed |
|-------|--------|----------------------|
| job_order_id | ❌ Missing | Link to job order |
| product_id | ❌ Missing | Product selection |
| description_text | ❌ Missing | RFQ/PO description |
| purchase_qty | ❌ Missing | Quantity to buy |
| received_quantities_po | ❌ Missing | Received qty |
| uom_id | ❌ Missing | Purchase UOM |
| supplier_id | ❌ Missing | Vendor selection |
| target_date | ❌ Missing | Expected date |
| remark | ❌ Missing | Purchase notes |
| purchase_line_id | ❌ Missing | **PO line link** |

**Missing Integration:**
- ❌ RFQ/PO creation
- ❌ Approval workflow integration
- ❌ Purchase order linking
- ❌ Receipt tracking
- ❌ Automatic contractor portal update

---

### 4. Contractor Portal ❌ **COMPLETELY MISSING**

#### Missing Components:

**A. Contractor User Group & Access:**
- ❌ Contractor portal group not defined
- ❌ Security rules for contractor access
- ❌ Contractor-specific views/menus

**B. Contractor Routes:**
- ❌ `/my/contractor/jobs` - List assigned jobs
- ❌ `/my/contractor/job/<id>` - Job detail view
- ❌ `/my/contractor/job/<id>/start` - Start work
- ❌ `/my/contractor/job/<id>/request_materials` - Material request form
- ❌ `/my/contractor/job/<id>/complete` - Mark completed
- ❌ `/my/contractor/job/<id>/supervisor_approval` - Request approval

**C. Contractor Portal Features:**
| Feature | Status | Notes |
|---------|--------|-------|
| View assigned jobs | ❌ Missing | List view with filters |
| See job details | ❌ Missing | Unit, tenant, priority |
| Start work button | ❌ Missing | Updates state + timestamp |
| Request materials form | ❌ Missing | Free-text + qty + attachments |
| View issued materials | ❌ Missing | Read-only table |
| View purchased materials | ❌ Missing | Read-only table |
| Enter corrective action | ❌ Missing | Text field |
| Digital signature | ❌ Missing | Supervisor signature widget |
| Complete work | ❌ Missing | Updates state + end time |
| Cancel job | ❌ Missing | With reason |

**D. Contractor Notifications:**
- ❌ Email on job assignment
- ❌ Email when materials issued
- ❌ Email when materials purchased
- ❌ Portal banner notifications

---

### 5. Tenant Portal for Job Orders ❌ **PARTIALLY MISSING**

#### Current Tenant Portal:
- ✅ Create maintenance request
- ✅ View maintenance requests
- ✅ See request status

#### Missing Tenant Features:
| Feature | Status | Notes |
|---------|--------|-------|
| View linked job order | ❌ Missing | See job order details from request |
| Track job progress | ❌ Missing | Timeline/status updates |
| View assigned contractor | ❌ Missing | Show contractor name |
| Digital approval signature | ❌ Missing | Sign-off on completion |
| Rate/feedback on job | ❌ Missing | Optional satisfaction rating |
| Cancel request (with reason) | ❌ Missing | Self-service cancellation |

**Missing Routes:**
- ❌ `/my/maintenance_request/<id>/job_order` - View job order
- ❌ `/my/maintenance_request/<id>/approve` - Tenant approval form
- ❌ `/my/maintenance_request/<id>/cancel` - Cancellation form

---

### 6. Workflow Integration ❌ **MAJOR GAPS**

#### State Synchronization:
| From | To | Status | Notes |
|------|----|----|-------|
| Request: under_review | Job: draft | ✅ Working | Job order creation |
| Job: sent_to_contractor | Request: in_progress | ✅ Working | Implemented |
| Job: completed_by_contractor | Request: (no change) | ⚠️ Partial | Should notify tenant |
| Job: pending_tenant_approval | Request: approved_by_tenant | ✅ Working | Updates request |
| Job: closed | Request: closed | ✅ Working | Final closure |

#### Missing Workflow Logic:
- ❌ **Material workflow**: Request → Issue → Track → Complete
- ❌ **Purchase workflow**: Identify need → RFQ → PO → Receive → Link to job
- ❌ **Approval chain**: Contractor → Supervisor → Tenant → Manager
- ❌ **Notification system**: Email alerts on state changes
- ❌ **SLA tracking**: Time limits, overdue alerts
- ❌ **Automated transitions**: Auto-close after X days, escalations

---

### 7. Stock Integration ❌ **NOT IMPLEMENTED**

**Missing Components:**
- ❌ Stock picking creation from "Issue Materials" button
- ❌ Source location: Main Warehouse
- ❌ Destination location: Job site / Virtual location
- ❌ Stock move validation
- ❌ Serial/lot tracking for issued items
- ❌ Return unused materials workflow
- ❌ Inventory adjustment on job completion
- ❌ Cost tracking per job order

**Required Models:**
- ❌ `stock.picking` integration
- ❌ `stock.move` creation
- ❌ `stock.location` for job sites
- ❌ Valuation layer tracking

---

### 8. Purchase Integration ❌ **NOT IMPLEMENTED**

**Missing Components:**
- ❌ RFQ creation from "Purchase Approval Request" button
- ❌ Link purchase lines to job order
- ❌ Approval workflow for purchases
- ❌ PO creation after approval
- ❌ Receipt tracking
- ❌ Update job order when goods received
- ❌ Cost allocation to job order
- ❌ Vendor performance tracking

**Required Models:**
- ❌ `purchase.requisition` or custom approval
- ❌ `purchase.order` linking
- ❌ `purchase.order.line` tracking
- ❌ Receipt → Job order updates

---

### 9. Views & UI ✅ **BASIC VIEWS COMPLETE**

#### Maintenance Request Views:
- ✅ Form view with statusbar
- ✅ Tree view
- ✅ Tenant portal view
- ❌ Kanban view (optional)
- ❌ Calendar view (by request date)
- ❌ Pivot/graph views for reporting

#### Job Order Views:
- ✅ Form view with statusbar
- ✅ Tree view
- ✅ Cancellation wizard
- ❌ **Material tabs missing** (3 tables)
- ❌ Contractor portal views
- ❌ Tenant approval view
- ❌ Timeline/Gantt view

---

### 10. Security & Access Rights ✅ **BASIC ACCESS COMPLETE**

#### Current Access:
- ✅ All users: CRUD on maintenance requests
- ✅ All users: CRUD on job orders
- ✅ Portal tenants: Create/view own requests

#### Missing Access Controls:
- ❌ Contractor group definition
- ❌ Contractor portal access rules
- ❌ Restrict job order editing by state
- ❌ Supervisor approval: admin only (already implemented)
- ❌ Material issuance: inventory group only
- ❌ Purchase approval: purchase manager only
- ❌ Record rules for contractors (see only assigned jobs)

---

## Priority Implementation Plan

### Phase 1: Material Management (HIGH PRIORITY)
1. ✅ Create `maintenance.job.request.line` model
2. ✅ Create `maintenance.job.issue.line` model
3. ✅ Create `maintenance.job.purchase.line` model
4. ✅ Add O2M fields to job order
5. ✅ Create form views with notebook tabs
6. ✅ Implement basic CRUD operations

### Phase 2: Stock Integration (HIGH PRIORITY)
1. ❌ Implement "Issue Materials" button
2. ❌ Create stock picking on issue
3. ❌ Link stock moves to issue lines
4. ❌ Add serial/lot tracking
5. ❌ Update contractor portal on issue

### Phase 3: Purchase Integration (MEDIUM PRIORITY)
1. ❌ Implement "Purchase Approval Request" button
2. ❌ Create approval request record
3. ❌ Link to Odoo Approval module (if installed)
4. ❌ Create PO from approved request
5. ❌ Track receipts and update job order

### Phase 4: Contractor Portal (MEDIUM PRIORITY)
1. ❌ Create contractor security group
2. ❌ Create contractor portal controllers
3. ❌ Implement job list view
4. ❌ Implement job detail view
5. ❌ Add material request form
6. ❌ Add start/complete/approval buttons
7. ❌ Implement signature widgets

### Phase 5: Tenant Portal Enhancements (LOW PRIORITY)
1. ❌ Add job order view from request
2. ❌ Add tenant approval form with signature
3. ❌ Add cancellation self-service
4. ❌ Add progress tracking timeline

### Phase 6: Workflow Automation (LOW PRIORITY)
1. ❌ Implement email notifications
2. ❌ Add SLA tracking
3. ❌ Create automated transitions
4. ❌ Add escalation logic

### Phase 7: Reporting & Analytics (LOW PRIORITY)
1. ❌ Add kanban/calendar views
2. ❌ Create dashboards
3. ❌ Add pivot reports
4. ❌ Implement KPIs

---

## Immediate Action Items

### Must Implement NOW:
1. ✅ **Material Line Models** - All 3 tables
2. ✅ **Material Tabs in Job Order Form** - Notebook with 3 pages
3. ❌ **"Issue Materials" Button** - Stock picking integration
4. ❌ **"Purchase Approval Request" Button** - Basic workflow

### Can Implement Later:
- Contractor portal (requires significant development)
- Advanced approval workflows
- SLA tracking
- Automated notifications
- Reporting dashboards

---

## Technical Debt & Limitations

### Current System Issues:
1. ✅ **FIXED**: x_request_type mandatory field error
2. ✅ **FIXED**: x_unit_area optional for portal submissions
3. ⚠️ **Remaining**: No stock integration
4. ⚠️ **Remaining**: No purchase integration
5. ⚠️ **Remaining**: No contractor portal
6. ⚠️ **Remaining**: Limited tenant portal features

### Breaking Changes Needed:
- None - all additions are backward compatible

### Migration Required:
- None - existing data will work with new fields

---

## Summary

**Completion Status: 60%**

✅ **Complete:**
- Maintenance request model & workflow
- Job order model & basic workflow  
- Tenant portal (create/view requests)
- Basic approval workflow
- State transitions
- Cancellation workflow

❌ **Missing:**
- Material management (0%)
- Stock integration (0%)
- Purchase integration (0%)
- Contractor portal (0%)
- Enhanced tenant portal (30%)
- Workflow automation (0%)

**Next Steps:**
1. Implement material line models
2. Add material tabs to job order form
3. Implement stock picking on "Issue Materials"
4. Create basic purchase request workflow
5. Plan contractor portal architecture

---

**Document Version:** 1.0  
**Last Updated:** December 16, 2025  
**Status:** Ready for Phase 1 Implementation
