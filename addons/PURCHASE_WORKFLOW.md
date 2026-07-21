# Purchase Workflow - Job Order Material Purchases

## Complete Workflow Flow

### Step 1: Add Materials to Purchase (In Job Order)
- In Job Order form, go to "Materials to Purchase" tab
- Click "Add a line"
- Select Product (e.g., [EXP_GEN] Expenses)
- Enter Purchase Qty
- Enter Supplier/Vendor
- **Line State**: `draft`

### Step 2: Create PO Request (From Job Order)
**Option A: Create individual POs** (Not yet implemented - Phase 4)
- In Materials to Purchase list, click the line
- Click "Request Approval"
- **Line State**: `approval_requested`

### Step 3: Approve & Create Purchase Order (From Purchase Line Form)
- Open the purchase line form
- Click **"Approve & Create PO"** button (highlighted in yellow/orange)
- System automatically:
  1. Creates a Purchase Order with the material details
  2. Confirms the PO (state becomes 'purchase')
  3. Links the PO back to the purchase line
  4. Updates purchase line state to `po_created`
  5. Posts message in job order chatter showing PO created
- **Line State**: `po_created`

### Step 4: Receive Materials (In Purchase Order)
- Once the supplier delivers, use standard Odoo Purchase → Receive workflow
- Create Inbound Picking
- Validate receipt
- **Purchase Line State**: Automatically updates to `received`

### Step 5: Complete Job Order
- Go back to Job Order
- Click **"Completed by Contractor"** button
- System validates:
  - All issued materials are accounted for (state: issued/returned/cancelled)
  - All purchase materials are accounted for (state: draft/approval_requested/approved/po_created/received/cancelled)
- If valid: Opens confirmation wizard showing material summary
- Click "Confirm Completion" to finalize

## Valid States for Job Completion

### Material Issue Lines (Material Issuance)
✅ **Valid for completion**:
- `issued` - Materials issued from warehouse
- `returned` - Materials returned to warehouse
- `cancelled` - Issuance cancelled

❌ **Blocks completion**:
- `draft` - Not yet issued

### Material Purchase Lines (Material Purchases)
✅ **Valid for completion**:
- `draft` - No approval needed (optional workflow)
- `approval_requested` - Approval requested, awaiting decision
- `approved` - Approved, ready for PO
- `po_created` - PO created and confirmed
- `received` - Materials received
- `cancelled` - Purchase cancelled

## Linking Back to Job Order

When a PO is created via "Approve & Create PO":

```
Job Order (maintenance.job.order)
  ↓
  Material Purchase Line (maintenance.job.purchase.line)
    ↓
    Purchase Order Line (purchase.order.line) ← purchase_line_id
      ↓
      Purchase Order (purchase.order) ← purchase_order_id
```

The linking is automatic:
- When you click "Approve & Create PO", a PO is created
- The purchase line is linked via `purchase_line_id` field
- The job order is linked via `purchase_order_id` field
- All messages are posted in job order chatter for audit trail

## Messages in Chatter

Each action posts a message showing what happened:

1. **Purchase request created**: "Purchase request created for [Product Name] (Qty: X Units). Awaiting approval."
2. **PO created**: "Purchase order created and confirmed for [Product Name]. PO: [PO#]. Status: PO Created"
3. **Job completed**: "Job completed and confirmed. Issued Materials: X. Purchased Materials: Y. Returned Materials: Z. Notes: ..."

## Key Differences from Old Flow

| Step | Old Flow | New Flow |
|------|----------|----------|
| Create Purchase | Manual PO creation required | Automatic PO creation via button |
| Link to Job | Manual linking | Automatic linking via purchase line |
| Track Status | Manual state updates | Automatic state transitions |
| Validation | No validation | Job completion validates all materials |
| Audit Trail | No messages | Full chatter history |

## Error Messages

### When Job Completion is Blocked

**"Cannot complete job order. There are X pending material issue(s). All materials must be issued, returned, or cancelled first."**
- Solution: Issue or return any draft material issues

**"Cannot complete job order. There are X invalid purchase line(s). All purchases must be in valid states."**
- Solution: Approve and create PO for all draft purchases OR cancel them

---

## Testing Checklist

- [ ] Add material to purchase line in job order
- [ ] Open purchase line form
- [ ] Click "Approve & Create PO"
- [ ] Verify PO is created and appears in purchase_order_id field
- [ ] Verify PO is confirmed (check in Purchase module)
- [ ] Go back to job order
- [ ] Click "Completed by Contractor"
- [ ] Verify wizard opens showing material summary
- [ ] Click "Confirm Completion"
- [ ] Verify job order state changes to "completed_by_contractor"
- [ ] Check chatter for completion message with material counts

