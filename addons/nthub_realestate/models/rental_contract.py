# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from dateutil.relativedelta import relativedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class RentalContract(models.Model):
    _name = 'rental.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "rental.contract"
    _rec_name = "name"

    name = fields.Char(string=_("Reference"), readonly=True)
    date = fields.Date(string=_("Date"))
    user_id = fields.Many2one("res.users", string=_("Responsible"))
    partner_id = fields.Many2one("res.partner", string=_("Tenant"), domain="[('is_tenant', '=', True)]")
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    maintenance_fee = fields.Float(string="Maintenance Fee", default=0.0)
    electricity_fee = fields.Float(string="Electricity Fee", default=0.0)
    is_electricity_included = fields.Boolean(string="Electricity Included in Rent", default=False)
    maintenance_monthly = fields.Boolean(string="Is Maintenance Monthly?", default=False)
    electricity_monthly = fields.Boolean(string="Is Electricity Monthly?", default=False)
    service_monthly = fields.Boolean(string="Is Service Monthly?", default=False)
    service_rate = fields.Float(string="Service Rate (%)")
    service_value = fields.Float(string="Service Value (Monthly)", compute="_compute_service_value", store=True)
    service_included_in_rent = fields.Boolean(string="Is Service Included in Rent?", default=True)
    
    # حقل الضرائب M2M
    tax_ids = fields.Many2many(
        'account.tax',
        'rental_contract_tax_rel',
        'contract_id',
        'tax_id',
        string='Taxes / الضرائب',
        domain=[('type_tax_use', '=', 'sale')],
        default=lambda self: self._get_default_taxes(),
        help="Taxes applied to this rental contract"
    )
    
    @api.model
    def _get_default_taxes(self):
        """Get default sales taxes from company"""
        company = self.env.company
        # البحث عن ضريبة المبيعات الافتراضية للشركة
        default_tax = company.account_sale_tax_id
        if default_tax:
            return [(6, 0, [default_tax.id])]
        return [(6, 0, [])]

    @api.depends('rental_fee', 'service_rate')
    def _compute_service_value(self):
        for rec in self:
            if rec.rental_fee and rec.service_rate:
                rec.service_value = (rec.rental_fee * rec.service_rate) / 100
            else:
                rec.service_value = 0.0

    @api.depends('rental_fee', 'service_fee', 'electricity_fee')
    def _compute_total_rental_fee(self):
        """Calculate total rental fee: Rental Fee + Service Fee + Electricity Fee (per period)"""
        for rec in self:
            rec.total_rental_fee = (rec.rental_fee or 0.0) + (rec.service_fee or 0.0) + (rec.electricity_fee or 0.0)
    
    @api.depends('rental_fee', 'service_fee', 'electricity_fee', 'date_from', 'date_to', 'service_monthly', 'electricity_monthly', 'periodicity', 'recurring_interval')
    def _compute_total_contract_value(self):
        """Calculate total contract value for the entire period"""
        for rec in self:
            if not rec.date_from or not rec.date_to:
                rec.total_contract_value = 0.0
                continue
            
            # حساب عدد الشهور
            delta = relativedelta(rec.date_to, rec.date_from)
            total_months = delta.years * 12 + delta.months + (1 if delta.days > 0 else 0)
            
            if total_months <= 0:
                rec.total_contract_value = 0.0
                continue
            
            # الإيجار الأساسي (دائماً شهري)
            total_rent = (rec.rental_fee or 0.0) * total_months
            
            # رسوم الخدمة
            if rec.service_monthly:
                total_service = (rec.service_fee or 0.0) * total_months
            else:
                total_service = rec.service_fee or 0.0
            
            # رسوم الكهرباء
            if not rec.is_electricity_included:
                if rec.electricity_monthly:
                    total_electricity = (rec.electricity_fee or 0.0) * total_months
                else:
                    total_electricity = rec.electricity_fee or 0.0
            else:
                total_electricity = 0.0
            
            rec.total_contract_value = total_rent + total_service + total_electricity
    
    @api.depends('total_rental_fee', 'tax_ids', 'tax_included')
    def _compute_tax_amount(self):
        """Calculate tax amount based on selected taxes (tax_ids)
        Only calculates tax if taxes are selected in tax_ids field
        """
        for rec in self:
            # لا تحسب ضريبة إذا لم يتم اختيار ضريبة من حقل tax_ids
            if not rec.total_rental_fee or not rec.tax_ids:
                rec.tax_amount = 0.0
                continue
            
            # حساب نسبة الضريبة من الضرائب المختارة
            tax_rate = sum(rec.tax_ids.mapped('amount'))
            tax_rate_decimal = tax_rate / 100
            
            if rec.tax_included:
                # إذا كان المبلغ شامل الضريبة، نستخرج قيمة الضريبة من المبلغ
                rec.tax_amount = rec.total_rental_fee * tax_rate_decimal / (1 + tax_rate_decimal)
            else:
                # إذا لم يكن شامل الضريبة، نحسب الضريبة على المبلغ
                rec.tax_amount = rec.total_rental_fee * tax_rate_decimal

    @api.depends('total_rental_fee', 'tax_amount', 'tax_ids')
    def _compute_total_rental_fee_after_tax(self):
        """Calculate total rental fee after tax (per period)
        If tax_ids is set: Total After Tax = Total Before Tax + Tax Amount
        If no tax_ids: Total After Tax = Total Before Tax (no tax)
        """
        for rec in self:
            if not rec.tax_ids:
                # لا يوجد ضريبة مختارة، المبلغ النهائي = المبلغ قبل الضريبة
                rec.total_rental_fee_after_tax = rec.total_rental_fee or 0.0
            elif rec.tax_included:
                # إذا كان شامل الضريبة، المبلغ النهائي هو نفسه total_rental_fee
                rec.total_rental_fee_after_tax = rec.total_rental_fee or 0.0
            else:
                # إذا لم يكن شامل الضريبة، نضيف الضريبة للمبلغ
                rec.total_rental_fee_after_tax = (rec.total_rental_fee or 0.0) + (rec.tax_amount or 0.0)

    @api.depends('total_contract_value', 'previously_paid_amount')
    def _compute_adjusted_contract_value(self):
        """Calculate adjusted contract value after deducting previously paid amounts"""
        for rec in self:
            previously_paid = rec.previously_paid_amount or 0.0
            total_value = rec.total_contract_value or 0.0
            rec.adjusted_contract_value = max(0.0, total_value - previously_paid)

    # =============================================================
    # THE FIX IS HERE: Add a direct dependency for the currency.
    # This field gets the currency from the contract's company.
    # =============================================================
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True
    )
    unit_handover_ids = fields.One2many(
        'unit.handover.form',
        'contract_id',
        string='Unit Handover Forms'
    )
    state = fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed"),
                                  ("cancel", "Canceled"),("renew", "Renewed") ,("done", "Done")], string=_("state"), default='draft')
    reservation_id = fields.Many2one("unit.reservation", string=_("Reservation"))
    date_from = fields.Date(string=_("Start Date"))
    maintenance_request_ids = fields.One2many(
        'rental.maintenance.request',
        'contract_id',
        string='Maintenance Requests'
    )
    drawing_submittal_ids = fields.One2many(
        'drawing.submittal',
        'contract_id',
        string='Drawing Submittals'
    )

    unit_takeover_ids = fields.One2many('unit.takeover.form', 'contract_id', string="Unit Takeovers")

    def action_open_unit_handover_forms(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Unit Handover Forms',
            'res_model': 'unit.handover.form',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
            'target': 'current',
        }

    def action_open_unit_takeover_forms(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Unit Takeover Forms',
            'res_model': 'unit.takeover.form',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
            'target': 'current',
        }

    def action_open_drawing_submittals(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Drawing Submittals',
            'res_model': 'drawing.submittal',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {
                'default_contract_id': self.id,
            },
            'target': 'current',
        }

    date_to = fields.Date(string=_("End Date"))
    rental_fee = fields.Integer(string=_("Rental fee"))
    service_fee = fields.Float(string=_("Service Fee / رسوم الخدمة"))
    total_rental_fee = fields.Float(string=_("Total Rental Fees Before Tax / إجمالي الرسوم قبل الضريبة"), compute='_compute_total_rental_fee', store=True, help="Rental Fee + Service Fee + Electricity Fee (per period)")
    total_rental_fee_after_tax = fields.Float(string=_("Total Fees After Tax / إجمالي الرسوم بعد الضريبة"), compute='_compute_total_rental_fee_after_tax', store=True, help="Total rental fee including tax (per period)")
    total_contract_value = fields.Float(string=_("Total Contract Value / إجمالي قيمة العقد"), compute='_compute_total_contract_value', store=True, help="Total value for entire contract period including tax")
    insurance_fee = fields.Integer(string=_("Insurance fee"))
    rs_project = fields.Many2one("rs.project", string=_("Project"))
    rs_project_code = fields.Char(string=_("Project Code"))
    no_of_floors = fields.Integer(string=_("Floors"))
    property_owner_id = fields.Many2one("res.partner", string=_("Project Owner"), domain="[('is_owner','=',True)]")
    region = fields.Many2one("regions", string=_("Region"))
    rs_project_unit = fields.Many2one("sub.property", string=_("Project Unit"))
    unit_code = fields.Char(string=_("Unit Code"))
    floor = fields.Char(string=_("Floor"))
    address = fields.Char(string=_("Address"))
    type = fields.Many2one("rs.project.type", string=_("Property Type"))
    status = fields.Many2one("rs.project.status", string=_("Property Status"))
    rs_project_area = fields.Integer(string=_("Project Unit Area m²"))
    rental_line_ids = fields.One2many("rental.contract.line", "rental_contract_id", string=_("Rental Contract Lines"))
    furniture_line_ids = fields.One2many("rental.contract.furniture", "contract_id", string=_("FurnitureLine"))
    rental_attachment_ids = fields.One2many("rental.contract.attachment", "rental_contract_id",
                                            string=_("Rental Attachment"))
    periodicity = fields.Selection([('days', 'Days'), ('weeks', 'Weeks'),
                                    ('months', 'Months'), ('quarters', 'Quarters'), ('semi_annual', 'Semi-annual'), ('years', 'Years'), ],
                                   string='Recurrence', required=True,
                                   help="Invoice automatically repeat at specified interval", default='months',
                                   tracking=True)
    recurring_interval = fields.Integer(string="Invoicing Period", help="Repeat every (Days/Week/Month/Quarter/Year)",
                                        required=True, default=1, tracking=True)
    
    # حقول الضريبة
    tax_included = fields.Boolean(string='Tax Included / شامل الضريبة', default=False, 
                                  help="If checked, tax is included in the amount. If unchecked, tax will be added.")
    tax_rate = fields.Float(string='Tax Rate % / معدل الضريبة', default=15.0, 
                           help="Tax percentage rate")
    tax_amount = fields.Float(string='Tax Amount / قيمة الضريبة', compute='_compute_tax_amount', store=True,
                             help="Calculated tax amount based on total rental fee and tax rate")
    
    # حقول الفواتير المدفوعة مسبقاً (قبل إدخال النظام)
    previously_paid_amount = fields.Float(
        string='Previously Paid Amount / المبالغ المدفوعة مسبقاً',
        default=0.0,
        tracking=True,
        help="Amount already paid before system implementation. This will be deducted from total contract value for installment calculation."
    )
    
    adjusted_contract_value = fields.Float(
        string='Adjusted Contract Value / قيمة العقد المعدلة',
        compute='_compute_adjusted_contract_value',
        store=True,
        help="Total contract value minus previously paid amount. This is the base for installment calculation."
    )
    
    paid = fields.Float(compute='_check_amounts', string='Paid', )
    balance = fields.Float(compute='_check_amounts', string='Balance', )
    amount_total = fields.Float(compute='_check_amounts', string='Total', )
    boolean_make_renewed = fields.Boolean(compute='_boolean_make_renewed')
    boolean_make_done = fields.Boolean(compute='_boolean_make_done')
    property_owners_id = fields.Many2one("res.partner", string=_("Properties Owner"), domain="[('is_owner','=',True)]")
    renewed_contract_id = fields.Many2one('rental.contract', readonly=True, string="Next Contract")
    ann_inc = fields.Float(string="Anual Increase Percantage")
    duration_x = fields.Float(string="Duration")
    duration = fields.Integer()

    @api.depends('date_from', 'duration')
    def _get_end_date_(self):
        for r in self:
            if not (r.date_from and r.duration):
                r.date_to = r.date_from
                continue
            duration = timedelta(days=r.duration, seconds=-1)
            r.date_to = r.date_from + duration

    def _set_end_date(self):
        for r in self:
            if not (r.date_from and r.duration):
                continue

            r.duration = (r.date_to - r.start_borrow).days + 1

    @api.constrains('date_from', 'date_to')
    def _check_date_from_date_to(self):
        """This function,  used as an Odoo model constraint, checks that the contract's start date is before or equal to the end date, raising a validation error if the condition is not met."""
        if self.filtered(lambda d: d.date_to and d.date_from > d.date_to):
            raise ValidationError(_('Contract start date must be less than contract end date.'))

    @api.constrains('recurring_interval')
    def _check_recurring_interval(self):
        """This Odoo model constraint ensures that the 'recurring_interval' is a positive value, raising a validation error if it's less than or equal to zero."""
        for record in self:
            if record.recurring_interval <= 0:
                raise ValidationError(_("The recurring interval must be positive"))

    @api.constrains('previously_paid_amount', 'total_contract_value')
    def _check_previously_paid_amount(self):
        """Ensure previously paid amount doesn't exceed total contract value"""
        for record in self:
            if record.previously_paid_amount < 0:
                raise ValidationError(_("Previously paid amount cannot be negative."))
            if record.previously_paid_amount > 0 and record.total_contract_value > 0:
                if record.previously_paid_amount > record.total_contract_value:
                    raise ValidationError(
                        _("Previously paid amount (%.2f) cannot exceed total contract value (%.2f).") 
                        % (record.previously_paid_amount, record.total_contract_value)
                    )

    @api.depends('rental_line_ids', 'rental_line_ids.amount_residual')
    def _check_amounts(self):
        """This function calculates and updates the 'paid,' 'balance,' and 'amount_total' fields based on the 'rental_line_ids' and their 'amount' and 'amount_residual' values, while ensuring that these fields depend on changes in those related fields."""
        for rec in self:
            total_paid = 0
            total_unpaid = 0
            amount_total = 0
            for line in rec.rental_line_ids:
                amount_total += line.amount
                total_unpaid += line.amount_residual
                total_paid += (line.amount - line.amount_residual)

            rec.paid = total_paid
            rec.balance = total_unpaid
            rec.amount_total = amount_total

    @api.onchange('region')
    def onchange_region(self):
        """This Odoo 'onchange' method updates the available options for the 'rs_project' field based on the selected 'region,' retrieving and filtering 'rs_project' records related to the chosen region."""
        if self.region:
            rs_project_ids = self.env['rs.project'].search([('region', '=', self.region.id)])
            rs_projects = []
            for b in rs_project_ids: rs_projects.append(b.id)
            return {'domain': {'rs_project': [('id', 'in', rs_projects)]}}

    @api.onchange('rs_project')
    def onchange_rs_project(self):
        """This Odoo 'onchange' method updates various fields, including 'rs_project_code,' 'no_of_floors,' and 'region,' based on the selected 'rs_project,' and it also filters 'rs_project' options based on the 'state' and the chosen 'rs_project.'"""
        if self.rs_project:
            units = self.env['sub.property'].search(
                [('rs_project_id', '=', self.rs_project.id), ('state', '=', 'free')])
            unit_ids = []
            for u in units: unit_ids.append(u.id)
            rs_project = self.env['rs.project'].browse(self.rs_project.id)
            code = rs_project.code
            no_of_floors = rs_project.no_of_floors
            region = rs_project.region.id
            if rs_project:
                self.rs_project_code = code
                self.region = region
                self.no_of_floors = no_of_floors
                return {'domain': {'rs_project_unit': [('id', 'in', unit_ids)]}}

    @api.onchange('rs_project_unit')
    def onchange_unit(self):
        """This 'onchange' method populates various fields based on the selected 'rs_project_unit' and constructs a 'full_address' by concatenating address components, updating multiple related fields in the process."""
        full_address = ""
        if self.rs_project_unit.street:
            full_address += self.rs_project_unit.street
        if self.rs_project_unit.street2:
            if full_address:
                full_address += ", " + self.rs_project_unit.street2
            else:
                full_address += self.rs_project_unit.street2
        if self.rs_project_unit.city:
            if full_address:
                full_address += ", " + self.rs_project_unit.city
            else:
                full_address += self.rs_project_unit.city
        if self.rs_project_unit.zip:
            if full_address:
                full_address += ", " + self.rs_project_unit.zip
            else:
                full_address += self.rs_project_unit.zip

        self.unit_code = self.rs_project_unit.code
        self.floor = self.rs_project_unit.floor
        self.type = self.rs_project_unit.ptype.id
        self.address = full_address
        self.status = self.rs_project_unit.status.id
        self.rs_project_area = self.rs_project_unit.rs_project_area
        self.rs_project = self.rs_project_unit.rs_project_id.id
        self.region = self.rs_project_unit.region.id
        self.rental_fee = self.rs_project_unit.rental_fee
        self.service_fee = self.rs_project_unit.service_fee
        self.total_rental_fee = self.rs_project_unit.total_rental_fee
        self.insurance_fee = self.rs_project_unit.insurance_fee
        self.property_owners_id = self.rs_project_unit.partner_id

    def action_confirm(self):
        """This function confirms a contract and performs various checks, updates the state of related objects, and creates payment records for the insurance fee and invoices for rental lines."""
        _logger.info("="*80)
        _logger.info("START action_confirm for contract: %s", self.name)
        _logger.info("="*80)
        
        if not self.partner_id:
            raise UserError(_('You can not confirm a contract with no Tenant selected!'))

        if not self.rs_project_unit:
            raise UserError(_('You can not confirm a contract with no rs_project_unit selected!'))

        if not self.date_from:
            raise UserError(_('You can not confirm a contract with no start date!'))

        if not self.date_to:
            raise UserError(_('You can not confirm a contract with no end date!'))

        if self.total_rental_fee <= 0:
            raise UserError(_('You can not confirm a contract with no total rental fee!'))

        if not self.rental_line_ids:
            raise UserError(_('You can not confirm a contract with no rental line!'))

        else:
            _logger.info("Contract validation passed. Updating states...")
            self.rs_project_unit.write({'state': 'on_lease'})
            self.write({'state': 'confirmed'})
            self.reservation_id.state = 'contracted'
            
            if self.insurance_fee:
                _logger.info("Creating insurance payment: %s", self.insurance_fee)
                # البحث عن journal للدفعات (Bank أو Cash)
                journal_pool = self.env['account.journal']
                payment_journal = journal_pool.search([
                    ('type', 'in', ['bank', 'cash']),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                
                if not payment_journal:
                    raise UserError(_('Please configure a Bank or Cash journal for payments!'))
                
                payment = self.env['account.payment'].create({
                    'payment_type': 'inbound',
                    'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                    'partner_type': 'customer',
                    'partner_id': self.partner_id.id,
                    'amount': self.insurance_fee,
                    'memo': self.name,
                    'journal_id': payment_journal.id,
                })
                payment.action_post()
                _logger.info("Insurance payment created and posted: %s", payment.name)
            
            _logger.info("Creating invoices for %s rental lines...", len(self.rental_line_ids))
            for idx, line in enumerate(self.rental_line_ids, 1):
                _logger.info("-" * 60)
                _logger.info("Processing rental line %s/%s: %s", idx, len(self.rental_line_ids), line.name)
                _logger.info("  Line ID: %s", line.id)
                _logger.info("  Due Date: %s", line.date)
                _logger.info("  Rent Amount: %s", line.rent_amount)
                _logger.info("  Service Amount: %s", line.service_amount)
                _logger.info("  Electricity Amount: %s", line.electricity_amount)
                _logger.info("  Total Amount: %s", line.amount)
                
                line.make_invoice()
                
                if line.invoice_id:
                    _logger.info("  ✓ Invoice created: %s", line.invoice_id.name)
                    _logger.info("  Invoice lines count: %s", len(line.invoice_id.invoice_line_ids))
                    for inv_line in line.invoice_id.invoice_line_ids:
                        _logger.info("    - Line: %s | Amount: %s", inv_line.name, inv_line.price_unit)
                else:
                    _logger.warning("  ✗ No invoice created for line %s", line.name)
            
            _logger.info("="*80)
            _logger.info("END action_confirm - All invoices created successfully")
            _logger.info("="*80)
            
            # Trigger recompute of monthly_revenue for the project
            if self.rs_project:
                self.rs_project._compute_monthly_revenue()

    def action_mark_done(self):
        for record in self:
            if record.state == 'confirmed' and record.date_to <= fields.Date.today()and all(line.payment_state == "paid" for line in record.rental_line_ids):
                record.write({'state': 'done'})
            else:
                # Handle case when conditions are not met
                pass

    def action_cancel(self):
        """This function cancels a contract, updates the state of related rs_project units and invoices, and sets the contract's state to 'cancel.'"""
        for rec in self:
            rec.rs_project_unit.write({'state': 'free'})
            self.write({'state': 'cancel'})
        for line in self.rental_line_ids:
            line.invoice_id.button_draft()
            line.invoice_id.button_cancel()

    def action_send_portal_invite(self):
        """Send portal invitation to tenant with login credentials"""
        self.ensure_one()
        
        # التحقق من وجود الإيميل
        if not self.partner_id.email:
            raise UserError(_('Please set an email address for the tenant!'))
        
        tenant = self.partner_id
        tenant_email = tenant.email.strip().lower()
        
        # البحث عن مستخدم موجود بنفس الإيميل
        existing_user = self.env['res.users'].search([('login', '=', tenant_email)], limit=1)
        
        if existing_user:
            # إذا كان المستخدم موجود، تأكد من أنه في مجموعة portal
            portal_group = self.env.ref('base.group_portal')
            if portal_group not in existing_user.groups_id:
                existing_user.write({'groups_id': [(4, portal_group.id)]})
            user = existing_user
        else:
            # إنشاء مستخدم portal جديد
            portal_group = self.env.ref('base.group_portal')
            user_vals = {
                'name': tenant.name,
                'login': tenant_email,
                'email': tenant_email,
                'partner_id': tenant.id,
                'password': tenant_email,  # كلمة المرور = الإيميل
                'groups_id': [(4, portal_group.id)],
                'active': True,
            }
            user = self.env['res.users'].create(user_vals)
        
        # إعداد رابط Portal
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        portal_url = f"{base_url}/my"
        
        # إعداد نص الإيميل
        subject = _('Portal Access for %s') % self.name
        body = _("""
Dear %s,

You have been granted access to our tenant portal for rental contract: %s

Your login credentials are:
• Email: %s
• Password: %s

Portal URL: %s

You can use the portal to:
- View your rental contract details
- Check payment status
- Download invoices
- Contact support

If you have any questions, please don't hesitate to contact us.

Best regards,
Real Estate Management Team
        """) % (
            tenant.name,
            self.name,
            tenant_email,
            tenant_email,
            portal_url
        )
        
        # إرسال الإيميل
        try:
            mail_values = {
                'subject': subject,
                'body_html': body.replace('\n', '<br/>'),
                'email_from': self.env.company.email or 'no-reply@company.com',
                'email_to': tenant_email,
                'auto_delete': False,
            }
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
            
            # إضافة رسالة في Chatter
            self.message_post(
                body=_("Portal invitation sent to %s (%s)<br/>Login credentials:<br/>• Email: %s<br/>• Password: %s<br/>• Portal URL: <a href='%s'>%s</a>") % (
                    tenant.name,
                    tenant_email,
                    tenant_email,
                    tenant_email,
                    portal_url,
                    portal_url
                ),
                subject=_('Portal Invitation Sent'),
                message_type='notification'
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Portal invitation sent successfully to %s') % tenant_email,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(_('Failed to send email: %s') % str(e))

    def calc_ann_inc(self, date_from, date_to, rental_fee, ann_inc):
        years_no = relativedelta(date_to, date_from).years
        new_rent_fee = rental_fee
        for y in range(years_no):
            new_rent_fee += (new_rent_fee * ann_inc)
        return new_rent_fee

    def action_calculate(self):
        for rec in self:
            # حذف السطور القديمة
            rec.rental_line_ids.unlink()

            if not rec.date_from or not rec.date_to:
                continue

            # حساب عدد الشهور الكلية بين تاريخ البداية والنهاية
            total_months = (rec.date_to.year - rec.date_from.year) * 12 + (rec.date_to.month - rec.date_from.month) + 1
            
            # حساب عدد الدفعات بناءً على نوع الفترة والتواريخ
            if rec.periodicity == 'days':
                total_days = (rec.date_to - rec.date_from).days + 1
                num_payments = max(1, total_days // int(rec.recurring_interval or 1))
            elif rec.periodicity == 'weeks':
                total_days = (rec.date_to - rec.date_from).days + 1
                num_payments = max(1, total_days // (7 * int(rec.recurring_interval or 1)))
            elif rec.periodicity == 'months':
                num_payments = max(1, total_months // int(rec.recurring_interval or 1))
            elif rec.periodicity == 'quarters':
                # كل ربع سنة = 3 أشهر
                # عدد الأرباع = عدد الشهور ÷ 3
                num_payments = max(1, (total_months + 2) // 3)  # التقريب للأعلى
            elif rec.periodicity == 'semi_annual':
                # كل نصف سنة = 6 أشهر
                num_payments = max(1, (total_months + 5) // 6)  # التقريب للأعلى
            elif rec.periodicity == 'years':
                total_years = rec.date_to.year - rec.date_from.year + 1
                num_payments = max(1, total_years // int(rec.recurring_interval or 1))
            else:
                num_payments = 1
            
            # للصيانة والكهرباء، نستخدم عدد الشهور
            periods_duration = total_months

            # استخدام rental_fee (الإيجار الأساسي فقط) و service_fee المحددين مباشرة
            base_rent = rec.rental_fee or 0.0
            service_fee = rec.service_fee or 0.0
            maintenance = rec.maintenance_fee or 0.0
            electricity = rec.electricity_fee or 0.0

            # حساب إجمالي كل مكون
            total_base_rent = base_rent * periods_duration
            
            # حساب رسوم الخدمة
            if rec.service_monthly:
                total_service = service_fee * periods_duration
            else:
                total_service = service_fee

            # حساب رسوم الصيانة
            if rec.maintenance_monthly:
                total_maintenance = maintenance * periods_duration
            else:
                total_maintenance = maintenance

            # حساب الكهرباء
            if not rec.is_electricity_included:
                if rec.electricity_monthly:
                    total_electricity = electricity * periods_duration
                else:
                    total_electricity = electricity
            else:
                total_electricity = 0.0

            # إجمالي المبلغ قبل حساب الضريبة
            subtotal = total_base_rent + total_maintenance + total_electricity + total_service

            # حساب الضريبة
            tax_rate = rec.tax_rate / 100 if rec.tax_rate else 0.0
            
            if rec.tax_included:
                # إذا كان المبلغ شامل الضريبة
                # المبلغ المدخل = المبلغ النهائي الشامل للضريبة
                total_with_tax = subtotal
                # نستخرج قيمة الضريبة من المبلغ الشامل
                tax_amount = total_with_tax * tax_rate / (1 + tax_rate)
                # المبلغ الأساسي (بدون ضريبة) = المبلغ الشامل - الضريبة
                total_base_rent_after_tax = (total_base_rent * 1) / (1 + tax_rate) if tax_rate > 0 else total_base_rent
                total_maintenance_after_tax = (total_maintenance * 1) / (1 + tax_rate) if tax_rate > 0 else total_maintenance
                total_electricity_after_tax = (total_electricity * 1) / (1 + tax_rate) if tax_rate > 0 else total_electricity
                total_service_after_tax = (total_service * 1) / (1 + tax_rate) if tax_rate > 0 else total_service
                total_before_tax = total_with_tax - tax_amount
            else:
                # إذا لم يكن شامل الضريبة
                # المبلغ المدخل = المبلغ الأساسي (بدون ضريبة)
                total_before_tax = subtotal
                # نضيف الضريبة على المبلغ
                tax_amount = total_before_tax * tax_rate
                total_with_tax = total_before_tax + tax_amount
                # المبالغ الأساسية كما هي
                total_base_rent_after_tax = total_base_rent
                total_maintenance_after_tax = total_maintenance
                total_electricity_after_tax = total_electricity
                total_service_after_tax = total_service

            # خصم المبلغ المدفوع مسبقاً من إجمالي قيمة العقد
            previously_paid = rec.previously_paid_amount or 0.0
            if previously_paid > 0:
                # حساب نسبة الخصم من الإجمالي
                if total_with_tax > 0:
                    deduction_ratio = previously_paid / total_with_tax
                    # تطبيق نسبة الخصم على كل مكون
                    total_base_rent_after_tax = total_base_rent_after_tax * (1 - deduction_ratio)
                    total_maintenance_after_tax = total_maintenance_after_tax * (1 - deduction_ratio)
                    total_electricity_after_tax = total_electricity_after_tax * (1 - deduction_ratio)
                    total_service_after_tax = total_service_after_tax * (1 - deduction_ratio)
                    tax_amount = tax_amount * (1 - deduction_ratio)
                    total_with_tax = total_with_tax - previously_paid

            # توزيع المبالغ على الدفعات (استخدام المبالغ المحسوبة بعد معالجة الضريبة وخصم المدفوع مسبقاً)
            rent_per_payment = total_base_rent_after_tax / num_payments
            maintenance_per_payment = total_maintenance_after_tax / num_payments
            electricity_per_payment = total_electricity_after_tax / num_payments
            service_per_payment = total_service_after_tax / num_payments
            tax_per_payment = tax_amount / num_payments
            
            # المبلغ قبل الضريبة لكل دفعة
            amount_per_payment_before_tax = rent_per_payment + maintenance_per_payment + electricity_per_payment + service_per_payment
            # المبلغ النهائي (شامل الضريبة) لكل دفعة
            amount_per_payment_after_tax = amount_per_payment_before_tax + tax_per_payment

            # إنشاء السطور
            rental_lines = []
            for i in range(num_payments):
                # حساب تاريخ الدفعة حسب نوع الفترة
                if rec.periodicity == 'days':
                    payment_date = rec.date_from + relativedelta(days=int(rec.recurring_interval or 1) * i)
                elif rec.periodicity == 'weeks':
                    payment_date = rec.date_from + relativedelta(weeks=int(rec.recurring_interval or 1) * i)
                elif rec.periodicity == 'months':
                    payment_date = rec.date_from + relativedelta(months=int(rec.recurring_interval or 1) * i)
                elif rec.periodicity == 'quarters':
                    # كل ربع سنة = 3 أشهر
                    payment_date = rec.date_from + relativedelta(months=3 * i)
                elif rec.periodicity == 'semi_annual':
                    # كل نصف سنة = 6 أشهر
                    payment_date = rec.date_from + relativedelta(months=6 * i)
                elif rec.periodicity == 'years':
                    payment_date = rec.date_from + relativedelta(years=int(rec.recurring_interval or 1) * i)
                else:
                    payment_date = rec.date_from + relativedelta(months=int(rec.recurring_interval or 1) * i)

                rental_lines.append((0, 0, {
                    'serial': i + 1,
                    'date': payment_date,
                    'amount': amount_per_payment_after_tax,
                    'rent_amount': rent_per_payment,
                    'maintenance_amount': maintenance_per_payment,
                    'electricity_amount': electricity_per_payment,
                    'service_amount': service_per_payment,
                    'tax_amount': tax_per_payment,
                    'amount_before_tax': amount_per_payment_before_tax,
                    'name': f"Rental Fee (Part {i + 1})"
                }))

            # كتابة السطور
            rec.write({'rental_line_ids': rental_lines})

    @api.onchange("date_to" , "state" , "rental_line_ids.payment_state")
    def _boolean_make_done(self):
        for record in self:
            if (
                    isinstance(record.date_to, date)
                    and record.date_to <= date.today()
                    and all(line.payment_state == "paid" for line in record.rental_line_ids)
                    and record.state == 'confirmed'
            ):
                record.boolean_make_done = True
            else:
                record.boolean_make_done = False

    @api.onchange("date_to", "rental_line_ids.payment_state")
    def _boolean_make_renewed(self):
        """This 'onchange' method sets the 'boolean_make_renewed' field to 'True' if the 'date_to' matches the current date
        and all lines' 'payment_state' are 'paid'; otherwise, it sets it to 'False'."""
        for record in self:
            last_line = record.rental_line_ids[-1] if record.rental_line_ids else None
            if (
                    last_line
                    and last_line.date
                    and isinstance(last_line.date, date)
                    and last_line.date <= date.today()
                    and all(line.payment_state == "paid" for line in record.rental_line_ids)
                    and record.state == 'confirmed'
            ):
                record.boolean_make_renewed = True
            else:
                record.boolean_make_renewed = False

    def make_renewed(self):
        """This function creates a renewed rental contract, setting its state to 'renew' and populating its fields with values from the current contract, while also changing the state of the related rs_project unit to 'reserved' if applicable."""
        self.state = 'renew'
        # Calculate the new 'date_from' based on periodicity
        if self.periodicity == 'days':
            delta = timedelta(days=1)
        elif self.periodicity == 'weeks':
            delta = timedelta(weeks=1)
        elif self.periodicity == 'months':
            delta = relativedelta(months=1)
        elif self.periodicity == 'quarters':
            delta = relativedelta(months=3)
        elif self.periodicity == 'years':
            delta = relativedelta(years=1)
        else:
            # Handle an unknown periodicity (you may raise an exception, set a default, or choose another strategy)
            delta = timedelta(days=1)

        # Calculate the new 'date_from'
        if self.rental_line_ids:
            last_date = max(line.date for line in self.rental_line_ids)
            new_date_from = last_date + delta
        else:
            # Handle the case where there are no rental_line_ids
            new_date_from = date.today()
        vals = {
            'name': self.name,
            'state': 'draft',
            'date_from': new_date_from,
            'date': date.today(),
            'user_id': self.user_id.id,
            'rental_fee': self.rental_fee,
            'insurance_fee': self.insurance_fee,
            'reservation_id': self.reservation_id.id,
            'partner_id': self.partner_id.id,
            'rs_project': self.rs_project.id,
            'rs_project_code': self.rs_project_code,
            'no_of_floors': self.no_of_floors,
            'property_owner_id': self.property_owner_id.id,
            'region': self.region.id,
            'rs_project_unit': self.rs_project_unit.id,
            'unit_code': self.unit_code,
            'floor': self.floor,
            'address': self.address,
            'type': self.type.id,
            'status': self.status.id,
            'rs_project_area': self.rs_project_area,
        }
        new_rental_contract_post = self.env['rental.contract'].create(vals)
        self.renewed_contract_id = new_rental_contract_post
        if self.rs_project_unit:
            self.rs_project_unit.state = 'reserved'

        return new_rental_contract_post


    @api.model
    def create(self, vals):
        """This method creates a new rental contract by generating a unique 'name' using an Odoo sequence and then calling the superclass 'create' method to create the contract with the provided values."""
        vals['name'] = self.env['ir.sequence'].next_by_code('rental.contract')
        contract = super(RentalContract, self).create(vals)
        return contract

    def unlink(self):
        """This method allows the deletion of rental contracts in the 'draft' state, raising a user error if the contract is in any other state."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('You can not delete a contract not in draft state'))
            super(RentalContract, rec).unlink()

    def make_update_furniture(self):
        """This function updates the 'furniture_line_ids' by clearing existing lines and populating it with furniture details from the selected 'rs_project_unit,' if available."""
        self.furniture_line_ids = [(5, 0, 0)]
        if self.rs_project_unit:
            furniture_lines = []
            for furniture in self.rs_project_unit.furniture_ids:
                furniture_lines.append((0, 0, {
                    'product_id': furniture.product_id.id,
                    'description': furniture.description,
                    'list_price': furniture.list_price,
                    'product_qty': furniture.product_qty,
                }))
            self.furniture_line_ids = furniture_lines

    @api.onchange('rs_project_unit')
    def _onchange_rs_project_unit(self):
        """This 'onchange' method updates the 'furniture_line_ids' by clearing existing lines and populating it with furniture details from the selected 'rs_project_unit,' if available."""
        self.furniture_line_ids = [(5, 0, 0)]
        if self.rs_project_unit:
            furniture_lines = []
            for furniture in self.rs_project_unit.furniture_ids:
                furniture_lines.append((0, 0, {
                    'product_id': furniture.product_id.id,
                    'description': furniture.description,
                    'list_price': furniture.list_price,
                    'product_qty': furniture.product_qty,
                }))
            self.furniture_line_ids = furniture_lines


class RentalContractLine(models.Model):
    _name = 'rental.contract.line'
    _description = "rental.contract.line"
    _rec_name = "name"

    date = fields.Date(string=_("Due Date"), required=True)
    name = fields.Char(string=_("Reference"), required=True)
    serial = fields.Char('#')
    rent_amount = fields.Float(string="Rent")
    maintenance_amount = fields.Float(string="Maintenance")
    electricity_amount = fields.Float(string="Electricity")
    service_amount = fields.Float(string="Service")
    tax_amount = fields.Float(string="Tax Amount / مبلغ الضريبة")
    amount_before_tax = fields.Float(string="Amount Before Tax / المبلغ قبل الضريبة")
    amount = fields.Float(string=_("Amount"), required=True, help="Total amount including tax")
    amount_residual = fields.Monetary(string='Amount Due / المبلغ المستحق', currency_field='currency_id', related='invoice_id.amount_residual', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency')
    invoice_id = fields.Many2one('account.move', string='Invoice', )
    payment_state = fields.Selection(related='invoice_id.payment_state', readonly=True, store=True)
    inv_number = fields.Char(string='Invoice Number',related='invoice_id.name')
    invoice_state = fields.Selection(related='invoice_id.state', readonly=True, store=True)
    rental_contract_id = fields.Many2one("rental.contract", string=_("Rental Contract"))
    customer_id = fields.Many2one('res.partner', string="Tenant", related='rental_contract_id.partner_id', store=True)
    reference = fields.Char(string="Reference", related='rental_contract_id.name', store=True)
    make_stat_paid = fields.Boolean(compute="_compute_make_stat_paid", store=True)





    @api.depends('payment_state', 'date')
    def _compute_make_stat_paid(self):
        for rec in self:
            if rec.payment_state != "paid" and rec.date <= date.today():
                rec.make_stat_paid = True
            else:
                rec.make_stat_paid = False

    def make_invoice(self):
        """This function creates an invoice in the 'out_invoice' type, associating it with a rental contract, and populates it with relevant details, including the journal, partner, and invoice lines, then posts the invoice and links it to the rental line."""
        for rec in self:
            account_move = self.env['account.move']
            journal_pool = self.env['account.journal']
            journal = journal_pool.search([
                ('type', '=', 'sale'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            
            if not journal:
                raise UserError(_('Please configure a Sales journal for invoicing!'))
            
            # التحقق من وجود الحساب المحاسبي
            account_in_id = self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.rental_settlement_account')
            
            if account_in_id:
                # إذا كان محدد في الإعدادات، تحقق من صحته
                try:
                    account_in_id = int(account_in_id)
                    account = self.env['account.account'].browse(account_in_id)
                    if not account.exists():
                        raise UserError(_('The configured rental settlement account (ID: %s) does not exist. Please check the settings!') % account_in_id)
                except (ValueError, TypeError):
                    raise UserError(_('Invalid account ID configured for rental settlement. Please check the settings!'))
            else:
                # البحث عن حساب إيرادات افتراضي
                # في Odoo 18، account.account لا يحتوي على company_id مباشرة
                # نبحث عن أي حساب إيرادات متاح
                account = self.env['account.account'].search([
                    ('account_type', '=', 'income')
                ], limit=1)
                
                if account:
                    account_in_id = account.id
                else:
                    raise UserError(_('No income account found. Please configure a rental settlement account in the settings or create an income account!'))
            
            # استخدام الضرائب المحددة في العقد مباشرة من حقل tax_ids
            tax_ids = []
            if rec.rental_contract_id.tax_ids:
                tax_ids = [(6, 0, rec.rental_contract_id.tax_ids.ids)]
                _logger.info(f"Using taxes from contract: {rec.rental_contract_id.tax_ids.mapped('name')}")
            else:
                _logger.info("No taxes defined on the contract")
            
            # إنشاء سطور الفاتورة
            invoice_lines = []
            
            _logger.info(f"Creating invoice for rental line {rec.id}: rent_amount={rec.rent_amount}, electricity_amount={rec.electricity_amount}, service_amount={rec.service_amount}")
            
            # السطر الأول: رسوم الإيجار + رسوم الخدمة
            rental_and_service = (rec.rent_amount or 0.0) + (rec.service_amount or 0.0)
            _logger.info(f"Rental + Service = {rental_and_service}")
            
            if rental_and_service > 0:
                invoice_lines.append((0, None, {
                    'name': _('Rental Fee / رسوم الإيجار') + ' - ' + rec.rental_contract_id.name,
                    'quantity': 1,
                    'account_id': account_in_id,
                    'price_unit': rental_and_service,
                    'tax_ids': tax_ids,
                }))
                _logger.info(f"Added Rental Fee line (Rental + Service): {rental_and_service}")
            
            # السطر الثاني: رسوم الكهرباء
            if rec.electricity_amount and rec.electricity_amount > 0:
                invoice_lines.append((0, None, {
                    'name': _('Electricity Fee / رسوم الكهرباء') + ' - ' + rec.rental_contract_id.name,
                    'quantity': 1,
                    'account_id': account_in_id,
                    'price_unit': rec.electricity_amount,
                    'tax_ids': tax_ids,
                }))
                _logger.info(f"Added Electricity Fee line: {rec.electricity_amount}")
            
            # إذا لم يكن هناك سطور، استخدم المبلغ الإجمالي
            if not invoice_lines:
                _logger.warning(f"No invoice lines created, using total amount: {rec.amount}")
                invoice_lines.append((0, None, {
                    'name': (rec.rental_contract_id.name + ' - ' + rec.name),
                    'quantity': 1,
                    'account_id': account_in_id,
                    'price_unit': rec.amount,
                    'tax_ids': tax_ids,
                }))
            
            _logger.info(f"Total invoice lines to create: {len(invoice_lines)}")
            
            invoice = account_move.create({
                'journal_id': journal.id,
                'partner_id': rec.rental_contract_id.partner_id.id,
                'move_type': 'out_invoice',
                'rental_line_id': rec.id,
                'invoice_date_due': rec.date,
                'ref': (rec.rental_contract_id.name + ' - ' + rec.name),
                'invoice_line_ids': invoice_lines
            })
            # لا تنشر الفاتورة مباشرة، اتركها في حالة Draft
            # invoice.action_post()  # تم تعطيل النشر التلقائي
            self.invoice_id = invoice.id

    def action_post_invoice(self):
        """Post the invoice and open it for viewing"""
        self.ensure_one()
        
        if not self.invoice_id:
            raise UserError(_('No invoice found for this rental line!'))
        
        # إذا كانت الفاتورة في حالة draft، قم بنشرها
        if self.invoice_id.state == 'draft':
            self.invoice_id.action_post()
        elif self.invoice_id.state == 'cancel':
            raise UserError(_('Cannot post a cancelled invoice!'))
        elif self.invoice_id.state == 'posted':
            # الفاتورة منشورة بالفعل، فقط افتحها
            pass
        
        # إرجاع action لعرض الفاتورة
        return {
            'name': _('Invoice'),
            'view_type': 'form',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def action_post_and_pay_invoice(self):
        """This function posts the invoice and returns the invoice action for viewing"""
        self.ensure_one()
        
        if not self.invoice_id:
            raise UserError(_('No invoice found for this installment!'))
        
        # إذا كانت الفاتورة في حالة draft، قم بنشرها
        if self.invoice_id.state == 'draft':
            self.invoice_id.action_post()
        elif self.invoice_id.state == 'cancel':
            raise UserError(_('Cannot post a cancelled invoice!'))
        
        # إرجاع action لعرض الفاتورة
        return {
            'name': _('Posted Invoice'),
            'view_type': 'form',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }



class RentalContractFurniture(models.Model):
    _name = 'rental.contract.furniture'
    _description = "rental contract furniture"

    product_id = fields.Many2one("product.product", string=_("Product"), domain="[('furniture', '=', True)]")
    description = fields.Char(string=_('Description'))
    list_price = fields.Float(related="product_id.list_price")
    contract_id = fields.Many2one("rental.contract")
    product_qty = fields.Integer(string=_("Quantity"), default=1)


class RentalAttachmentLine(models.Model):
    _name = 'rental.contract.attachment'
    _description = "rental.attachment.line"

    name = fields.Char(string=_("Name"))
    file = fields.Binary(string=_("File"))
    rental_contract_id = fields.Many2one("rental.contract", string=_("Rental Contract"))
