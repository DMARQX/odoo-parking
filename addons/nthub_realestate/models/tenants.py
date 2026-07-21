# -*- coding: utf-8 -*-
from odoo import models, fields, api,_


class Tenants(models.Model):
    _inherit = 'res.partner'

    is_tenant = fields.Boolean(string=_("Tenant"))
    is_owner = fields.Boolean(string=_("Owner"))

    commercial_registration_number = fields.Char(string="CR Number")
    commercial_registration_expiry = fields.Date(string="Cr Registration Expiry")

    commercial_status = fields.Selection([
        ('active', 'active'),
        ('expired', 'expired'),
    ], string="Cr Status ", compute="_compute_commercial_status", store=True)

    @api.depends('commercial_registration_expiry')
    def _compute_commercial_status(self):
        for rec in self:
            if rec.commercial_registration_expiry:
                if rec.commercial_registration_expiry >= fields.Date.today():
                    rec.commercial_status = 'active'
                else:
                    rec.commercial_status = 'expired'
            else:
                rec.commercial_status = False

