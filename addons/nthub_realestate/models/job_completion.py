from odoo import models, fields, api
from odoo.exceptions import UserError


class JobOrderCompletionChecklist(models.Model):
    """Checklist Template for Job Completion Quality Assurance"""
    _name = 'job.order.completion.checklist'
    _description = 'Job Completion Quality Checklist'
    _rec_name = 'name'

    name = fields.Char(
        string='Checklist Name',
        required=True
    )

    maintenance_type = fields.Selection(
        [('electrical', 'Electrical'),
         ('mechanical', 'Mechanical'),
         ('low_current', 'Low Current'),
         ('civil', 'Civil'),
         ('general', 'General'),
         ('other', 'Other')],
        string='Maintenance Type',
        required=True
    )

    checklist_items = fields.One2many(
        'job.order.completion.item',
        'checklist_id',
        string='Checklist Items'
    )

    is_active = fields.Boolean(
        string='Active',
        default=True
    )

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company
    )

    _sql_constraints = [
        ('unique_maintenance_type', 'UNIQUE(maintenance_type, company_id)',
         'Only one checklist per maintenance type per company'),
    ]


class JobOrderCompletionItem(models.Model):
    """Individual Checklist Item"""
    _name = 'job.order.completion.item'
    _description = 'Completion Checklist Item'
    _order = 'sequence ASC'

    checklist_id = fields.Many2one(
        'job.order.completion.checklist',
        required=True,
        ondelete='cascade'
    )

    description = fields.Char(
        string='Item Description',
        required=True
    )

    is_required = fields.Boolean(
        string='Required',
        default=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )


class JobOrderCompletionResult(models.Model):
    """Completion Assessment Results"""
    _name = 'job.order.completion.result'
    _description = 'Job Completion Assessment'
    _inherit = ['mail.thread']
    _rec_name = 'job_order_id'

    job_order_id = fields.Many2one(
        'job.order.form',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    checklist_id = fields.Many2one(
        'job.order.completion.checklist',
        required=True,
        ondelete='restrict'
    )

    completion_date = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True
    )

    item_results = fields.One2many(
        'job.order.checklist.result',
        'completion_result_id',
        string='Item Results'
    )

    overall_status = fields.Selection(
        [('passed', 'Passed'),
         ('failed', 'Failed'),
         ('pending_rework', 'Pending Rework')],
        compute='_compute_overall_status',
        store=True
    )

    completion_photos = fields.Many2many(
        'ir.attachment',
        'job_completion_photos_rel',
        string='Completion Photos'
    )

    contractor_notes = fields.Text(
        string='Contractor Notes'
    )

    @api.depends('item_results.status')
    def _compute_overall_status(self):
        for record in self:
            failed_items = record.item_results.filtered(lambda x: x.status == 'failed')
            if failed_items:
                record.overall_status = 'failed'
            else:
                record.overall_status = 'passed'


class JobOrderChecklistResult(models.Model):
    """Individual Checklist Item Result"""
    _name = 'job.order.checklist.result'
    _description = 'Checklist Item Result'

    completion_result_id = fields.Many2one(
        'job.order.completion.result',
        required=True,
        ondelete='cascade'
    )

    item_id = fields.Many2one(
        'job.order.completion.item',
        required=True
    )

    description = fields.Char(
        related='item_id.description',
        store=True,
        readonly=True
    )

    status = fields.Selection(
        [('passed', 'Passed'),
         ('failed', 'Failed'),
         ('n/a', 'Not Applicable')],
        required=True,
        default='n/a'
    )

    notes = fields.Text(
        string='Notes'
    )

    photo_id = fields.Many2one(
        'ir.attachment',
        string='Supporting Photo'
    )


class JobOrderDefect(models.Model):
    """Job Order Defect Report & Rework Tracking"""
    _name = 'job.order.defect'
    _description = 'Job Order Defect Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'create_date DESC'

    name = fields.Char(
        string='Defect ID',
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('job.order.defect')
    )

    job_order_id = fields.Many2one(
        'job.order.form',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    description = fields.Text(
        string='Defect Description',
        required=True,
        tracking=True
    )

    severity = fields.Selection(
        [('minor', 'Minor'),
         ('major', 'Major'),
         ('critical', 'Critical')],
        default='minor',
        tracking=True
    )

    reported_date = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True
    )

    reported_by = fields.Many2one(
        'res.partner',
        string='Reported By',
        default=lambda self: self.env.user.partner_id,
        readonly=True
    )

    status = fields.Selection(
        [('reported', 'Reported'),
         ('acknowledged', 'Acknowledged'),
         ('in_repair', 'In Repair'),
         ('resolved', 'Resolved'),
         ('closed', 'Closed')],
        default='reported',
        tracking=True
    )

    rework_job_order_id = fields.Many2one(
        'job.order.form',
        string='Rework Job Order',
        readonly=True,
        help='Auto-created rework job order'
    )

    photos = fields.Many2many(
        'ir.attachment',
        'job_defect_photos_rel',
        string='Defect Photos'
    )

    def action_acknowledge(self):
        """Acknowledge the defect"""
        self.status = 'acknowledged'
        self.message_post(
            body='Defect acknowledged',
            message_type='notification'
        )

    def action_create_rework(self):
        """Auto-create rework job order"""
        if self.rework_job_order_id:
            raise UserError('Rework job order already created')

        # Copy original job order for rework
        rework_job = self.job_order_id.copy({
            'name': f"{self.job_order_id.name} - REWORK",
            'work_description': f"Rework for defect: {self.description}",
            'state': 'draft',
        })

        self.rework_job_order_id = rework_job.id
        self.status = 'in_repair'

        self.message_post(
            body=f'Rework job order created: {rework_job.name}',
            message_type='notification'
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'job.order.form',
            'res_id': rework_job.id,
            'view_mode': 'form',
        }

    def action_resolve(self):
        """Mark defect as resolved"""
        self.status = 'resolved'
        self.message_post(
            body='Defect marked as resolved',
            message_type='notification'
        )

    def action_close(self):
        """Close defect report"""
        self.status = 'closed'
        self.message_post(
            body='Defect report closed',
            message_type='notification'
        )
