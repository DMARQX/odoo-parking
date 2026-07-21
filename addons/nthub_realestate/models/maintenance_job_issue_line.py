from odoo import models, fields, api

class MaintenanceJobIssueLine(models.Model):
    """E-2: Issued Materials from Stock (by Store Manager)"""
    _name = 'maintenance.job.issue.line'
    _description = 'Job Order Issued Materials Line'

    job_order_id = fields.Many2one('maintenance.job.order', string="Job Order", required=True, ondelete='cascade')
    request_line_id = fields.Many2one('maintenance.job.request.line', string="Request Line", ondelete='set null')
    product_id = fields.Many2one('product.product', string="Product", required=True, 
                                 domain=[('type', '=', 'product')])
    issue_qty = fields.Float(string="Issue Quantity", default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', string="UOM", related='product_id.uom_id', readonly=True)
    serial_no = fields.Char(string="Serial No")
    move_id = fields.Many2one('stock.move', string="Stock Move", readonly=True)
    issue_date = fields.Date(string="Issue Date", default=fields.Date.today)
    notes = fields.Text(string="Notes")
