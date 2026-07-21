# -*- coding: utf-8 -*-
"""
Job Site Location Model
Represents physical job site storage locations for received materials
"""

from odoo import models, fields, api, _


class JobSiteLocation(models.Model):
    """Model to manage job site storage locations"""
    
    _name = 'job.site.location'
    _description = 'Job Site Storage Location'
    _rec_name = 'name'
    _order = 'project_id, name'
    
    name = fields.Char(
        string=_('Location Name'),
        required=True,
        help='Name of the job site storage location (e.g., "Site Office", "Storage Area A")'
    )
    
    project_id = fields.Many2one(
        'rs.project',
        string=_('Project'),
        required=True,
        ondelete='cascade',
        help='Project where this location is situated'
    )
    
    stock_location_id = fields.Many2one(
        'stock.location',
        string=_('Stock Location'),
        required=True,
        domain="[('usage', '=', 'internal')]",
        help='Corresponding Odoo stock location for inventory tracking'
    )
    
    location_type = fields.Selection(
        [
            ('site_office', 'Site Office'),
            ('storage_area', 'Storage Area'),
            ('material_store', 'Material Store'),
            ('equipment_yard', 'Equipment Yard'),
            ('staging_area', 'Staging Area'),
            ('other', 'Other'),
        ],
        string=_('Location Type'),
        default='storage_area',
        required=True,
        help='Type of storage location'
    )
    
    description = fields.Text(
        string=_('Description'),
        help='Detailed description of the location (address, facilities, etc.)'
    )
    
    capacity = fields.Float(
        string=_('Storage Capacity (m³)'),
        help='Total storage capacity of this location'
    )
    
    contact_person_id = fields.Many2one(
        'res.partner',
        string=_('Contact Person'),
        help='Person responsible for this location'
    )
    
    contact_phone = fields.Char(
        string=_('Contact Phone'),
        help='Phone number of location contact'
    )
    
    is_active = fields.Boolean(
        string=_('Active'),
        default=True,
        help='Whether this location is active'
    )
    
    is_primary = fields.Boolean(
        string=_('Primary Location'),
        default=False,
        help='Primary material storage location for this project'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string=_('Company'),
        default=lambda self: self.env.company,
        required=True
    )
    
    # Computed fields for inventory tracking
    total_items = fields.Integer(
        string=_('Total Items'),
        compute='_compute_inventory_stats',
        help='Total number of items stored'
    )
    
    total_quantity = fields.Float(
        string=_('Total Quantity'),
        compute='_compute_inventory_stats',
        help='Total quantity of all items'
    )
    
    current_capacity_usage = fields.Float(
        string=_('Capacity Usage %'),
        compute='_compute_capacity_usage',
        help='Percentage of storage capacity in use'
    )
    
    @api.depends('stock_location_id')
    def _compute_inventory_stats(self):
        """Compute current inventory statistics"""
        for record in self:
            if record.stock_location_id:
                stock_quants = self.env['stock.quant'].search([
                    ('location_id', '=', record.stock_location_id.id),
                ])
                
                record.total_items = len(stock_quants)
                record.total_quantity = sum(stock_quants.mapped('quantity'))
            else:
                record.total_items = 0
                record.total_quantity = 0
    
    @api.depends('total_quantity', 'capacity')
    def _compute_capacity_usage(self):
        """Compute capacity usage percentage"""
        for record in self:
            if record.capacity > 0 and record.total_quantity > 0:
                record.current_capacity_usage = (record.total_quantity / record.capacity) * 100
            else:
                record.current_capacity_usage = 0.0
    
    def name_get(self):
        """Display name showing location and project"""
        result = []
        for record in self:
            name = f"{record.name} ({record.project_id.name})"
            result.append((record.id, name))
        return result
    
    @api.model
    def get_primary_location(self, project_id):
        """Get primary storage location for a project"""
        location = self.search([
            ('project_id', '=', project_id),
            ('is_primary', '=', True),
            ('is_active', '=', True),
        ], limit=1)
        
        if not location:
            # Fall back to any active location
            location = self.search([
                ('project_id', '=', project_id),
                ('is_active', '=', True),
            ], limit=1)
        
        return location
    
    def get_inventory_summary(self):
        """Get detailed inventory summary for this location"""
        self.ensure_one()
        
        stock_moves = self.env['stock.move'].search([
            ('location_dest_id', '=', self.stock_location_id.id),
            ('state', '=', 'done'),
        ], order='date desc', limit=100)
        
        return {
            'location': self,
            'total_items': self.total_items,
            'total_quantity': self.total_quantity,
            'capacity_usage': self.current_capacity_usage,
            'recent_moves': stock_moves,
        }
    
    def action_show_inventory(self):
        """Show inventory details for this location"""
        self.ensure_one()
        
        return {
            'name': _('Inventory'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [('location_id', '=', self.stock_location_id.id)],
            'context': {'search_default_location_id': self.stock_location_id.id}
        }
