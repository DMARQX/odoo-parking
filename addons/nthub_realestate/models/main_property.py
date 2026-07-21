# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class MainProperty(models.Model):
    _name = 'rs.project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'main.property'

    name = fields.Char('Name')
    project_status_type = fields.Selection([
        ('new', 'New'),
        ('active', 'Active'),
        ('archived', 'Archived')
        ], string="Project Status", default='new', tracking=True)
    code = fields.Char(string='Code', required=True)
    region = fields.Many2one('regions', 'Region')
    partner_id = fields.Many2one('res.partner', 'Owner', domain="[('is_owner','=',True)]")
    purchase_date = fields.Date()
    launching_date = fields.Date()
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    property_type = fields.Many2one('rs.project.type')
    property_status = fields.Many2one('rs.project.status')
    rs_project_area = fields.Integer('Property Area m^2')
    land_area = fields.Integer('Land Area m^2')
    constructed = fields.Date('Construction Date')
    lift = fields.Integer('Passenger Elevators')
    lift_f = fields.Integer('Freight Elevators')
    pricing = fields.Integer('Price')
    no_of_floors = fields.Integer('Floors')
    props_per_floor = fields.Integer('Units Per Floor')
    surface = fields.Integer('Surface')
    garage = fields.Integer('Garage Included')
    garden = fields.Integer('Garden m^2')
    north = fields.Char('Northern border by')
    south = fields.Char('Southern border by')
    east = fields.Char('Eastern border by')
    west = fields.Char('Western border by')
    license_code = fields.Char('License Code')
    license_date = fields.Date('License Date')
    date_added = fields.Date('Date Added to Notarization')
    license_notarization = fields.Char('License Notarization')
    note = fields.Text()
    subproperties_ids = fields.One2many('sub.property', 'rs_project_id')
    rs_project_attachment_ids = fields.One2many('rs.project.attachment.line','rs_project_attachment_id')
    rs_project_image_ids = fields.One2many('rs.project.images', 'rs_project_id')
    rs_project_floor_plans = fields.One2many('rs.project.floor.plans', 'rs_project_id')
    
    sub_properties_created = fields.Boolean('Sub Properties Created', default=False)
    street = fields.Char(string=_('Street'))
    street2 = fields.Char(string=_('Street2'))
    city = fields.Char(string=_('City'))
    country_id = fields.Many2one('res.country')
    zip = fields.Char(string=_('Zip'))
    state_id = fields.Many2one('res.country.state')
    image = fields.Image(_("Image"))
    quantity = fields.Integer(string="Quantity", compute='get_propreties_number')
    total_projects_sold = fields.Integer(compute="total_projects_sold_state")
    count_of_proprety = fields.Integer(compute="count_of_proprety_project")
    is_create_unit = fields.Boolean()
    
    # Project Service Fee Percentage
    project_service_fee_percent = fields.Float(
        string='Project Service Fee %',
        digits=(16, 2),
        default=0.0,
        help='Service fee percentage to be applied on units in this project'
    )

    def action_create_portal_user(self):
        for project in self:
            if not project.partner_id:
                raise UserError(_("Please select a partner first."))

            if not project.partner_id.email:
                raise UserError(_("The partner must have an email address."))

            existing_user = self.env['res.users'].sudo().search([
                ('partner_id', '=', project.partner_id.id)
            ], limit=1)

            if existing_user:
                raise UserError(_("This partner already has a user account."))

            user = self.env['res.users'].sudo().create({
                'name': project.partner_id.name,
                'login': project.partner_id.email,
                'email': project.partner_id.email,
                'partner_id': project.partner_id.id,
                'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
            })

            # Send password reset email (with signup link)
            user.action_reset_password()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('User Created'),
                    'message': _('A password setup link has been sent to %s.') % user.email,
                    'type': 'success',
                    'sticky': False,
                }
            }

    _sql_constraints = [
        ('unique_code', 'UNIQUE (code)', 'The code field must be unique.'),
    ]


    # === START: الحقول الجديدة لمواد العقد ===
    contract_article_1 = fields.Html(string="المادة رقم (1) المقدمة")
    contract_article_2 = fields.Html(string="المادة رقم (2) تعيين الطرف الثاني ونطاق العمل")
    contract_article_3 = fields.Html(string="المادة رقم (3) تفصيل واجبات الطرفان")
    contract_article_4 = fields.Html(string="المادة رقم (4) مكاتب الطرف الثاني")
    contract_article_5 = fields.Html(string="المادة رقم (5) الأتعاب وشروط الدفع")
    contract_article_6 = fields.Html(string="المادة رقم (6) تأخير الأتعاب")
    contract_article_7 = fields.Html(string="المادة رقم (7) موجبات الفسخ")
    contract_article_8 = fields.Html(string="المادة رقم (8) القوة القاهرة")
    contract_article_9 = fields.Html(string="المادة رقم (9) شروط خاصة")
    contract_article_10 = fields.Html(string="المادة رقم (10) شروط عامة")
    contract_article_11 = fields.Html(string="المادة رقم (11) حماية الطرفان من الأضرار")
    contract_article_12 = fields.Html(string="المادة رقم (12) النظام الواجب التطبيق")
    contract_article_13 = fields.Html(string="المادة رقم (13) المراسلات")
    contract_article_14 = fields.Html(string="المادة رقم (14) كامل الاتفاق")
    contract_approved = fields.Boolean(string="Contract Approved by Owner", readonly=True, copy=False)
    contract_signature = fields.Binary(string="Owner's Signature", readonly=True, copy=False)
    contract_approval_date = fields.Datetime(string="Contract Approval Date", readonly=True, copy=False)
    contract_approved = fields.Boolean(string="Contract Approved by Owner", readonly=True, copy=False)
    contract_signature = fields.Binary(string="Owner's Signature", readonly=True, copy=False)
    contract_approval_date = fields.Datetime(string="Contract Approval Date", readonly=True, copy=False)
    # === END: الحقول الجديدة لمواد العقد ===

    # === START: default_get لعرض القيم عند فتح الفورم ===
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        config = self.env['ir.config_parameter'].sudo()
        for i in range(1, 15):
            field = f'contract_article_{i}'
            key = f'nthub_realestate.{field}'
            if field in fields_list:
                res[field] = config.get_param(key, default='')
        return res

    # === START: create لتخزين القيم من الإعدادات لو مش موجودة في vals ===
    @api.model_create_multi
    def create(self, vals_list):
        config = self.env['ir.config_parameter'].sudo()
        for vals in vals_list:
            for i in range(1, 15):
                field = f'contract_article_{i}'
                key = f'nthub_realestate.{field}'
                if field not in vals or not vals[field]:
                    vals[field] = config.get_param(key, default='')
        return super().create(vals_list)

    # === START: write لتحديث الحقول الفارغة بالقيم الافتراضية لو مستخدم ضغط "تعديل" ===
    def write(self, vals):
        config_params = self.env['ir.config_parameter'].sudo()
        for rec in self:
            for i in range(1, 15):
                field = f'contract_article_{i}'
                key = f'nthub_realestate.{field}'
                if field not in vals or not vals.get(field):
                    if not getattr(rec, field):
                        vals[field] = config_params.get_param(key, default='')
        return super().write(vals)



    # --- Stored Total Units ---
    @api.depends('subproperties_ids')
    def _compute_quantity(self):
        for project in self:
            project.quantity = len(project.subproperties_ids)

    quantity = fields.Integer(string="Total Units", compute='_compute_quantity', store=True)






    # --- NEW: Override create() method to send email ---
    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to send an email to the project owner upon creation.
        """
        # First, create the project(s) by calling the original create method
        projects = super(MainProperty, self).create(vals_list)


        # Find the email template. IMPORTANT: Replace 'nthub_realestate' with your module's technical name.
        template = self.env.ref('nthub_realestate.email_template_new_project_creation', raise_if_not_found=False)
        print(template)
        if not template:
            _logger.warning("Could not find email template 'email_template_new_project_creation'")
            return projects

        # Now, for each newly created project, send the notification email
        for project in projects:
            if project.partner_id and project.partner_id.email:
                # Send the email using the template
                template.send_mail(project.id, force_send=True)

        return projects

    # --- Stored Rented/Available/Occupancy Stats ---
    @api.depends('subproperties_ids.state')
    def _compute_unit_stats(self):
        for project in self:
            total_units = project.quantity
            rented_units_count = len(project.subproperties_ids.filtered(lambda u: u.state == 'on_lease'))

            project.rented_units_count = rented_units_count
            project.available_units_count = total_units - rented_units_count
            project.occupancy_rate = float_round((rented_units_count / total_units) * 100,
                                                 precision_digits=0) if total_units > 0 else 0.0

    available_units_count = fields.Integer(string="Available Units", compute='_compute_unit_stats', store=True)
    rented_units_count = fields.Integer(string="Rented Units", compute='_compute_unit_stats', store=True)
    occupancy_rate = fields.Float(string="Occupancy Rate (%)", compute='_compute_unit_stats', store=True,
                                  group_operator='avg')

    # --- Stored Sold Stats ---
    @api.depends('subproperties_ids.state', 'subproperties_ids.pricing')
    def _compute_sold_stats(self):
        for project in self:
            sold_units = project.subproperties_ids.filtered(lambda u: u.state == 'sold')
            project.total_projects_sold = sum(sold_units.mapped('pricing'))
            project.count_of_proprety = len(sold_units)

    total_projects_sold = fields.Monetary(string="Value of Sold Units", compute="_compute_sold_stats", store=True,
                                          currency_field='company_currency_id')
    count_of_proprety = fields.Integer(string="Number of Sold Units", compute="_compute_sold_stats", store=True)

    # --- Stored Revenue Stats ---
    @api.depends('subproperties_ids.state', 'subproperties_ids.rental_fee')
    def _compute_monthly_revenue(self):
        for project in self:
            # Calculate monthly revenue from confirmed rental contracts
            confirmed_contracts = self.env['rental.contract'].search([
                ('rs_project', '=', project.id),
                ('state', 'in', ['confirm', 'confirmed', 'done'])
            ])
            
            total_revenue = 0.0
            for contract in confirmed_contracts:
                # Monthly revenue = rental_fee + service_fee (if monthly) + electricity_fee (if monthly)
                monthly_fee = contract.rental_fee or 0.0
                
                # Add service_fee if monthly
                if contract.service_monthly:
                    monthly_fee += contract.service_fee or 0.0
                
                # Add electricity_fee if monthly and not included
                if contract.electricity_monthly and not contract.is_electricity_included:
                    monthly_fee += contract.electricity_fee or 0.0
                
                # Add tax if not included in amounts
                if not contract.tax_included and contract.tax_rate:
                    tax_rate_decimal = contract.tax_rate / 100
                    monthly_fee += monthly_fee * tax_rate_decimal
                
                total_revenue += monthly_fee
            
            project.monthly_revenue = total_revenue

    monthly_revenue = fields.Monetary(string="Monthly Revenue", compute="_compute_monthly_revenue", store=True,
                                      currency_field='company_currency_id')

    # --- Stored Currency Field ---
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Company Currency', store=True)


    def get_propreties_number(self):
        self.quantity = len(self.subproperties_ids)
        wn_obj = self.env['sub.property']
        own_ids = wn_obj.search_count([('rs_project_id', '=', self.id)])

    @api.depends("subproperties_ids", "subproperties_ids.pricing")
    def total_projects_sold_state(self):
        for rec in self:
            rec.total_projects_sold = sum(
                rec.subproperties_ids.filtered(lambda x: x.state == "sold").mapped("pricing"))

    @api.depends("subproperties_ids")
    def count_of_proprety_project(self):
        for rec in self:
            rec.count_of_proprety = len(rec.subproperties_ids.filtered(lambda x: x.state == "sold"))

    def get_number_propreties(self):
        return {
            'name': _('property'),
            'domain': [('rs_project_id', '=', self.id)],
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'sub.property',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'target': 'current',
        }

    @api.onchange('region')
    def onchange_region(self):
        """
        This method is When the 'region' field is changed, this method ensures that the 'street', 'street2', 'city',
        'country_id', and 'zip' fields are updated accordingly.
        """
        if self.region:
            self.street = self.region.street
            self.street2 = self.region.street2
            self.city = self.region.city
            self.country_id = self.region.country_id.id
            self.zip = self.region.zip

    can_add_more_units = fields.Boolean(compute="_compute_can_add_more_units")
    first_unit_created = fields.Boolean(compute="_compute_first_unit_created")

    @api.depends('subproperties_ids')
    def _compute_first_unit_created(self):
        for rec in self:
            rec.first_unit_created = bool(rec.subproperties_ids)
    @api.depends('subproperties_ids', 'no_of_floors', 'props_per_floor')
    def _compute_can_add_more_units(self):
        for rec in self:
            max_units = rec.no_of_floors * rec.props_per_floor
            rec.can_add_more_units = len(rec.subproperties_ids) < max_units
    def generate_subproperties(self):


        self.ensure_one()


        if not self.no_of_floors or not self.props_per_floor:
            raise ValidationError("من فضلك أدخل عدد الأدوار وعدد الوحدات.")

        if self.subproperties_ids:
            raise ValidationError("تم إنشاء أول وحدة بالفعل.")

        floor = 1
        unit = 1
        name = f'{self.code}-{floor}-{unit}'
        self.is_create_unit = True

        self.env['sub.property'].create({
            'name': name,
            'code': name,
            'rs_project_id': self.id,
            'ptype': self.property_type.id,
            'status': self.property_status.id,
            'region': self.region.id,
            'street': self.street,
            'street2': self.street2,
            'country_id': self.country_id.id,
            'zip': self.zip,
            'state_id': self.state_id.id,
            'floor': str(floor),
        })

        # 🔁 إعادة تحميل النموذج
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
        # """
        #     This method generates subproperties based on the specified number of floors and units per floor.
        #      It clears existing subproperties before creating new ones.
        # """
        #
        # self.ensure_one()
        #
        # if not self.no_of_floors or not self.props_per_floor:
        #     raise ValidationError("من فضلك أدخل عدد الأدوار وعدد الوحدات.")
        #
        # self.subproperties_ids.unlink()
        #
        # floor = 1
        # unit = 1
        # name = f'{self.code}-{floor}-{unit}'
        #
        # sub = self.env['sub.property'].create({
        #     'name': name,
        #     'code': name,
        #     'rs_project_id': self.id,
        #     'ptype': self.property_type.id,
        #     'status': self.property_status.id,
        #     'region': self.region.id,
        #     'street': self.street,
        #     'street2': self.street2,
        #     'country_id': self.country_id.id,
        #     'zip': self.zip,
        #     'state_id': self.state_id.id,
        #     'floor': str(floor),
        # })


        # return {
        #     'type': 'ir.actions.act_window',
        #     'res_model': 'subproperty.repeat.wizard',
        #     'view_mode': 'form',
        #     'target': 'new',
        #     'context': {
        #         'default_rs_project_id': self.id,
        #         'default_current_floor': floor,
        #         'default_current_unit': unit,
        #         'default_last_subproperty_id': sub.id,
        #     }
        # }
        # if self.no_of_floors and self.props_per_floor:
        #     # It first checks if 'no_of_floors' and 'props_per_floor' are both filled.
        #     for do in self.subproperties_ids:
        #         do.unlink()
        #     for floor in range(1, self.no_of_floors + 1):
        #         for unit in range(1, self.props_per_floor + 1):
        #             subproperty_name = f'{self.code}-{floor}-{unit}'
        #             subproperty = {
        #                 'name': subproperty_name,
        #                 'code': subproperty_name,
        #                 'rs_project_id': self.id,
        #                 'ptype': self.property_type.id,
        #                 'status': self.property_status.id,
        #                 'region': self.region.id,
        #                 'street': self.street,
        #                 'street2': self.street2,
        #                 'country_id': self.country_id,
        #                 'zip': self.zip,
        #                 'state_id': self.state_id.id,
        #                 'floor': str(floor),
        #             }
        #             self.env['sub.property'].create(subproperty)
        #     self.sub_properties_created = True
        # else:
        #     # ValidationError: If any of the required fields (Name, Number of floors, Units per floor) is not filled.
        #     raise ValidationError("please fill all required fields. (Name , Number of floors, Units per floor)")

    def action_generate_next_unit(self):
        """
        زر يقوم بإنشاء وحدة واحدة فقط في كل مرة، مع مراعاة العدد الأقصى المسموح به من الأدوار والوحدات.
        """
        self.ensure_one()

        if not self.no_of_floors or not self.props_per_floor:
            raise ValidationError("من فضلك أدخل عدد الأدوار وعدد الوحدات لكل دور.")

        def safe_floor_int(floor_value):
            """Convert floor to int safely, handling Arabic text like 'الأرضي' (ground floor)"""
            if not floor_value:
                return 0
            try:
                return int(floor_value)
            except (ValueError, TypeError):
                # Handle Arabic floor names - ground floor = 0
                return 0

        existing_units = self.subproperties_ids.sorted(key=lambda r: (safe_floor_int(r.floor), r.code or ''))
        total_units = len(existing_units)
        max_units = self.no_of_floors * self.props_per_floor

        if total_units >= max_units:
            raise ValidationError("تم إنشاء جميع الوحدات المحددة لهذا المشروع.")

        next_floor = (total_units // self.props_per_floor) + 1
        next_unit = (total_units % self.props_per_floor) + 1

        name = f'{self.code}-{next_floor}-{next_unit}'

        if self.env['sub.property'].search_count([('code', '=', name)]):
            raise ValidationError(f"الوحدة {name} موجودة بالفعل.")

        self.env['sub.property'].create({
            'name': name,
            'code': name,
            'rs_project_id': self.id,
            'ptype': self.property_type.id,
            'status': self.property_status.id,
            'region': self.region.id,
            'street': self.street,
            'street2': self.street2,
            'country_id': self.country_id.id,
            'zip': self.zip,
            'state_id': self.state_id.id,
            'floor': str(next_floor),
        })

        # ✅ إعادة تحميل صفحة المشروع
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class RsProjectAttachmentLine(models.Model):
    _name = 'rs.project.attachment.line'
    _description = "rs.project.attachment.line"

    name = fields.Char(string=_("Name"))
    file = fields.Binary(string=_("File"))
    rs_project_attachment_id = fields.Many2one("rs.project", string="Project")


class RsProjectImage(models.Model):
    _name = 'rs.project.images'
    _description = "rs.project.images"

    name = fields.Char(string=_("Image Name"), required=True)
    video_url = fields.Char(string=_("Video URL"))
    image = fields.Image()
    rs_project_id = fields.Many2one("rs.project",string="Project")


class RsProjectFloorPlans(models.Model):
    _name = 'rs.project.floor.plans'
    _description = "rs.project.floor.plans"

    name = fields.Char(string=_("Image Name"), required=True)
    video_url = fields.Char(string=_("Video URL"))
    image = fields.Image()
    rs_project_id = fields.Many2one("rs.project", string="Project")

