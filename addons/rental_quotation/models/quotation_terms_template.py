# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class QuotationTermsTemplate(models.Model):
    _name = 'quotation.terms.template'
    _description = 'Quotation Terms and Conditions Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(
        string='Template Name',
        required=True,
        translate=True,
        tracking=True,
        help='Name of the terms and conditions template (e.g., "Residential Terms", "Commercial Terms")'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Used to order templates in selection lists'
    )
    
    language = fields.Selection([
        ('ar', 'Arabic / العربية'),
        ('en', 'English / الإنجليزية'),
    ], string='Language / اللغة', required=True, default='ar', 
       help='Language of this template')
    
    salutation_html = fields.Html(
        string='Salutation / التحية',
        sanitize=False,
        help='Greeting text shown above the rental fees table'
    )
    
    content_html = fields.Html(
        string='Lease Agreement Requirements & Conditions / متطلبات وشروط عقد الإيجار',
        sanitize=False,
        help='Requirements and conditions content (payment terms, documents required, etc.)'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Inactive templates will not be available for selection'
    )
    
    template_type = fields.Selection([
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('general', 'General'),
    ], string='Template Type', default='general', help='Category of the template')
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Template specific to a company (leave empty for all companies)'
    )
    
    note = fields.Text(
        string='Internal Notes',
        help='Internal notes about this template (not shown in quotations)'
    )
    
    _sql_constraints = [
        ('name_company_language_unique', 'UNIQUE(name, company_id, language)', 
         'Template name must be unique per company and language!')
    ]
    
    def name_get(self):
        """Display template name with language and type in selection lists"""
        result = []
        for record in self:
            name = record.name
            # Add language
            lang_label = 'AR' if record.language == 'ar' else 'EN'
            name = f"[{lang_label}] {name}"
            # Add type if not general
            if record.template_type != 'general':
                type_label = dict(self._fields['template_type'].selection).get(record.template_type, '')
                name = f"{name} ({type_label})"
            result.append((record.id, name))
        return result
