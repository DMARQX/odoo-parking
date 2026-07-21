# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Bilingual name fields
    name_english = fields.Char(
        string="Name (English) / الاسم بالإنجليزية",
        help="Partner name in English"
    )
    name_arabic = fields.Char(
        string="Name (Arabic) / الاسم بالعربية",
        help="Partner name in Arabic"
    )
    
    # Keep name_en for backward compatibility
    name_en = fields.Char(
        string="Name (English)",
        compute='_compute_name_en',
        inverse='_inverse_name_en',
        store=True
    )
    
    @api.depends('name_english')
    def _compute_name_en(self):
        for partner in self:
            partner.name_en = partner.name_english
    
    def _inverse_name_en(self):
        for partner in self:
            partner.name_english = partner.name_en
    
    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """Override name search to search in both English and Arabic names"""
        args = args or []
        if name:
            # Search in name, name_english, and name_arabic
            domain = ['|', '|', 
                     ('name', operator, name),
                     ('name_english', operator, name),
                     ('name_arabic', operator, name)]
            return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
        return super()._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)
    
    def _compute_display_name(self):
        """Display name based on user language context"""
        for partner in self:
            # Get user's language
            lang = self.env.context.get('lang', 'en_US')
            
            # If Arabic language and Arabic name exists, use it
            if lang and lang.startswith('ar') and partner.name_arabic:
                partner.display_name = partner.name_arabic
            # If English name exists, use it
            elif partner.name_english:
                partner.display_name = partner.name_english
            # Otherwise use default name
            else:
                super(ResPartner, partner)._compute_display_name()
    
    # Tenant information fields
    is_tenant = fields.Boolean(string="Is Tenant", default=False)
    is_owner = fields.Boolean(string="Is Owner", default=False)
    is_contractor = fields.Boolean(string="Is Contractor", default=False)
    is_contractor_supervisor = fields.Boolean(string="Is Contractor Supervisor", default=False)
    tenant_name = fields.Char(string="Tenant Name", translate=True)
    trade_name = fields.Char(string="Trade Name", translate=True)
    activity = fields.Text(string="Activity", translate=True)
    
    # Related fields to standard Odoo fields
    commercial_registration_no = fields.Char(
        string="Commercial Registration No.",
        related='company_registry',
        readonly=False,
        store=True
    )
    unified_number = fields.Char(
        string="Unified Number",
        related='ref',
        readonly=False,
        store=True
    )
    commercial_registration_validity = fields.Date(string="Commercial Registration Validity")
    vat_number = fields.Char(
        string="VAT Number",
        related='vat',
        readonly=False,
        store=True
    )
    company_age = fields.Integer(string="Company Age (Years)")
    current_location = fields.Text(string="Current Location")
    number_of_employees = fields.Integer(string="Number of Employees")
    number_of_companies = fields.Integer(string="Number of Companies (if any)")
    companies_activity = fields.Text(string="Activity of Companies (if any)")
    international_location = fields.Selection([
        ('international', 'International'),
        ('local', 'Local')
    ], string="International / Location")
    capital_of_company = fields.Monetary(string="Capital of Company")
    capital_investment = fields.Monetary(string="Capital Investment")
    credit_record = fields.Text(string="Credit Record")
    financial_performance = fields.Text(string="Financial Performance")
    legal_cases = fields.Boolean(string="Legal Cases", default=False)
    legal_cases_details = fields.Text(string="Legal Cases Details", 
                                     help="Provide details if there are any legal cases")
    company_owners_cv = fields.Text(string="CV of Company Owners")
    number_of_existing_projects = fields.Integer(string="Number of Existing Projects")
    number_of_future_projects = fields.Integer(string="Number of Future Projects")

    def action_print_tenant_form(self):
        """Print tenant information form"""
        self.ensure_one()
        return self.env.ref('nthub_realestate.tenant_information_report').report_action(self)