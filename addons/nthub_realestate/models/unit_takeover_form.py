from odoo import models, fields

class UnitTakeoverForm(models.Model):
    _name = 'unit.takeover.form'
    _description = 'Unit Takeover Form'
    _inherit = ['mail.thread']

    contract_id = fields.Many2one('rental.contract', string='Rental Contract', required=True)
    date = fields.Date(string='Date', default=fields.Date.today)
    unit_number = fields.Char(string='Unit(s) #', related='contract_id.unit_code')
    total_area = fields.Integer(string='Unit(s) Total Area', related='contract_id.rs_project_area')
    tenant_name = fields.Char(string='Tenant’s', related='contract_id.partner_id.name')
    contact_person = fields.Char(string='Contact Person')
    office_number = fields.Char(string='Office #')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company.id,
        readonly=True
    )

    takeover_item_ids = fields.One2many(
        'unit.takeover.item',
        'form_id',
        string='Items'
    )

    consultant_name = fields.Char(string="Consultant Name")
    consultant_signature = fields.Binary(string="Consultant Signature")
    consultant_date = fields.Date(string="Consultant Date")

    tenant_rep_name = fields.Char(string="Tenant Rep. Name")
    tenant_signature = fields.Binary(string="Tenant Signature")
    tenant_date = fields.Date(string="Tenant Date")


class UnitTakeoverItem(models.Model):
    _name = 'unit.takeover.item'
    _description = 'Unit Takeover Item'

    form_id = fields.Many2one('unit.takeover.form', string='Form')
    item_name = fields.Char(string='Item Name', required=True)
    description = fields.Text(string='Description')
    checked = fields.Boolean(string='Available')
