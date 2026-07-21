from odoo import models, fields, api
from odoo.exceptions import UserError


class MaintenanceJobMaterialRequest(models.Model):
    """Material Request Lines for Job Orders - Stock Integration"""
    _name = 'maintenance.job.material.request'
    _description = 'Job Order Material Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'create_date DESC'

    # Reference
    name = fields.Char(
        string='Request Number',
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('maint.material.request')
    )

    job_order_id = fields.Many2one(
        'job.order.form',
        string='Job Order',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    # Material Details
    product_id = fields.Many2one(
        'product.product',
        string='Material/Product',
        required=True,
        domain="[('type', '!=', 'service')]",
        tracking=True
    )

    description = fields.Char(
        string='Description',
        related='product_id.name',
        store=True,
        readonly=True
    )

    # Quantities
    qty_requested = fields.Float(
        string='Quantity Requested',
        required=True,
        default=1.0
    )

    qty_issued = fields.Float(
        string='Quantity Issued',
        readonly=True,
        default=0.0
    )

    qty_returned = fields.Float(
        string='Quantity Returned',
        readonly=True,
        default=0.0
    )

    qty_used = fields.Float(
        string='Quantity Used',
        compute='_compute_qty_used',
        store=True
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        store=True,
        readonly=True
    )

    # Stock Integration
    state = fields.Selection(
        [('draft', 'Draft'),
         ('approved', 'Approved'),
         ('picking_created', 'Picking Created'),
         ('issued', 'Issued'),
         ('returned', 'Returned'),
         ('cancelled', 'Cancelled')],
        string='State',
        default='draft',
        tracking=True
    )

    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Stock Picking',
        readonly=True,
        help='Associated warehouse stock picking'
    )

    picking_state = fields.Selection(
        related='stock_picking_id.state',
        store=True,
        readonly=True
    )

    delivery_date = fields.Datetime(
        string='Delivery Date',
        readonly=True,
        help='When materials were delivered to job site'
    )

    received_date = fields.Datetime(
        string='Received Date',
        readonly=True,
        help='When contractor confirmed receipt'
    )

    received_by = fields.Many2one(
        'res.partner',
        string='Received By',
        readonly=True,
        help='Contractor who received materials'
    )

    proof_image = fields.Binary(
        string='Delivery Proof',
        help='Photo proof of delivered materials'
    )

    proof_image_filename = fields.Char()

    # Notes
    notes = fields.Text(
        string='Notes'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.depends('qty_issued', 'qty_returned')
    def _compute_qty_used(self):
        for record in self:
            record.qty_used = record.qty_issued - record.qty_returned

    def action_approve(self):
        """Approve material request"""
        self.state = 'approved'
        self.message_post(
            body='Material request approved',
            message_type='notification'
        )

    def action_create_picking(self):
        """Create stock picking for approved material request"""
        if self.state != 'approved':
            raise UserError('Only approved requests can be picked')

        if self.stock_picking_id:
            raise UserError('Stock picking already created for this request')

        # Get warehouse locations
        mapping = self.env['warehouse.location.mapping'].get_default_mapping(
            self.job_order_id.project_id.rs_project_id.id
        )

        if not mapping:
            raise UserError('Warehouse location mapping not configured for this project')

        # Create stock.picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.env.ref('nthub_realestate.picking_type_maintenance').id,
            'location_id': mapping.warehouse_location_id.id,
            'location_dest_id': mapping.job_site_location_id.id,
            'partner_id': self.job_order_id.assigned_contractor_id.id,
            'origin': self.name,
            'note': f'Materials for Job Order: {self.job_order_id.name}',
            'x_job_order_id': self.job_order_id.id,  # Link to job order
        })

        # Create stock move
        self.env['stock.move'].create({
            'picking_id': picking.id,
            'product_id': self.product_id.id,
            'product_uom_qty': self.qty_requested,
            'product_uom': self.uom_id.id,
            'name': self.description,
        })

        self.stock_picking_id = picking.id
        self.state = 'picking_created'
        self.delivery_date = fields.Datetime.now()

        self.message_post(
            body=f'Stock picking created: {picking.name}',
            message_type='notification'
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
        }

    def action_confirm_receipt(self, received_by_id=None, proof_image=None):
        """Confirm material receipt by contractor"""
        if self.state != 'picking_created':
            raise UserError('Can only confirm receipt for picking_created state')

        if not self.stock_picking_id:
            raise UserError('No stock picking associated with this request')

        # Mark picking as done
        if self.stock_picking_id.state == 'draft':
            self.stock_picking_id.action_confirm()
        if self.stock_picking_id.state == 'assigned':
            self.stock_picking_id.button_validate()

        # Update receipt info
        self.update({
            'state': 'issued',
            'received_date': fields.Datetime.now(),
            'received_by': received_by_id,
            'qty_issued': self.qty_requested,
            'proof_image': proof_image,
        })

        self.message_post(
            body=f'Materials received by {self.received_by.name}',
            message_type='notification'
        )

    def action_cancel(self):
        """Cancel material request"""
        self.state = 'cancelled'
        if self.stock_picking_id and self.stock_picking_id.state == 'draft':
            self.stock_picking_id.action_cancel()
        self.message_post(
            body='Material request cancelled',
            message_type='notification'
        )
