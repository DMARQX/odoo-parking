from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_product_requester = fields.Boolean(
        string='Is Product Requester / يمكنه طلب منتجات',
        default=False,
        help='Allow this contact to make product requests via portal / السماح لهذا جهة الاتصال بطلب المنتجات عبر البورتال'
    )
    
    allowed_product_ids = fields.Many2many(
        'product.product',
        'partner_product_request_rel',
        'partner_id',
        'product_id',
        string='Allowed Products / المنتجات المسموح بها',
        domain=[('type', 'in', ['product', 'consu'])],
        help='Products that this contact can request via portal / المنتجات التي يمكن لهذا جهة الاتصال طلبها عبر البورتال'
    )
    
    allowed_source_location_ids = fields.Many2many(
        'stock.location',
        'partner_source_location_rel',
        'partner_id',
        'location_id',
        string='Allowed Source Locations / المخازن المصدر المسموح بها',
        domain=[('usage', '=', 'internal')],
        help='Source warehouses that this contact can request from / المخازن المصدر التي يمكن لهذا جهة الاتصال الطلب منها'
    )
    
    allowed_dest_location_ids = fields.Many2many(
        'stock.location',
        'partner_dest_location_rel',
        'partner_id',
        'location_id',
        string='Allowed Destination Locations / مخازن الوجهة المسموح بها',
        domain=[('usage', '=', 'internal')],
        help='Destination warehouses that this contact can request to / مخازن الوجهة التي يمكن لهذا جهة الاتصال الطلب إليها'
    )
    
    product_request_ids = fields.One2many(
        'product.request',
        'partner_id',
        string='Product Requests / طلبات المنتجات',
        readonly=True
    )
    
    product_request_count = fields.Integer(
        string='Product Request Count / عدد طلبات المنتجات',
        compute='_compute_product_request_count'
    )

    @api.depends('product_request_ids')
    def _compute_product_request_count(self):
        for partner in self:
            partner.product_request_count = len(partner.product_request_ids)

    def action_view_product_requests(self):
        """Action to view partner's product requests"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Requests / طلبات المنتجات',
            'view_mode': 'list,form',
            'res_model': 'product.request',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }