from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class ProductRequest(models.Model):
    _name = 'product.request'
    _description = 'Product Request / طلب المنتجات'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Request Number / رقم الطلب',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('New')
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Requester / الطالب',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact / جهة الاتصال',
        related='user_id.partner_id',
        store=True,
        readonly=True
    )
    
    request_date = fields.Datetime(
        string='Request Date / تاريخ الطلب',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    source_location_id = fields.Many2one(
        'stock.location',
        string='Source Warehouse / المخزن المصدر',
        required=True,
        domain=[('usage', '=', 'internal')],
        tracking=True
    )
    
    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Warehouse / مخزن الوجهة',
        required=True,
        domain=[('usage', '=', 'internal')],
        tracking=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft / مسودة'),
        ('submitted', 'Submitted / مُرسل'),
        ('approved', 'Approved / معتمد'),
        ('received', 'Received / مُستلم'),
        ('cancelled', 'Cancelled / مُلغى'),
    ], string='Status / الحالة', default='draft', tracking=True, copy=False)
    
    request_line_ids = fields.One2many(
        'product.request.line',
        'request_id',
        string='Request Lines / بنود الطلب',
        copy=True
    )
    
    notes = fields.Text(
        string='Notes / ملاحظات'
    )
    
    approval_date = fields.Datetime(
        string='Approval Date / تاريخ الاعتماد',
        readonly=True,
        tracking=True
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By / اعتمد بواسطة',
        readonly=True,
        tracking=True
    )
    
    received_date = fields.Datetime(
        string='Received Date / تاريخ الاستلام',
        readonly=True,
        tracking=True
    )
    
    internal_transfer_id = fields.Many2one(
        'stock.picking',
        string='Internal Transfer / التحويل الداخلي',
        readonly=True,
        copy=False
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company / الشركة',
        default=lambda self: self.env.company,
        required=True
    )
    
    total_quantity = fields.Float(
        string='Total Quantity / إجمالي الكمية',
        compute='_compute_total_quantity',
        store=True
    )
    
    line_count = fields.Integer(
        string='Number of Lines / عدد البنود',
        compute='_compute_line_count',
        store=True
    )

    @api.depends('request_line_ids.quantity')
    def _compute_total_quantity(self):
        for record in self:
            record.total_quantity = sum(record.request_line_ids.mapped('quantity'))

    @api.depends('request_line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.request_line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('product.request') or _('New')
        return super().create(vals_list)

    @api.constrains('source_location_id', 'dest_location_id')
    def _check_locations(self):
        for record in self:
            if record.source_location_id == record.dest_location_id:
                raise ValidationError(_("Source and destination warehouses must be different. / يجب أن يكون المخزن المصدر والوجهة مختلفين."))

    @api.constrains('request_line_ids')
    def _check_request_lines(self):
        for record in self:
            if not record.request_line_ids:
                raise ValidationError(_("Request must have at least one line. / يجب أن يحتوي الطلب على بند واحد على الأقل."))

    def action_submit(self):
        """Submit the request for approval"""
        if not self.request_line_ids:
            raise UserError(_("Cannot submit a request without lines. / لا يمكن إرسال طلب بدون بنود."))
        
        for line in self.request_line_ids:
            if line.quantity <= 0:
                raise UserError(_("All quantities must be greater than zero. / يجب أن تكون جميع الكميات أكبر من الصفر."))
        
        self.write({
            'state': 'submitted',
        })
        
        # Send notification to managers
        self._notify_managers()
        
        self.message_post(
            body=_("Product request has been submitted for approval. / تم إرسال طلب المنتجات للاعتماد."),
            message_type='notification'
        )

    def action_approve(self):
        """Approve the request"""
        if self.state != 'submitted':
            raise UserError(_("Only submitted requests can be approved. / يمكن اعتماد الطلبات المُرسلة فقط."))
        
        self.write({
            'state': 'approved',
            'approval_date': fields.Datetime.now(),
            'approved_by': self.env.user.id,
        })
        
        self.message_post(
            body=_("Product request has been approved by %s. / تم اعتماد طلب المنتجات بواسطة %s.") % self.env.user.name,
            message_type='notification'
        )

    def action_receive(self):
        """Mark as received and create internal transfer"""
        if self.state != 'approved':
            raise UserError(_("Only approved requests can be received. / يمكن استلام الطلبات المعتمدة فقط."))
        
        # Create internal transfer
        transfer = self._create_internal_transfer()
        
        self.write({
            'state': 'received',
            'received_date': fields.Datetime.now(),
            'internal_transfer_id': transfer.id,
        })
        
        self.message_post(
            body=_("Product request has been received. Internal transfer %s created. / تم استلام طلب المنتجات. تم إنشاء التحويل الداخلي %s.") % transfer.name,
            message_type='notification'
        )

    def action_cancel(self):
        """Cancel the request"""
        if self.state == 'received':
            raise UserError(_("Cannot cancel a received request. / لا يمكن إلغاء طلب مُستلم."))
        
        self.write({'state': 'cancelled'})
        
        self.message_post(
            body=_("Product request has been cancelled. / تم إلغاء طلب المنتجات."),
            message_type='notification'
        )

    def action_reset_to_draft(self):
        """Reset to draft state"""
        if self.state in ['received']:
            raise UserError(_("Cannot reset a received request to draft. / لا يمكن إعادة تعيين طلب مُستلم إلى مسودة."))
        
        self.write({
            'state': 'draft',
            'approval_date': False,
            'approved_by': False,
            'received_date': False,
        })
        
        self.message_post(
            body=_("Product request has been reset to draft. / تم إعادة تعيين طلب المنتجات إلى مسودة."),
            message_type='notification'
        )

    def _create_internal_transfer(self):
        """Create internal transfer for approved request"""
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not picking_type:
            raise UserError(_("No internal picking type found. / لم يتم العثور على نوع انتقاء داخلي."))
        
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': self.source_location_id.id,
            'location_dest_id': self.dest_location_id.id,
            'origin': self.name,
            'partner_id': self.partner_id.id,
            'scheduled_date': fields.Datetime.now(),
            'company_id': self.company_id.id,
        }
        
        picking = self.env['stock.picking'].create(picking_vals)
        
        # Create move lines
        for line in self.request_line_ids:
            move_vals = {
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.dest_location_id.id,
                'company_id': self.company_id.id,
            }
            self.env['stock.move'].create(move_vals)
        
        picking.action_confirm()
        picking.action_assign()
        
        return picking

    def _notify_managers(self):
        """Notify managers about new request submission"""
        managers = self.env['res.users'].search([
            ('groups_id', 'in', [self.env.ref('stock.group_stock_manager').id])
        ])
        
        if managers:
            self.message_subscribe(partner_ids=managers.mapped('partner_id.id'))

    def _compute_access_url(self):
        """Compute portal access URL"""
        super()._compute_access_url()
        for request in self:
            request.access_url = '/my/product_request/%s' % request.id

    def action_view_picking(self):
        """View associated picking/internal transfer"""
        self.ensure_one()
        if not self.internal_transfer_id:
            return {}
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Internal Transfer',
            'view_mode': 'form',
            'res_model': 'stock.picking',
            'res_id': self.internal_transfer_id.id,
            'context': dict(self.env.context, create=False),
        }

    def _get_portal_return_action(self):
        """Return portal action"""
        return {
            'type': 'ir.actions.act_url',
            'url': '/my/product_requests',
            'target': 'self',
        }