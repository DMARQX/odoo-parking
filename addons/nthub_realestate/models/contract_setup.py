# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta


class ContractSetup(models.Model):
    _name = 'contract.setup'
    _description = 'Contract Setup Information'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Basic Information
    name = fields.Char(
        string='Contract Name',
        required=True,
        default='Contract Setup Information'
    )
    
    date = fields.Date(
        string='Date',
        default=fields.Date.today,
        required=True
    )
    
    project_title = fields.Char(
        string='Project Title',
        default='King Road Tower - Jeddah'
    )
    
    # Project Link
    project_id = fields.Many2one(
        'rs.project',
        string='Project',
        required=True
    )
    
    # Company Information
    company_name = fields.Char(
        string='Company Name',
        required=True
    )
    
    unified_number = fields.Char(
        string='Unified Number',
        required=True
    )
    
    establishment_number = fields.Char(
        string='Establishment Number',
        required=True
    )
    
    commercial_register_source = fields.Char(
        string='Commercial Register Source',
        default='Jeddah'
    )
    
    commercial_register_date = fields.Char(
        string='Commercial Register Date'
    )
    
    main_address = fields.Text(
        string='Main Address'
    )
    
    # Postal Address
    postal_code = fields.Char(
        string='Postal Code'
    )
    
    city = fields.Char(
        string='City',
        default='Jeddah'
    )
    
    zip_code = fields.Char(
        string='ZIP Code'
    )
    
    # معلومات الاتصال
    phone = fields.Char(
        string='Phone | رقم الهـــاتـف'
    )
    
    fax = fields.Char(
        string='Fax | رقــم الفـاكـس'
    )
    
    # معلومات المفوض
    authorized_signatory = fields.Char(
        string='Authorized Signatory | اسـم المفـوض بالتـوقـيـع',
        required=True
    )
    
    nationality = fields.Char(
        string='Nationality | جـنـســيـتـه'
    )
    
    contractual_status = fields.Char(
        string='Contractual Status | صـفـتـه التـعــاقـديـة'
    )
    
    # أرقام الهوية والاتصال
    id_passport_number = fields.Char(
        string='ID/Passport Number | رقم الهوية / جواز السفر'
    )
    
    id_issue_place = fields.Char(
        string='ID Issue Place | مكان إصدارها'
    )
    
    mobile_number = fields.Char(
        string='Mobile Number | رقــم الجـــوال'
    )
    
    absher_mobile = fields.Char(
        string='Absher Mobile | رقم جوال أبشر'
    )
    
    # معلومات الوحدة/المكتب
    unit_id = fields.Many2one(
        'sub.property',
        string='Unit/Office | الوحدة/المكتب',
        domain="[('rs_project_id', '=', project_id), ('state', '=', 'free')]",
        required=True
    )
    
    unit_office_number = fields.Char(
        string='Unit/Office Number | رقم العين / المكتب رقم',
        related='unit_id.name',
        readonly=True
    )
    
    unit_area = fields.Float(
        string='Unit Area (m²) | المساحة (م²)',
        related='unit_id.rs_project_area',
        readonly=True
    )
    
    activity = fields.Text(
        string='Activity | النشــــــــــــاط'
    )
    
    # معلومات تجارية
    trade_name = fields.Char(
        string='Trade Name | الإسم التجاري / الماركــــة'
    )
    
    # القيم المالية
    rental_value = fields.Float(
        string='Rental Value | القيمة الإيجارية',
        digits=(10, 2)
    )
    
    services_value = fields.Float(
        string='Services Value | قيمة الخدمات',
        digits=(10, 2)
    )
    
    total_value = fields.Float(
        string='Total Value | إجمالي',
        compute='_compute_total_value',
        store=True,
        digits=(10, 2)
    )
    
    vat_amount = fields.Float(
        string='VAT Amount | قيمة الضريبة',
        digits=(10, 2)
    )
    
    # مدة العقد
    contract_duration = fields.Char(
        string='Contract Duration | مدة العقد',
        default='3 سنوات ميلادية'
    )
    
    contract_start_date = fields.Date(
        string='Contract Start Date | تاريخ بداية العقد'
    )
    
    # الملاحظات
    notes_1 = fields.Text(
        string='Notes 1 | ملاحظة 1'
    )
    
    notes_2 = fields.Text(
        string='Notes 2 | ملاحظة 2'
    )
    
    # مسئول المبيعات
    sales_manager = fields.Char(
        string='Sales Manager | اسم مسئول المبيعات'
    )
    
    # الحالة
    state = fields.Selection([
        ('draft', 'Draft | مسودة'),
        ('confirmed', 'Confirmed | مؤكد'),
        ('done', 'Done | منجز'),
    ], string='State | الحالة', default='draft')

    @api.depends('rental_value', 'services_value')
    def _compute_total_value(self):
        for record in self:
            record.total_value = record.rental_value + record.services_value

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """تحديث عنوان المشروع عند اختيار المشروع"""
        if self.project_id:
            self.project_title = self.project_id.name
            # مسح الوحدة المحددة عند تغيير المشروع
            self.unit_id = False
        else:
            self.project_title = 'برج طريق الملك – جدة'
            self.unit_id = False

    def action_confirm(self):
        """تأكيد إعداد العقد"""
        self.state = 'confirmed'

    def action_done(self):
        """إنجاز إعداد العقد"""
        self.state = 'done'

    def action_print_contract_setup(self):
        """طباعة إعداد العقد"""
        return self.env.ref('nthub_realestate.action_report_contract_setup').report_action(self)