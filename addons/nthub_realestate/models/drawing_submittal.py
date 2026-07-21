from odoo import api, fields, models,_


class DrawingSubmittal(models.Model):
    _name = 'drawing.submittal'
    _description = 'Tenant Shop Drawing Submittal'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Document No.", required=True, default=lambda self: _('New'))
    contract_id = fields.Many2one('rental.contract', string="Rental Contract", required=True)
    tenant_id = fields.Many2one(related='contract_id.partner_id', string="Tenant", readonly=True)
    submission_date = fields.Date(string="Submission Date", default=fields.Date.today)
    drawing_description = fields.Text(string="Drawings")
    copies = fields.Integer(string="No. of Copies")

    # Comments Sections
    architectural_comments = fields.Text(string="Architectural Comments")
    architectural_status = fields.Selection([
        ('app', 'APP'), ('aan', 'AAN'), ('rej', 'REJ')
    ], string="Architectural Status")

    electrical_comments = fields.Text(string="Electrical Comments")
    electrical_status = fields.Selection([
        ('app', 'APP'), ('aan', 'AAN'), ('rej', 'REJ')
    ], string="Electrical Status")

    hvac_comments = fields.Text(string="HVAC Comments")
    hvac_status = fields.Selection([
        ('app', 'APP'), ('aan', 'AAN'), ('rej', 'REJ')
    ], string="HVAC Status")

    drainage_comments = fields.Text(string="Drainage & Water Supply Comments")
    drainage_status = fields.Selection([
        ('app', 'APP'), ('aan', 'AAN'), ('rej', 'REJ')
    ], string="Drainage Status")

    firefighting_comments = fields.Text(string="Fire Fighting Comments")
    firefighting_status = fields.Selection([
        ('app', 'APP'), ('aan', 'AAN'), ('rej', 'REJ')
    ], string="Firefighting Status")

    low_current_comments = fields.Text(string="Low Current Comments")
    low_current_status = fields.Selection([
        ('app', 'APP'), ('aan', 'AAN'), ('rej', 'REJ')
    ], string="Low Current Status")

    fire_alarm_comments = fields.Text(string="Fire Alarm Comments")
    fire_alarm_status = fields.Selection([
        ('app', 'APP'), ('aan', 'AAN'), ('rej', 'REJ')
    ], string="Fire Alarm Status")

    guideline_note = fields.Text(string="Note", default="Kindly take in consideration our Construction Guideline")
    signed_by = fields.Char(string="Name")
    signed_date = fields.Date(string="Date", default=fields.Date.today)
    signature = fields.Binary(string="Signature")

    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='draft', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('drawing.submittal') or _('New')
        return super(DrawingSubmittal, self).create(vals)
