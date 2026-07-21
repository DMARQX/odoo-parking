from odoo import models, fields, api

class MaintenanceJobRequestLine(models.Model):
    """E-1: Contractor Input - Requested Materials"""
    _name = 'maintenance.job.request.line'
    _description = 'Job Order Material Request Line'

    job_order_id = fields.Many2one('maintenance.job.order', string="Job Order", required=True, ondelete='cascade')
    description = fields.Char(string="Description of Material", required=True)
    quantity = fields.Float(string="Quantity", default=1.0)
    uom_id = fields.Many2one('uom.uom', string="UOM")
    type_of_material = fields.Selection([
        ('stock', 'From Stock'),
        ('purchase', 'To Be Purchased')
    ], string="Type of Material", required=True, default='stock')
    request_priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string="Request Priority", default='normal')
    
    # Link to issued/purchased materials
    issue_line_ids = fields.One2many('maintenance.job.issue.line', 'request_line_id', string="Issued Materials")
    purchase_line_ids = fields.One2many('maintenance.job.purchase.line', 'request_line_id', string="Purchase Lines")
    
    reception_status = fields.Selection([
        ('pending', 'Pending'),
        ('received_from_stock', 'Received from Stock'),
        ('received_from_supplier', 'Received from Supplier')
    ], string="Reception Status / حالة الاستلام", compute='_compute_reception_status', store=True, readonly=False)
    
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    notes = fields.Text(string="Notes")
    
    @api.depends('issue_line_ids', 'issue_line_ids.move_id', 
                 'purchase_line_ids', 'purchase_line_ids.purchase_line_id',
                 'purchase_line_ids.received_quantities_po', 'purchase_line_ids.quantity')
    def _compute_reception_status(self):
        """Compute reception status based on issued materials or purchase orders"""
        for line in self:
            # Check if material was issued from stock (has stock move)
            if line.issue_line_ids and any(issue.move_id for issue in line.issue_line_ids):
                line.reception_status = 'received_from_stock'
            # Check if material was purchased AND fully received (quantity >= received)
            elif line.purchase_line_ids:
                # Check if ALL purchase lines are fully received
                all_received = all(
                    purchase.purchase_line_id and 
                    purchase.received_quantities_po >= purchase.quantity
                    for purchase in line.purchase_line_ids
                )
                if all_received and len(line.purchase_line_ids) > 0:
                    line.reception_status = 'received_from_supplier'
                else:
                    line.reception_status = 'pending'
            else:
                line.reception_status = 'pending'
