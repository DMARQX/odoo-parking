from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductRequestLine(models.Model):
    _name = 'product.request.line'
    _description = 'Product Request Line / بند طلب المنتجات'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Sequence / التسلسل',
        default=10
    )
    
    request_id = fields.Many2one(
        'product.request',
        string='Product Request / طلب المنتجات',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product / المنتج',
        required=True,
        domain=[('type', 'in', ['product', 'consu'])]
    )
    
    product_template_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        readonly=True
    )
    
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure / وحدة القياس',
        related='product_id.uom_id',
        readonly=True
    )
    
    quantity = fields.Float(
        string='Quantity / الكمية',
        required=True,
        default=1.0
    )
    
    available_quantity = fields.Float(
        string='Available Quantity / الكمية المتاحة',
        compute='_compute_available_quantity',
        store=False
    )
    
    description = fields.Text(
        string='Description / الوصف'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company / الشركة',
        related='request_id.company_id',
        store=True,
        readonly=True
    )
    
    state = fields.Selection(
        related='request_id.state',
        string='Request State / حالة الطلب',
        store=True,
        readonly=True
    )

    @api.depends('product_id', 'request_id.source_location_id')
    def _compute_available_quantity(self):
        """Compute available quantity in source location"""
        for line in self:
            if line.product_id and line.request_id.source_location_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', line.request_id.source_location_id.id)
                ])
                line.available_quantity = sum(quants.mapped('quantity'))
            else:
                line.available_quantity = 0.0

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero. / يجب أن تكون الكمية أكبر من الصفر."))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Update description when product changes"""
        if self.product_id:
            self.description = self.product_id.name

    @api.onchange('quantity', 'product_id', 'request_id.source_location_id')
    def _onchange_quantity_warning(self):
        """Show warning if requested quantity exceeds available quantity"""
        if self.product_id and self.request_id.source_location_id and self.quantity:
            available = 0.0
            quants = self.env['stock.quant'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id', '=', self.request_id.source_location_id.id)
            ])
            available = sum(quants.mapped('quantity'))
            
            if self.quantity > available:
                warning = {
                    'title': _('Warning / تحذير'),
                    'message': _('Requested quantity (%.2f) exceeds available quantity (%.2f) in source warehouse. / الكمية المطلوبة (%.2f) تتجاوز الكمية المتاحة (%.2f) في المخزن المصدر.') % (self.quantity, available)
                }
                return {'warning': warning}

    def name_get(self):
        """Custom name_get for better display"""
        result = []
        for line in self:
            name = '[%s] %s - %.2f %s' % (
                line.request_id.name,
                line.product_id.name,
                line.quantity,
                line.product_uom_id.name
            )
            result.append((line.id, name))
        return result