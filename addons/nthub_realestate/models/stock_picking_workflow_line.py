# -*- coding: utf-8 -*-
"""
Stock Picking Workflow Line Model
Individual material lines for stock picking workflows
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockPickingWorkflowLine(models.Model):
    """Model for individual material lines in picking workflow"""
    
    _name = 'stock.picking.workflow.line'
    _description = 'Stock Picking Workflow Line'
    _rec_name = 'product_id'
    
    workflow_id = fields.Many2one(
        'stock.picking.workflow',
        string=_('Picking Workflow'),
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string=_('Product'),
        required=True,
        ondelete='cascade',
        domain="[('type', '=', 'product')]"
    )
    
    product_template_id = fields.Many2one(
        'product.template',
        string=_('Product Template'),
        related='product_id.product_tmpl_id',
        readonly=True,
        store=True
    )
    
    product_category_id = fields.Many2one(
        'product.category',
        string=_('Product Category'),
        related='product_id.categ_id',
        readonly=True,
        store=True
    )
    
    quantity = fields.Float(
        string=_('Quantity'),
        required=True,
        default=1.0,
        help='Quantity of product to pick'
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string=_('Unit of Measure'),
        required=True,
        related='product_id.uom_id',
        readonly=True,
        store=True
    )
    
    sequence = fields.Integer(
        string=_('Sequence'),
        default=10,
        help='Display order of lines'
    )
    
    description = fields.Text(
        string=_('Description'),
        help='Additional description or specifications'
    )
    
    # Stock availability tracking
    available_quantity = fields.Float(
        string=_('Available Qty'),
        compute='_compute_available_quantity',
        help='Current available quantity in warehouse'
    )
    
    shortage_quantity = fields.Float(
        string=_('Shortage Qty'),
        compute='_compute_shortage_quantity',
        store=True,
        help='Quantity not available in warehouse'
    )
    
    has_shortage = fields.Boolean(
        string=_('Has Shortage'),
        compute='_compute_has_shortage',
        store=True
    )
    
    # Serial/Lot tracking
    lot_ids = fields.Many2many(
        'stock.lot',
        string=_('Serial Numbers / Lots'),
        help='Serial numbers or lot numbers for tracked products'
    )
    
    serial_number = fields.Char(
        string=_('Serial Number'),
        help='Specific serial number if applicable'
    )
    
    notes = fields.Text(
        string=_('Notes'),
        help='Line-specific notes or special requirements'
    )
    
    @api.depends('product_id', 'workflow_id.source_location_id')
    def _compute_available_quantity(self):
        """Compute available quantity in warehouse"""
        for line in self:
            if line.product_id and line.workflow_id.source_location_id:
                available = self.env['stock.quant']._get_available_quantity(
                    line.product_id,
                    line.workflow_id.source_location_id,
                    strict=False
                )
                line.available_quantity = available
            else:
                line.available_quantity = 0.0
    
    @api.depends('quantity', 'available_quantity')
    def _compute_shortage_quantity(self):
        """Compute shortage"""
        for line in self:
            shortage = max(0, line.quantity - line.available_quantity)
            line.shortage_quantity = shortage
    
    @api.depends('quantity', 'available_quantity')
    def _compute_has_shortage(self):
        """Set shortage flag"""
        for line in self:
            shortage = max(0, line.quantity - line.available_quantity)
            line.has_shortage = shortage > 0
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Update UOM when product changes"""
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id
    
    def name_get(self):
        """Display name showing product and quantity"""
        result = []
        for line in self:
            name = f"{line.product_id.name} ({line.quantity} {line.uom_id.name})"
            result.append((line.id, name))
        return result
    
    @api.constrains('quantity')
    def _check_quantity(self):
        """Ensure quantity is positive"""
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))
    
    def action_show_availability(self):
        """Show product availability across locations"""
        self.ensure_one()
        
        quants = self.env['stock.quant'].search([
            ('product_id', '=', self.product_id.id),
            ('quantity', '>', 0),
        ])
        
        return {
            'name': _('Availability'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [('product_id', '=', self.product_id.id)],
        }
    
    def action_select_from_warehouse(self):
        """Open wizard to select from warehouse locations"""
        return {
            'name': _('Select from Warehouse'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workflow_line_id': self.id,
                'default_product_id': self.product_id.id,
            }
        }
