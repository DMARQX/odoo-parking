# -*- coding: utf-8 -*-
"""
Stock Picking Creation Workflow Model
Manages the creation and tracking of stock pickings from maintenance requests
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class StockPickingWorkflow(models.Model):
    """Model to manage stock picking workflow for job site materials"""
    
    _name = 'stock.picking.workflow'
    _description = 'Stock Picking Workflow for Maintenance Requests'
    _rec_name = 'name'
    _order = 'creation_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string=_('Picking Reference'),
        required=True,
        copy=False,
        readonly=True,
        default='/',
        tracking=True
    )
    
    maintenance_request_id = fields.Many2one(
        'rental.maintenance.request',
        string=_('Maintenance Request'),
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    picking_id = fields.Many2one(
        'stock.picking',
        string=_('Stock Picking'),
        readonly=True,
        tracking=True,
        help='Generated Odoo stock picking'
    )
    
    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('picking_created', 'Picking Created'),
            ('partially_delivered', 'Partially Delivered'),
            ('delivered', 'Delivered'),
            ('received', 'Received'),
            ('rejected', 'Rejected'),
        ],
        string=_('Status'),
        default='draft',
        tracking=True,
        required=True
    )
    
    project_id = fields.Many2one(
        'rs.project',
        string=_('Project'),
        related='maintenance_request_id.contract_id.rs_project',
        readonly=True,
        store=True,
        help='Project where maintenance is being performed'
    )
    
    warehouse_location_mapping_id = fields.Many2one(
        'warehouse.location.mapping',
        string=_('Location Mapping'),
        help='Warehouse to job site location mapping'
    )
    
    source_location_id = fields.Many2one(
        'stock.location',
        string=_('Source Location'),
        help='Warehouse location from which materials are picked'
    )
    
    destination_location_id = fields.Many2one(
        'stock.location',
        string=_('Destination Location'),
        help='Job site location where materials will be delivered'
    )
    
    job_site_location_id = fields.Many2one(
        'job.site.location',
        string=_('Job Site Location'),
        help='Physical job site storage location'
    )
    
    picking_line_ids = fields.One2many(
        'stock.picking.workflow.line',
        'workflow_id',
        string=_('Material Lines'),
        help='Materials to be picked for this maintenance request'
    )
    
    creation_date = fields.Datetime(
        string=_('Created Date'),
        default=fields.Datetime.now,
        readonly=True,
        tracking=True
    )
    
    submission_date = fields.Datetime(
        string=_('Submission Date'),
        readonly=True,
        tracking=True
    )
    
    delivery_date = fields.Datetime(
        string=_('Delivery Date'),
        readonly=True,
        tracking=True
    )
    
    received_date = fields.Datetime(
        string=_('Receipt Date'),
        readonly=True,
        tracking=True
    )
    
    requested_delivery_date = fields.Date(
        string=_('Requested Delivery Date'),
        help='Date when materials are needed at job site'
    )
    
    contractor_id = fields.Many2one(
        'res.partner',
        string=_('Contractor'),
        compute='_compute_contractor_id',
        readonly=True,
        store=True,
        help='Contractor responsible for work'
    )
    
    contractor_signature = fields.Binary(
        string=_('Contractor Signature'),
        help='Digital signature of contractor upon receipt'
    )
    
    notes = fields.Text(
        string=_('Notes'),
        help='Additional notes about the picking'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string=_('Company'),
        default=lambda self: self.env.company,
        required=True
    )
    
    # Computed fields
    total_items = fields.Integer(
        string=_('Total Items'),
        compute='_compute_line_totals',
        store=True
    )
    
    total_quantity = fields.Float(
        string=_('Total Quantity'),
        compute='_compute_line_totals',
        store=True
    )
    
    delivered_quantity = fields.Float(
        string=_('Delivered Quantity'),
        compute='_compute_delivery_stats',
        help='Total quantity delivered to job site'
    )
    
    received_quantity = fields.Float(
        string=_('Received Quantity'),
        compute='_compute_delivery_stats',
        help='Total quantity received and confirmed'
    )
    
    delivery_progress = fields.Float(
        string=_('Delivery Progress %'),
        compute='_compute_delivery_stats',
        help='Percentage of materials delivered'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create workflow with auto-generated sequence number"""
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('stock.picking.workflow') or '/'
        return super().create(vals_list)
    
    @api.depends('maintenance_request_id.x_job_order_id.assigned_contractor_id')
    def _compute_contractor_id(self):
        """Compute contractor from maintenance request"""
        for record in self:
            if record.maintenance_request_id:
                job_order = record.maintenance_request_id.x_job_order_id
                if job_order and job_order.assigned_contractor_id:
                    record.contractor_id = job_order.assigned_contractor_id.id
                else:
                    record.contractor_id = False
            else:
                record.contractor_id = False
    
    @api.depends('picking_line_ids')
    def _compute_line_totals(self):
        """Compute total items and quantity from lines"""
        for record in self:
            record.total_items = len(record.picking_line_ids)
            record.total_quantity = sum(record.picking_line_ids.mapped('quantity'))
    
    @api.depends('picking_id.move_ids', 'picking_id.state')
    def _compute_delivery_stats(self):
        """Compute delivery statistics from stock picking"""
        for record in self:
            if record.picking_id:
                delivered = sum(
                    record.picking_id.move_ids.filtered(
                        lambda m: m.state == 'done'
                    ).mapped('quantity_done')
                )
                received = sum(
                    record.picking_id.move_ids.filtered(
                        lambda m: m.state == 'done'
                    ).mapped('quantity_done')
                )
                record.delivered_quantity = delivered
                record.received_quantity = received
                
                if record.total_quantity > 0:
                    record.delivery_progress = (delivered / record.total_quantity) * 100
                else:
                    record.delivery_progress = 0.0
            else:
                record.delivered_quantity = 0.0
                record.received_quantity = 0.0
                record.delivery_progress = 0.0
    
    def action_submit(self):
        """Submit picking workflow for processing"""
        if not self.picking_line_ids:
            raise ValidationError(_("Cannot submit picking without material lines."))
        
        self.write({
            'status': 'submitted',
            'submission_date': fields.Datetime.now(),
        })
        
        self._create_chatter_message(_("Picking workflow submitted"))
    
    def action_view_picking(self):
        """View the stock picking"""
        self.ensure_one()
        
        if not self.picking_id:
            raise ValidationError(_("No stock picking created yet."))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
        }
    
    def action_create_picking(self):
        """Create Odoo stock picking from workflow"""
        self.ensure_one()
        
        if self.picking_id:
            raise ValidationError(_("Stock picking already created for this workflow."))
        
        if not self.source_location_id or not self.destination_location_id:
            raise ValidationError(_("Source and destination locations must be set."))
        
        # Create stock picking
        picking_vals = {
            'picking_type_id': self._get_picking_type().id,
            'location_id': self.source_location_id.id,
            'location_dest_id': self.destination_location_id.id,
            'origin': self.name,
            'scheduled_date': self.requested_delivery_date or fields.Date.today(),
        }
        
        picking = self.env['stock.picking'].create(picking_vals)
        
        # Create picking lines from workflow lines
        for line in self.picking_line_ids:
            self.env['stock.move'].create({
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'product_uom_qty': line.quantity,
                'picking_id': picking.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
            })
        
        self.write({
            'picking_id': picking.id,
            'status': 'picking_created',
        })
        
        self._create_chatter_message(_("Stock picking created: ") + picking.name)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
        }
    
    def action_confirm_receipt(self):
        """Confirm receipt of materials at job site"""
        self.ensure_one()
        
        if self.status not in ['picking_created', 'partially_delivered']:
            raise ValidationError(_("Can only confirm receipt for pending pickings."))
        
        # Validate all lines have been received
        if self.picking_id and self.picking_id.state != 'done':
            raise ValidationError(_("Stock picking must be delivered before confirming receipt."))
        
        self.write({
            'status': 'received',
            'received_date': fields.Datetime.now(),
        })
        
        # Notify contractor and create activity
        self._create_chatter_message(_("Materials received and confirmed"))
        self._notify_contractor_received()
    
    def action_reject(self):
        """Reject the picking workflow"""
        self.write({
            'status': 'rejected',
        })
        
        self._create_chatter_message(_("Picking workflow rejected"))
    
    def _get_picking_type(self):
        """Get stock picking type for internal transfers"""
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '!=', False),
        ], limit=1)
        
        if not picking_type:
            raise ValidationError(_("No internal transfer picking type found."))
        
        return picking_type
    
    def _create_chatter_message(self, message):
        """Create message in chatter"""
        self.message_post(
            body=message,
            message_type='notification',
        )
    
    def _notify_contractor_received(self):
        """Send notification to contractor about receipt"""
        template = self.env.ref('nthub_realestate.mail_template_contractor_materials_received', raise_if_not_found=False)
        
        if template and self.contractor_id:
            template.send_mail(self.id)
