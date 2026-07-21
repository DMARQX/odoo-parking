# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class OfferPresentation(models.Model):
    _name = 'offer.presentation'
    _description = 'Request for Quotation'
    _rec_name = 'company_name'

    # Basic Information
    company_name = fields.Char(string="Company Name / اسم الشركة", required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    project_id = fields.Many2one('rs.project', string="Project / المشروع", required=True)
    responsible_name = fields.Char(string="Responsible Name / اسم المسؤول")
    responsible_department = fields.Char(string="Responsible Department / الجهة المسؤولة")
    phone_number = fields.Char(string="Phone Number / رقم الهاتف")
    fax_number = fields.Char(string="Fax Number / رقم الفاكس")
    mobile_number = fields.Char(string="Mobile Number / رقم الجوال")
    email = fields.Char(string="Email / البريد الإلكتروني")
    center_name = fields.Char(string="Center/Project Name / اسم المركز/المشروع", default="KRT")

    # Office/Unit Details (One2many relationship for multiple units)
    offer_line_ids = fields.One2many('offer.presentation.line', 'offer_id', string="Office/Unit Details")
    
    # Communication Method
    communication_method = fields.Selection([
        ('call', 'Call / إتصال'),
        ('visit', 'Visit / زيارة'),
        ('targeting', 'Targeting / إستهداف'),
        ('other', 'Other / أخرى')
    ], string="Communication Method / طريقة التواصل")
    
    # Additional Information
    notes = fields.Text(string="Notes / ملاحظات")
    marketer_name = fields.Char(string="Marketer Name / اسم المسوق")
    signature = fields.Char(string="Signature / التوقيع")
    
    # Date
    presentation_date = fields.Date(string="Date / التاريخ", default=fields.Date.today)
    
    # Track quotation creation
    quotation_count = fields.Integer(string="Quotation Count", default=0, copy=False)

    def action_print_offer_form(self):
        """Print offer presentation form"""
        self.ensure_one()
        return self.env.ref('nthub_realestate.offer_presentation_report').report_action(self)

    def action_create_rental_quotation(self):
        """إنشاء عارض سعر جديد من نموذج العرض التقديمي"""
        self.ensure_one()
        
        # التحقق من وجود وحدات في العرض
        if not self.offer_line_ids:
            raise UserError(_("Cannot create rental quotation without any units. Please add units first."))
        
        # البحث عن العميل أو إنشاؤه
        partner = self.env['res.partner'].search([
            ('name', '=', self.company_name)
        ], limit=1)
        
        if not partner:
            # إنشاء عميل جديد
            partner = self.env['res.partner'].create({
                'name': self.company_name,
                'email': self.email,
                'phone': self.phone_number,
                'mobile': self.mobile_number,
                'is_company': True,
                'comment': f"Created from offer presentation: {self.presentation_date}"
            })
        
        # إنشاء عارض السعر
        quotation_vals = {
            'partner_id': partner.id,
            'quotation_date': self.presentation_date or fields.Date.today(),
            'salesperson_id': self.env.user.id,
            'contact_person_name': self.responsible_name or '',  # نقل اسم المسؤول إلى اسم الأستاذ
            'notes': self.notes or '',
        }
        
        quotation = self.env['rental.quotation'].create(quotation_vals)
        
        # إنشاء خطوط عارض السعر من الوحدات المختارة
        for line in self.offer_line_ids:
            if line.unit_id:  # التأكد من وجود وحدة مختارة
                quotation_line_vals = {
                    'quotation_id': quotation.id,
                    'property_id': line.unit_id.id,
                    'property_area': float(line.area) if line.area else 0.0,
                    'rental_price_per_sqm': line.rental_price_per_sqm,
                    'service_fee': line.service_fee,
                    'description': f"Activity: {line.activity or 'N/A'}, Brand: {line.brand or 'N/A'}",
                }
                self.env['rental.quotation.line'].create(quotation_line_vals)
        
        # زيادة العداد بعد إنشاء عرض السعر
        self.quotation_count = 1
        
        # إرجاع action لفتح عارض السعر المُنشأ
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rental Quotation'),
            'view_mode': 'form',
            'res_model': 'rental.quotation',
            'res_id': quotation.id,
            'target': 'current',
        }


class OfferPresentationLine(models.Model):
    _name = 'offer.presentation.line'
    _description = 'Request for Quotation Line'

    offer_id = fields.Many2one('offer.presentation', string="Offer", ondelete='cascade')
    
    # ربط مع الوحدات المتاحة من المشروع المختار
    unit_id = fields.Many2one('sub.property', string="Unit / الوحدة", 
                              domain="[('rs_project_id', '=', parent.project_id), ('state', '=', 'free')]")
    office_number = fields.Char(string="Office/Unit Number / رقم العين/المكتب", related='unit_id.code', readonly=True)
    area = fields.Float(string="Area / المساحة", related='unit_id.rs_project_area', readonly=True)
    activity = fields.Char(string="Activity / النشاط")
    brand = fields.Char(string="Brand / الماركة")
    
    # سعر الإيجار لكل متر مربع (يدخله المستخدم)
    rental_price_per_sqm = fields.Float(
        string="Rental Price per m² / سعر الإيجار لكل م²",
        default=0.0
    )
    
    # نسبة رسوم الخدمة من المشروع
    project_service_fee_percent = fields.Float(
        string="Service Fee % / نسبة رسوم الخدمة",
        related='unit_id.rs_project_id.project_service_fee_percent',
        readonly=True
    )
    
    # رسوم الخدمة المحسوبة (للقراءة فقط)
    service_fee = fields.Float(
        string="Service Fee / رسوم الخدمة",
        compute='_compute_service_fee_and_total',
        store=True,
        readonly=True
    )
    
    # القيمة الإيجارية الإجمالية (محسوبة للقراءة فقط)
    rental_value = fields.Float(
        string="Rental Value + Services / القيمة الإيجارية + خدمات",
        compute='_compute_service_fee_and_total',
        store=True,
        readonly=True
    )
    
    # حقول إضافية من الوحدة
    unit_name = fields.Char(string="Unit Name / اسم الوحدة", related='unit_id.name', readonly=True)
    unit_type = fields.Char(string="Unit Type / نوع الوحدة", related='unit_id.ptype.name', readonly=True)
    
    @api.depends('rental_price_per_sqm', 'area', 'project_service_fee_percent')
    def _compute_service_fee_and_total(self):
        """حساب رسوم الخدمة والقيمة الإجمالية"""
        for line in self:
            # حساب رسوم الخدمة: (سعر الإيجار × المساحة) × (نسبة رسوم الخدمة / 100)
            base_rent = line.rental_price_per_sqm * line.area
            service_fee_percent = line.project_service_fee_percent or 0.0
            line.service_fee = base_rent * (service_fee_percent / 100)
            
            # القيمة الإجمالية = الإيجار الأساسي + رسوم الخدمة
            line.rental_value = base_rent + line.service_fee
    
    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        """تحديث البيانات عند اختيار وحدة جديدة"""
        if self.unit_id:
            # تحديث سعر الإيجار الافتراضي من الوحدة إذا كان متاحًا
            if self.unit_id.rental_price_per_sqm:
                self.rental_price_per_sqm = self.unit_id.rental_price_per_sqm