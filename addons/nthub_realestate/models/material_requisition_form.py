from odoo import models, fields,api

class MaterialRequisitionForm(models.Model):
    _name = 'material.requisition.form'
    _description = 'Material Requisition Form'
    _inherit = ['mail.thread']

    name = fields.Char(string="Reference", default="New", readonly=True)
    date = fields.Date(string="Date", default=fields.Date.today)
    project_id = fields.Many2one('rs.project', string="Project", required=True)
    department = fields.Char(string="Department")

    materials = fields.Boolean(string="Materials")
    spare_parts = fields.Boolean(string="Spare Parts")
    consumable = fields.Boolean(string="Consumable")
    stationary = fields.Boolean(string="Stationary")
    tools = fields.Boolean(string="Tools")
    equipments = fields.Boolean(string="Equipment's")
    furniture = fields.Boolean(string="Furniture")
    services = fields.Boolean(string="Services")

    line_ids = fields.One2many('material.requisition.line', 'form_id', string="Items")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
    ], default='draft', string="Status", tracking=True)

    def action_confirm(self):
        self.state = 'confirm'

    def action_set_to_draft(self):
        self.state = 'draft'

    def _get_default_sequence(self):
        return self.env['ir.sequence'].next_by_code('material.requisition.form') or 'New'

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self._get_default_sequence()
        return super().create(vals)




class MaterialRequisitionLine(models.Model):
    _name = 'material.requisition.line'
    _description = 'Material Requisition Line'

    form_id = fields.Many2one('material.requisition.form', string="Form")
    description = fields.Text(string="Description")
    unit = fields.Char(string="Unit")
    quantity = fields.Float(string="Qty")
    estimated_cost_per_unit = fields.Float(string="Estimated Cost / Unit")
    estimated_cost_total = fields.Float(string="Total", compute="_compute_total", store=True)
    remarks = fields.Text(string="Remarks")

    @api.depends('quantity', 'estimated_cost_per_unit')
    def _compute_total(self):
        for rec in self:
            rec.estimated_cost_total = (rec.quantity or 0.0) * (rec.estimated_cost_per_unit or 0.0)
