# -*- coding: utf-8 -*-
"""
Warehouse Location Mapping Model
Maps warehouse sources to job site destinations for material movements
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WarehouseLocationMapping(models.Model):
    """Model to manage warehouse to job site location mapping"""
    
    _name = 'warehouse.location.mapping'
    _description = 'Warehouse to Job Site Location Mapping'
    _rec_name = 'project_id'
    
    project_id = fields.Many2one(
        'rs.project',
        string=_('Project'),
        required=True,
        ondelete='cascade',
        help='Project for which this mapping applies'
    )
    
    warehouse_location_id = fields.Many2one(
        'stock.location',
        string=_('Main Warehouse Location'),
        required=True,
        domain="[('usage', '=', 'internal')]",
        help='Source location for material picking from warehouse'
    )
    
    job_site_location_id = fields.Many2one(
        'stock.location',
        string=_('Job Site Location'),
        required=True,
        domain="[('usage', '=', 'internal')]",
        help='Destination location for materials at job site'
    )
    
    is_default = fields.Boolean(
        string=_('Default Location'),
        default=False,
        help='Set as default mapping for this project'
    )
    
    is_active = fields.Boolean(
        string=_('Active'),
        default=True,
        help='Whether this mapping is active'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string=_('Company'),
        default=lambda self: self.env.company,
        required=True
    )
    
    notes = fields.Text(
        string=_('Notes'),
        help='Additional notes about this location mapping'
    )
    
    @api.constrains('is_default', 'project_id')
    def _check_default_unique(self):
        """Ensure only one default mapping per project"""
        for record in self:
            if record.is_default:
                existing = self.search([
                    ('project_id', '=', record.project_id.id),
                    ('is_default', '=', True),
                    ('id', '!=', record.id),
                ])
                if existing:
                    raise ValidationError(
                        _("Only one default mapping allowed per project. "
                          "Please unset the default on the other mapping first.")
                    )
    
    @api.constrains('warehouse_location_id', 'job_site_location_id')
    def _check_locations_different(self):
        """Ensure source and destination are different"""
        for record in self:
            if record.warehouse_location_id.id == record.job_site_location_id.id:
                raise ValidationError(
                    _("Warehouse location and job site location must be different.")
                )
    
    def name_get(self):
        """Display name showing project and location mapping"""
        result = []
        for record in self:
            name = f"{record.project_id.name} ({record.warehouse_location_id.name} → {record.job_site_location_id.name})"
            result.append((record.id, name))
        return result
    
    @api.model
    def get_default_mapping(self, project_id):
        """Get default mapping for a project"""
        mapping = self.search([
            ('project_id', '=', project_id),
            ('is_default', '=', True),
            ('is_active', '=', True),
        ], limit=1)
        
        if not mapping:
            # Fall back to any active mapping
            mapping = self.search([
                ('project_id', '=', project_id),
                ('is_active', '=', True),
            ], limit=1)
        
        return mapping
