from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MaintenanceMaterialMappingWizard(models.TransientModel):
    """Wizard to map contractor material requests to actual products"""
    _name = 'maintenance.material.mapping.wizard'
    _description = 'Material Mapping Wizard'

    job_order_id = fields.Many2one('maintenance.job.order', string='Job Order', required=True)
    mapping_line_ids = fields.One2many('maintenance.material.mapping.line', 'wizard_id', string='Material Mappings')

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with material request lines"""
        defaults = super().default_get(fields_list)
        
        job_order_id = self.env.context.get('job_order_id') or defaults.get('job_order_id')
        if job_order_id:
            job_order = self.env['maintenance.job.order'].browse(job_order_id)
            defaults['job_order_id'] = job_order_id
            
            # Create mapping lines for each material request
            mapping_lines = []
            for request_line in job_order.requested_material_ids:
                mapping_lines.append((0, 0, {
                    'request_line_id': request_line.id,
                    'description': request_line.description,
                    'requested_qty': request_line.quantity,
                    'mapping_type': 'stock' if request_line.type_of_material == 'stock' else 'purchase'
                }))
            
            defaults['mapping_line_ids'] = mapping_lines
        
        return defaults

    @api.model
    def create(self, vals):
        """Override create to populate mapping lines"""
        wizard = super().create(vals)
        
        if wizard.job_order_id and not wizard.mapping_line_ids:
            # Auto-populate mapping lines if not provided
            mapping_lines = []
            for request_line in wizard.job_order_id.requested_material_ids:
                mapping_lines.append({
                    'wizard_id': wizard.id,
                    'request_line_id': request_line.id,
                    'description': request_line.description,
                    'requested_qty': request_line.quantity,
                    'mapping_type': 'stock' if request_line.type_of_material == 'stock' else 'purchase'
                })
            
            if mapping_lines:
                self.env['maintenance.material.mapping.line'].create(mapping_lines)
        
        return wizard

    def action_map_materials(self):
        """Execute the material mapping"""
        self.ensure_one()
        
        for mapping in self.mapping_line_ids:
            if not mapping.product_id:
                continue
                
            if mapping.mapping_type == 'stock':
                # Create issued material line
                self.job_order_id.create_issued_material_from_request(
                    mapping.request_line_id,
                    mapping.product_id,
                    mapping.mapped_qty
                )
            elif mapping.mapping_type == 'purchase':
                # Create purchase material line
                self.job_order_id.create_purchase_material_from_request(
                    mapping.request_line_id,
                    mapping.product_id,
                    mapping.mapped_qty,
                    mapping.supplier_id
                )
        
        return {'type': 'ir.actions.act_window_close'}


class MaintenanceMaterialMappingLine(models.TransientModel):
    """Individual material mapping line"""
    _name = 'maintenance.material.mapping.line'
    _description = 'Material Mapping Line'

    wizard_id = fields.Many2one('maintenance.material.mapping.wizard', string='Wizard')
    request_line_id = fields.Many2one('maintenance.job.request.line', string='Material Request')
    description = fields.Char(string='Requested Material', readonly=True)
    requested_qty = fields.Float(string='Requested Qty', readonly=True)
    
    product_id = fields.Many2one('product.product', string='Product', 
                                 domain=[('type', '=', 'consu')])
    mapped_qty = fields.Float(string='Mapped Qty', default=1.0)
    
    mapping_type = fields.Selection([
        ('stock', 'Issue from Stock'),
        ('purchase', 'Purchase')
    ], string='Mapping Type', required=True, default='stock')
    
    supplier_id = fields.Many2one('res.partner', string='Supplier',
                                  domain=[('supplier_rank', '>', 0)],
                                  help='Required for purchase mapping')

    @api.onchange('requested_qty')
    def _onchange_requested_qty(self):
        """Set mapped quantity to requested quantity by default"""
        if self.requested_qty:
            self.mapped_qty = self.requested_qty

    @api.onchange('mapping_type')
    def _onchange_mapping_type(self):
        """Clear supplier when mapping type is stock"""
        if self.mapping_type == 'stock':
            self.supplier_id = False