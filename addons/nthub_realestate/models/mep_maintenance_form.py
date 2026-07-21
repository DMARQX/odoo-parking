
from odoo import models, fields, api

class MEPPreventiveMaintenanceForm(models.Model):
    _name = 'mep.maintenance.form'
    _description = 'MEP Preventive Maintenance Form'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    date = fields.Date(string="Date", default=fields.Date.today)
    project_id = fields.Many2one('rs.project', string="Project", required=True)
    location = fields.Char(string="Location")

    work_line_ids = fields.One2many(
        'mep.maintenance.work.line',
        'form_id',
        string="Work Lines"
    )

    additional_work = fields.Text(string="Additional Work Required")
    referral_task = fields.Text(string="Referral Task to Another Contractor")

    contractor_name = fields.Char(string="Contractor Name")
    contractor_signature = fields.Binary(string="Contractor Signature")
    contractor_date = fields.Date(string="Contractor Date")

    tenant_name = fields.Char(string="Tenant Name")
    tenant_signature = fields.Binary(string="Tenant Signature")
    tenant_date = fields.Date(string="Tenant Date")

    tower_name = fields.Char(string="Tower Management Name")
    tower_signature = fields.Binary(string="Tower Signature")
    tower_date = fields.Date(string="Tower Date")
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company.id,
        readonly=True
    )


class MEPMaintenanceWorkLine(models.Model):
    _name = 'mep.maintenance.work.line'
    _description = 'MEP Maintenance Work Line'

    form_id = fields.Many2one('mep.maintenance.form', string="Form")
    work_description = fields.Char(string="Work Description")
    system_details = fields.Char(string="System Details")
    status = fields.Selection([
        ('done', 'Done'),
        ('pending', 'Pending'),
        ('not_applicable', 'N/A')
    ], string="Status")
    remarks = fields.Text(string="Remarks")
