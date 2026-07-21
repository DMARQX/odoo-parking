# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)
class OwnerMessage(models.Model):
    _name = 'owner.message'
    _description = 'Owner Message Thread'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'subject'

    subject = fields.Char(string="Subject", required=True)
    owner_id = fields.Many2one(
        'res.partner',
        string="Owner",
        required=True,
        domain="[('is_owner', '=', True)]"
    )
    # This allows us to link to any related document, like a property
    related_document_id = fields.Reference(
        selection=[('rs.project', 'Project')],
        string="Related Document"
    )
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], string='Status', default='open', tracking=True)





class OwnerRequest(models.Model):
    _name = 'owner.request'
    # ... (the rest of your _inherit, _description, _rec_name lines) ...
    _description = 'Request from Property Owner'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'subject'

    # --- All your existing fields go here ---
    subject = fields.Char(string="Subject", required=True, tracking=True)
    owner_id = fields.Many2one(
        'res.partner',
        string="Owner",
        required=True,
        domain="[('is_owner', '=', True)]",
        default=lambda self: self.env.user.partner_id,
        tracking=True
    )
    project_id = fields.Many2one(
        'rs.project',
        string="Related Project",
        domain="[('partner_id', '=', owner_id)]",
        tracking=True
    )
    request_type = fields.Selection([
        ('financial', 'Financial Report'),
        ('maintenance', 'Maintenance Query'),
        ('info', 'Information Request'),
        ('other', 'Other'),
    ], string="Request Type", required=True, default='info', tracking=True)
    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new', tracking=True)
    description = fields.Text(string="Details")
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'owner_request_ir_attachments_rel',
        'owner_request_id',
        'attachment_id',
        string="Attachments"
    )

    # --- Button action methods ---
    def action_start_progress(self):
        return self.write({'state': 'in_progress'})

    def action_mark_as_done(self):
        return self.write({'state': 'done'})

    def action_cancel(self):
        return self.write({'state': 'cancelled'})

    def action_reset_to_new(self):
        return self.write({'state': 'new'})

    # --- NEW: Overridden write method to send emails ---
    def write(self, vals):
        """
        Override write to send an email notification when the state changes.
        """
        # First, perform the standard write operation
        res = super(OwnerRequest, self).write(vals)

        # Check if the 'state' field was part of the update
        if 'state' in vals:
            # Map states to their corresponding email templates
            # IMPORTANT: Replace 'nthub_realestate' with your module's technical name
            template_map = {
                'in_progress': 'nthub_realestate.email_template_owner_request_in_progress',
                'done': 'nthub_realestate.email_template_owner_request_done',
                'cancelled': 'nthub_realestate.email_template_owner_request_cancelled',
            }

            # Get the XML ID of the template for the new state
            template_xml_id = template_map.get(vals['state'])

            if template_xml_id:
                # Loop through each record that was updated
                for request in self:
                    try:
                        # Find the template and send the email
                        template = self.env.ref(template_xml_id)
                        template.send_mail(request.id, force_send=True)
                    except Exception as e:
                        _logger.error("Failed to send owner request email for state %s: %s", vals['state'], e)

        return res