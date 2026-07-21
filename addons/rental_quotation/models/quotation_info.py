# -*- coding: utf-8 -*-

from odoo import models, fields, api

class QuotationInfo(models.Model):
    _name = 'rental.quotation.info'
    _description = 'Quotation Information Form'
    _rec_name = 'company_name'

    # Basic Company Information
    company_name = fields.Char(string='اسم الشركة / المؤسسة', required=True)
    responsible_person = fields.Char(string='اسم المسئول / الجهة المسئولة', required=True)
    phone = fields.Char(string='رقم الهاتف')
    fax = fields.Char(string='رقم الفاكس')
    mobile = fields.Char(string='رقم الجوال')
    email = fields.Char(string='البريد الإلكتروني E-Mail')
    
    # Project Information
    center_name = fields.Char(string='اسم المركز / المشروع', )
    
    # Property Details - One2many relationship for multiple properties
    property_ids = fields.One2many('rental.quotation.property', 'quotation_info_id', string='تفاصيل العقارات')
    
    # Communication Method
    communication_method = fields.Selection([
        ('phone_call', 'إتصال'),
        ('visit', 'زيارة'),
        ('targeting', 'إستهداف'),
        ('other', 'أخرى')
    ], string='طريقة التواصل مع العميل')
    
    # Notes
    notes = fields.Text(string='ملاحظات')
    
    # Employee and Approval
    marketer_name = fields.Many2one('res.users', string='اسم المسوق', default=lambda self: self.env.user)
    sales_manager_approval = fields.Many2one('res.users', string='إعتماد مدير المبيعات')
    
    # Date
    date = fields.Date(string='التاريخ', default=fields.Date.context_today)
    
    # Partner Link
    partner_id = fields.Many2one('res.partner', string='العميل')
    
    def action_print_quotation_info(self):
        """Print quotation information report"""
        return self.env.ref('rental_quotation.action_report_quotation_info').report_action(self)


class QuotationProperty(models.Model):
    _name = 'rental.quotation.property'
    _description = 'Quotation Property Details'
    
    quotation_info_id = fields.Many2one('rental.quotation.info', string='Quotation Info', ondelete='cascade')
    
    # Property Details
    property_number = fields.Char(string='رقم العين / المكتب')
    area = fields.Float(string='المساحة')
    activity = fields.Char(string='النشاط')  
    brand = fields.Char(string='الماركة')
    rental_value = fields.Float(string='القيمة الإيجارية + خدمات')
    
    # Property reference if linked to actual property
    property_id = fields.Many2one('itsys.real.estate.property', string='العقار')