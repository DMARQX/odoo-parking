# models/low_current_maintenance_form.py

from odoo import models, fields,api

class LowCurrentMaintenanceForm(models.Model):
    _name = 'low.current.maintenance.form'
    _description = 'Low Current Preventive Maintenance Form'
    _inherit = ['mail.thread']

    name = fields.Char(string="Reference", default="New", readonly=True)
    date = fields.Date(string="Date", default=fields.Date.today)
    project_id = fields.Many2one('rs.project', string="Project", required=True)
    location = fields.Char(string="Location")

    work_line_ids = fields.One2many(
        'low.current.maintenance.line',
        'form_id',
        string="Work Items"
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
        'res.company', string='Company',
        default=lambda self: self.env.company.id,
        readonly=True
    )


    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('low.current.maintenance.form') or 'New'
        return super().create(vals)


class LowCurrentWorkLine(models.Model):
    _name = 'low.current.maintenance.line'
    _description = 'Low Current Maintenance Line'

    form_id = fields.Many2one('low.current.maintenance.form', string="Form")
    work_description = fields.Char(string="Work Description")
    system_details = fields.Char(string="System Details")
    status = fields.Selection([
        ('done', 'Done'),
        ('pending', 'Pending'),
        ('n/a', 'N/A'),
    ], string="Status")
    remarks = fields.Text(string="Remarks")