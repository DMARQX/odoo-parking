from odoo import models, fields, api

class MaintenanceJobPurchaseLine(models.Model):
    """E-3: Materials to Purchase (RFQ/PO tracking)"""
    _name = 'maintenance.job.purchase.line'
    _description = 'Job Order Purchase Materials Line'

    job_order_id = fields.Many2one('maintenance.job.order', string="Job Order", required=True, ondelete='cascade')
    request_line_id = fields.Many2one('maintenance.job.request.line', string="Request Line", ondelete='set null')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', string="UOM", related='product_id.uom_id', readonly=True)
    supplier_id = fields.Many2one('res.partner', string="Supplier", domain=[('supplier_rank', '>', 0)])
    target_date = fields.Date(string="Target Date")
    purchase_line_id = fields.Many2one('purchase.order.line', string="PO Line", readonly=True)
    received_quantities_po = fields.Float(string="Received Quantities (PO)", readonly=True)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('rfq_sent', 'RFQ Sent'),
        ('po_confirmed', 'PO Confirmed'),
        ('received', 'Received')
    ], string="Status", default='pending')
    notes = fields.Text(string="Notes")

    @api.depends('purchase_line_id', 'purchase_line_id.qty_received')
    def _compute_received_quantities(self):
        """Compute received quantities from linked PO line"""
        for line in self:
            if line.purchase_line_id:
                line.received_quantities_po = line.purchase_line_id.qty_received
                # Update status based on received quantity
                if line.received_quantities_po >= line.quantity:
                    line.status = 'received'
                elif line.purchase_line_id.order_id.state == 'purchase':
                    line.status = 'po_confirmed'
            else:
                line.received_quantities_po = 0.0

    received_quantities_po = fields.Float(
        string="Received Quantities (PO)", 
        compute='_compute_received_quantities',
        store=True,
        readonly=True
    )
