# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


class SubProperty(models.Model):
    _name = 'sub.property'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'sub.property'

    name = fields.Char('Name')
    code = fields.Char(string='Code', required=True)
    partner_id = fields.Many2one('res.partner', 'Owner', domain="[('is_owner','=',True)]")
    tenant_id = fields.Many2one('res.partner', 'Tenant / المستأجر', domain="[('is_tenant','=',True)]")
    video_url = fields.Char('Video URL')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    rs_project_id = fields.Many2one('rs.project', string="Project")
    
    # ربط مع نظام الطوابق الجديد
    floor_id = fields.Many2one('rs.project.floor', string="الطابق", ondelete='cascade')
    unit_number = fields.Integer(string="رقم الوحدة")
    unit_template_id = fields.Many2one('rs.project.unit.template', string="قالب الوحدة")
    
    street = fields.Char(string=_('Street'))
    street2 = fields.Char(string=_('Street2'))
    city = fields.Char(string=_('City'))
    country_id = fields.Many2one('res.country')
    zip = fields.Char(string=_('Zip'))
    state_id = fields.Many2one('res.country.state')
    region = fields.Many2one('regions', related='rs_project_id.region', string='Region', store='True')
    state = fields.Selection([('free', 'Available'),
                              ('reserved', 'Booked'),
                              ('on_lease', 'Leased'),
                              ('sold', 'Sold'),
                              ], 'State', default='free')

    ptype = fields.Many2one('rs.project.type', 'Property Type')
    rental_price_per_sqm = fields.Float('Rental Price per m²', help="Price per square meter for rental calculation")
    electricity_price_per_sqm = fields.Float('Electricity Price per m²', help="Electricity price per square meter")
    
    # Project Service Fee Percentage (editable, defaults from project)
    project_service_fee_percent = fields.Float(
        string='Project Service Fee %',
        related='rs_project_id.project_service_fee_percent',
        readonly=False,
        store=True,
        help='Service fee percentage (can override project default)'
    )
    
    # Service fee is now computed based on: base_rental_fee * (project_service_fee_percent/100)
    # Note: Service fee is calculated on rental only (excluding electricity)
    service_fee = fields.Float(
        string='Service Fee / رسوم الخدمة',
        compute='_compute_service_fee',
        store=True,
        help="Computed as: Base Rental Fee × (Project Service Fee % / 100) - Excludes electricity"
    )
    
    # Base rental fee (without electricity) - used for service fee calculation
    base_rental_fee = fields.Float(
        string='Base Rental Fee',
        compute='_compute_rental_fee',
        store=True,
        help="Rental amount only (area × rental price per sqm) - excludes electricity"
    )
    
    rental_fee = fields.Float('Rental Fee', compute='_compute_rental_fee', store=True, help="Automatically calculated: (Rental Price + Electricity Price) × Area")
    total_rental_fee = fields.Float('Total Rental Fee / إجمالي الإيجار', compute='_compute_total_rental_fee', store=True, help="Total rental fee including service fee: Rental Fee + Service Fee")
    insurance_fee = fields.Integer('Insurance Fee')
    status = fields.Many2one('rs.project.status', 'Property Status')
    rs_project_area = fields.Float('Project Unit Area m^2')
    rs_project_area_net = fields.Integer('Net Area m^2', invisible=True)
    land_area = fields.Integer('Gross Area m^2', invisible=True)
    constructed = fields.Date('Construction Date')
    air_condition = fields.Selection([
        ('unknown', 'Unknown'),
        ('central', 'Central'),
        ('partial', 'Partial'),
        ('none', 'None')])
    rooms = fields.Integer('Rooms')
    bathrooms = fields.Integer('Bathrooms')
    telephone = fields.Boolean()
    internet = fields.Boolean()
    pricing = fields.Integer('Selling Price')
    floor = fields.Char('Floor')
    surface = fields.Integer('Surface', invisible=True)
    garage = fields.Integer('Garage Included')
    garden = fields.Integer('Garden m^2', invisible=True)
    balcony = fields.Integer('Balconies m^2', invisible=True)
    solar_electric = fields.Boolean('Solar Electric System')
    heating_source = fields.Selection([
        ('unknown', 'Unknown'),
        ('electricity', 'Electricity'),
        ('wood', 'Wood'),
        ('pellets', 'Pellets'),
        ('oil', 'Oil'),
        ('gas', 'Gas'),
        ('district', 'District Heating')])
    desc = fields.Many2one('rs.project.desc', 'Description')
    electricity_meter = fields.Char('Electricity Meter')
    water_meter = fields.Char('Water Meter')
    north = fields.Char('Northern border by')
    south = fields.Char('Southern border by')
    east = fields.Char('Eastern border by')
    west = fields.Char('Western border by')
    license_code = fields.Char('License Code')
    license_date = fields.Date('License Date')
    date_added = fields.Date('Date Added to Notarization')
    license_notarization = fields.Char('License Notarization')
    note = fields.Text()
    marker_color = fields.Char()
    date_localization = fields.Char(readonly=True)
    furniture_ids = fields.One2many('furniture', 'property_id')
    property_attachment_ids = fields.One2many('property.attachment.line', 'prop_attachment_id')
    reservation_count = fields.Integer(compute='_reservation_count', string='Reservation Count', )
    sub_property_images_ids = fields.One2many('sub.property.image', 'sub_property_id')
    image = fields.Image()
    repeat_count = fields.Integer(string="Number of repetitions", default=1)
    
    # Portal visibility fields
    show_owner_portal_button = fields.Boolean(compute='_compute_portal_visibility')
    show_tenant_portal_button = fields.Boolean(compute='_compute_portal_visibility')

    #This SQL constraint enforces uniqueness on the 'code' field, ensuring that no duplicate values are allowed for this field in the database.
    _sql_constraints = [
        ('unique_code', 'UNIQUE (code)', 'The code field must be unique.'),
    ]

    @api.depends('rs_project_area', 'rental_price_per_sqm')
    def _compute_rental_fee(self):
        """Calculate rental fee: Rental Price per m² × Project Unit Area m²
        Note: Rental fee does NOT include electricity
        """
        for record in self:
            if record.rs_project_area:
                # Rental Fee = Rental Price per m² × Project Unit Area m²
                record.rental_fee = record.rs_project_area * (record.rental_price_per_sqm or 0.0)
                record.base_rental_fee = record.rental_fee
            else:
                record.rental_fee = 0.0
                record.base_rental_fee = 0.0

    @api.depends('base_rental_fee', 'rs_project_area', 'project_service_fee_percent')
    def _compute_service_fee(self):
        """Calculate service fee as: Base Rental Fee × (Project Service Fee % / 100)
        Note: Service fee is calculated on rental only (excludes electricity)
        """
        for record in self:
            if record.base_rental_fee and record.project_service_fee_percent:
                record.service_fee = record.base_rental_fee * (record.project_service_fee_percent / 100)
            else:
                record.service_fee = 0.0

    @api.depends('rental_fee', 'service_fee', 'rs_project_area', 'electricity_price_per_sqm')
    def _compute_total_rental_fee(self):
        """Calculate total rental fee: Rental Fee + Service Fee + Electricity
        Total = Rental Fee + Service Fee + (Electricity Price per m² × Area)
        """
        for record in self:
            electricity_fee = (record.rs_project_area or 0.0) * (record.electricity_price_per_sqm or 0.0)
            record.total_rental_fee = (record.rental_fee or 0.0) + (record.service_fee or 0.0) + electricity_fee

    def _compute_portal_visibility(self):
        """Compute portal button visibility based on user type"""
        for record in self:
            current_user = self.env.user
            current_partner = current_user.partner_id
            
            # Show owner portal button if:
            # 1. Current user is admin/internal user AND has owner assigned
            # 2. OR current user is the owner themselves
            record.show_owner_portal_button = (
                (not current_user.has_group('base.group_portal') and record.partner_id) or
                (current_partner == record.partner_id and record.partner_id)
            )
            
            # Show tenant portal button if:
            # 1. Current user is admin/internal user AND has tenant assigned
            # 2. OR current user is the tenant themselves
            record.show_tenant_portal_button = (
                (not current_user.has_group('base.group_portal') and record.tenant_id) or
                (current_partner == record.tenant_id and record.tenant_id)
            )

    def action_duplicate_unit(self):
        self.ensure_one()
        project = self.rs_project_id

        repeat = self.repeat_count if self.repeat_count > 0 else 1

        floor = int(self.floor or 1)
        unit = int(self.code.split("-")[-1]) if self.code else 1

        new_unit = None
        total_units = ((floor - 1) * project.props_per_floor) + unit

        for i in range(repeat):
            total_units += 1
            next_floor = ((total_units - 1) // project.props_per_floor) + 1
            next_unit = ((total_units - 1) % project.props_per_floor) + 1

            if next_floor > project.no_of_floors:
                raise ValidationError("❌ تم الوصول للحد الأقصى من عدد الوحدات.")

            name = f'{project.code}-{next_floor}-{next_unit}'

            if self.env['sub.property'].search_count([('code', '=', name)]):
                raise ValidationError(f"❌ الوحدة {name} موجودة بالفعل.")

            excluded_fields = ['id', 'name', 'code', 'floor', 'state', '__last_update', 'display_name', 'repeat_count']
            base_fields = {}
            for field in self._fields:
                if field in excluded_fields or self._fields[field].type in ['one2many', 'many2many']:
                    continue
                field_type = self._fields[field].type
                base_fields[field] = self[field].id if field_type == 'many2one' else self[field]

            base_fields.update({
                'name': name,
                'code': name,
                'rs_project_id': project.id,
                'floor': str(next_floor),
                'state': 'free',
            })

            new_unit = self.env['sub.property'].create(base_fields)

            # علاقات One2many
            for line in self.furniture_ids:
                new_unit.furniture_ids.create({
                    'property_id': new_unit.id,
                    **{f: line[f] for f in line._fields if
                       f not in ['id', 'property_id', '__last_update', 'display_name']}
                })
            for attach in self.property_attachment_ids:
                new_unit.property_attachment_ids.create({
                    'prop_attachment_id': new_unit.id,
                    **{f: attach[f] for f in attach._fields if
                       f not in ['id', 'prop_attachment_id', '__last_update', 'display_name']}
                })
            for img in self.sub_property_images_ids:
                new_unit.sub_property_images_ids.create({
                    'sub_property_id': new_unit.id,
                    **{f: img[f] for f in img._fields if
                       f not in ['id', 'sub_property_id', '__last_update', 'display_name']}
                })

        # بعد التكرار، فتح آخر وحدة
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sub.property',
            'res_id': new_unit.id,
            'view_mode': 'form',
            'target': 'current',
        }
        # self.ensure_one()
        # project = self.rs_project_id
        #
        # # تحديد الدور ورقم الوحدة الحالي
        # floor = int(self.floor or 1)
        # unit = int(self.code.split("-")[-1]) if self.code else 1
        #
        # # إعداد الوحدة التالية
        # unit += 1
        # if unit > project.props_per_floor:
        #     unit = 1
        #     floor += 1
        #
        # # حماية من التكرار المفرط
        # if floor > project.no_of_floors:
        #     raise ValidationError("❌ تم إنشاء جميع الوحدات المحددة في المشروع.")
        #
        # # إعداد الكود الجديد
        # name = f'{project.code}-{floor}-{unit}'
        #
        # # حماية من تكرار الكود
        # if self.env['sub.property'].search_count([('code', '=', name)]):
        #     raise ValidationError(f"❌ الوحدة برقم {name} موجودة بالفعل.")
        #
        # # إعداد القيم الأساسية مع مراعاة many2one
        # excluded_fields = ['id', 'name', 'code', 'floor', 'state', '__last_update', 'display_name']
        # base_fields = {}
        # for field in self._fields:
        #     if field in excluded_fields or self._fields[field].type in ['one2many', 'many2many']:
        #         continue
        #     field_type = self._fields[field].type
        #     if field_type == 'many2one':
        #         base_fields[field] = self[field].id
        #     else:
        #         base_fields[field] = self[field]
        #
        # # إضافة الحقول المتغيرة يدويًا
        # base_fields.update({
        #     'name': name,
        #     'code': name,
        #     'rs_project_id': project.id,
        #     'floor': str(floor),
        #     'state': 'free',
        # })
        #
        # # إنشاء الوحدة الجديدة
        # new_unit = self.env['sub.property'].create(base_fields)
        #
        # # تكرار العلاقات One2many
        # for line in self.furniture_ids:
        #     new_unit.furniture_ids.create({
        #         'property_id': new_unit.id,
        #         **{f: line[f] for f in line._fields if f not in ['id', 'property_id', '__last_update', 'display_name']}
        #     })
        #
        # for attach in self.property_attachment_ids:
        #     new_unit.property_attachment_ids.create({
        #         'prop_attachment_id': new_unit.id,
        #         **{f: attach[f] for f in attach._fields if
        #            f not in ['id', 'prop_attachment_id', '__last_update', 'display_name']}
        #     })
        #
        # for img in self.sub_property_images_ids:
        #     new_unit.sub_property_images_ids.create({
        #         'sub_property_id': new_unit.id,
        #         **{f: img[f] for f in img._fields if
        #            f not in ['id', 'sub_property_id', '__last_update', 'display_name']}
        #     })
        #
        # # فتح النموذج الجديد
        # return {
        #     'type': 'ir.actions.act_window',
        #     'res_model': 'sub.property',
        #     'res_id': new_unit.id,
        #     'view_mode': 'form',
        #     'target': 'current',
        # }

    @api.onchange('rs_project_id')
    def onchange_region(self):
        """This method updates address-related fields, such as 'street,' 'street2,' 'city,' 'country_id,' and 'zip,' based on the selected 'rs_project_id.'"""
        if self.rs_project_id:
            self.street = self.rs_project_id.street
            self.street2 = self.rs_project_id.street2
            self.city = self.rs_project_id.city
            self.country_id = self.rs_project_id.country_id.id
            self.zip = self.rs_project_id.zip

    def make_reservation(self):
        """This function creates a reservation for a rs_project unit, updating various fields, and then opens the reservation record in the Odoo user interface for further interaction."""
        full_address = ""
        if self.street:
            full_address += self.street
        if self.street2:
            if full_address:
                full_address += ", " + self.street2
            else:
                full_address += self.street2
        if self.city:
            if full_address:
                full_address += ", " + self.city
            else:
                full_address += self.city
        if self.zip:
            if full_address:
                full_address += ", " + self.zip
            else:
                full_address += self.zip
        if self.state_id:
            if full_address:
                full_address += ", " + self.state_id
            else:
                full_address += self.state_id
        for unit in self:
            code = unit.code
            rs_project_unit = unit.id
            address = full_address
            floor = unit.floor
            pricing = unit.pricing
            type = unit.ptype.id
            status = unit.status.id
            rs_project = unit.rs_project_id.id
            rs_project_code = unit.rs_project_id.code
            region = unit.region.id
            rs_project_area = unit.rs_project_area
            unit.state = 'reserved'
        reservation = self.env['unit.reservation']
        reservation_id = reservation.create({'region': region,
                                             'rs_project_code': rs_project_code,
                                             'rs_project': rs_project,
                                             'unit_code': code,
                                             'floor': floor,
                                             'pricing': pricing,
                                             'type': type,
                                             'address': address,
                                             'status': status,
                                             'rs_project_area': rs_project_area,
                                             'rs_project_unit': rs_project_unit})
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'unit.reservation',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': reservation_id.id,
        }

    def view_reservations(self):
        """This function retrieves and displays a list of reservations associated with the selected rs_project units in the Odoo user interface, allowing users to view and manage the reservations."""
        reservation = self.env['unit.reservation']
        reservations_ids = reservation.search([('rs_project_unit', '=', self.ids)])
        reservations = []
        for re in reservations_ids: reservations.append(re.id)
        return {
            'name': _('Reservation'),
            'domain': [('id', 'in', reservations)],
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'unit.reservation',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'target': 'current',
        }

    def _reservation_count(self):
        """This function calculates and updates the 'reservation_count' field with the count of reservations associated with the rs_project unit."""
        reservation = self.env['unit.reservation']
        for unit in self:
            reservations_ids = reservation.search([('rs_project_unit', '=', unit.id)])
            unit.reservation_count = len(reservations_ids)

    def transfer_furniture_products(self):
        """This function transfers furniture products from one location to another by creating a stock transfer order, validating it, and updating the status of the related furniture reservation lines accordingly."""
        lines_stock = []
        location_id = int(self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.location_id'))
        location_dest_id = int(self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.location_dest_id'))
        if not location_id:
            raise UserError(_('Please set source location from setting!'))
        if not location_dest_id:
            raise UserError(_('Please set destination location from setting!'))


        for rec in self:
            if rec.furniture_ids:
                for line in rec.furniture_ids:
                    if not line.product_id:
                        raise UserError(_("You cannot validate a transfer if no Products are reserved."))
                    if not line.product_qty:
                        raise UserError(_("You cannot validate a transfer if no quantities are reserved."))
                    if line.transfer == False and line.check == True:
                        lines_stock.append((0, 0, {
                            'name': line.product_id.name,
                            'product_id': line.product_id.id,
                            'product_uom': line.product_id.uom_id.id,
                            'location_id': location_id,
                            'location_dest_id': location_dest_id,
                            'product_uom_qty': line.product_qty,
                            'quantity_done': line.product_qty,
                        }))
                        transfer_order = self.env['stock.picking'].create({
                            'picking_type_id': self.env.ref('stock.picking_type_internal').id,
                            'location_id': location_id,
                            'location_dest_id': location_dest_id,
                            'immediate_transfer': True,
                            'move_ids_without_package': lines_stock
                        })
                        transfer_order.button_validate()
                        line.transfer = True
                        line.check = False
            else:
                raise UserError(_("You cannot validate a transfer if no Products are reserved."))

    def action_transfer_reverse(self):
        """This function performs a reverse transfer of reserved furniture products by creating a stock transfer order, validating it, and updating the status of the related furniture reservation lines accordingly."""
        lines_stock = []
        location_id = int(self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.location_id'))
        location_dest_id = int(self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.location_dest_id'))

        if not location_id:
            raise UserError(_('Please set source location from setting!'))
        if not location_dest_id:
            raise UserError(_('Please set destination location from setting!'))

        for rec in self:
            if rec.furniture_ids:
                for line in rec.furniture_ids:
                    if not line.product_id:
                        raise UserError(_("You cannot validate a reverse if no Products are reserved."))
                    if not line.product_qty:
                        raise UserError(_("You cannot validate a reverse if no quantities are reserved."))
                    if line.transfer == True and line.check == True:
                        lines_stock.append((0, 0, {
                            'name': line.product_id.name,
                            'product_id': line.product_id.id,
                            'product_uom': line.product_id.uom_id.id,
                            'location_id': location_dest_id,
                            'location_dest_id': location_id,
                            'product_uom_qty': line.product_qty,
                            'quantity_done': line.product_qty,
                        }))
                        transfer_order = self.env['stock.picking'].create({
                            'picking_type_id': self.env.ref('stock.picking_type_internal').id,
                            'location_id': location_dest_id,
                            'location_dest_id': location_id,
                            'immediate_transfer': True,
                            'move_ids_without_package': lines_stock
                        })
                        transfer_order.button_validate()
                        line.transfer = False
                        line.check = False
            else:
                raise UserError(_("You cannot validate a transfer if no Products are reserved."))

    def action_send_owner_portal_invite(self):
        """Send portal invitation to owner"""
        self.ensure_one()
        
        if not self.partner_id:
            raise UserError(_("No owner is assigned to this property."))
        
        if not self.partner_id.email:
            raise UserError(_("Owner email is not set. Please add email address first."))
        
        # Check if user already exists
        existing_user = self.env['res.users'].search([
            ('partner_id', '=', self.partner_id.id)
        ], limit=1)
        
        if existing_user:
            self.message_post(
                body=f"Portal user already exists for owner: {self.partner_id.name} ({self.partner_id.email})"
            )
            return
        
        # Add to portal group if not already added
        portal_group = self.env.ref('base.group_portal')
        if portal_group not in self.partner_id.category_id:
            self.partner_id.write({'category_id': [(4, portal_group.id)]})
        
        # Create portal user
        user_vals = {
            'name': self.partner_id.name,
            'login': self.partner_id.email,
            'email': self.partner_id.email,
            'partner_id': self.partner_id.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        }
        
        new_user = self.env['res.users'].create(user_vals)
        
        # Send invitation email
        template = self.env.ref('auth_signup.mail_template_user_signup_account_created')
        if template:
            new_user.with_context(
                create_user=True,
                website_id=self.env['website'].get_current_website().id
            ).action_reset_password()
        
        self.message_post(
            body=f"Portal invitation sent to owner: {self.partner_id.name} ({self.partner_id.email})"
        )

    def action_send_tenant_portal_invite(self):
        """Send portal invitation to tenant"""
        self.ensure_one()
        
        if not self.tenant_id:
            raise UserError(_("No tenant is assigned to this property."))
        
        if not self.tenant_id.email:
            raise UserError(_("Tenant email is not set. Please add email address first."))
        
        # Check if user already exists
        existing_user = self.env['res.users'].search([
            ('partner_id', '=', self.tenant_id.id)
        ], limit=1)
        
        if existing_user:
            self.message_post(
                body=f"Portal user already exists for tenant: {self.tenant_id.name} ({self.tenant_id.email})"
            )
            return
        
        # Add to portal group if not already added
        portal_group = self.env.ref('base.group_portal')
        if portal_group not in self.tenant_id.category_id:
            self.tenant_id.write({'category_id': [(4, portal_group.id)]})
        
        # Create portal user
        user_vals = {
            'name': self.tenant_id.name,
            'login': self.tenant_id.email,
            'email': self.tenant_id.email,
            'partner_id': self.tenant_id.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        }
        
        new_user = self.env['res.users'].create(user_vals)
        
        # Send invitation email
        template = self.env.ref('auth_signup.mail_template_user_signup_account_created')
        if template:
            new_user.with_context(
                create_user=True,
                website_id=self.env['website'].get_current_website().id
            ).action_reset_password()
        
        self.message_post(
            body=f"Portal invitation sent to tenant: {self.tenant_id.name} ({self.tenant_id.email})"
        )


class Furniture(models.Model):
    _name = 'furniture'
    _description = "furniture"

    product_id = fields.Many2one("product.product", string=_("Product"), domain="[('furniture', '=', True)]")
    description = fields.Char(string=_('Description'), compute="_description_get", default=" ")
    list_price = fields.Float(related="product_id.list_price")
    property_id = fields.Many2one("sub.property")
    product_qty = fields.Integer(string=_("Quantity"), default=1)
    transfer = fields.Boolean('Transfer', default=False)
    check = fields.Boolean()


    @api.depends("product_id.name", "product_id.default_code")
    def _description_get(self):
        """This function to make description of furniture"""
        for record in self:
            if not record.product_id.default_code:
                descriptions = str(record.product_id.name)
                record.description = descriptions
            else:
                descriptions = str([record.product_id.default_code]) + str(record.product_id.name)
                record.description = descriptions





class PropertyAttachmentLine(models.Model):
    _name = 'property.attachment.line'
    _description = "property.attachment.line"

    name = fields.Char(string=_("Name"))
    file = fields.Binary(string=_("File"))
    prop_attachment_id = fields.Many2one("sub.property")


class SubPropertyImage(models.Model):
    _name = 'sub.property.image'
    _description = "sub.property.image"

    name = fields.Char(string=_("Image Name"), required=True)
    video_url = fields.Char(string=_("Video URL"))
    image = fields.Image()
    sub_property_id = fields.Many2one("sub.property")
