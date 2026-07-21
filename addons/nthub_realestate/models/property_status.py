# -*- coding: utf-8 -*-
from odoo import models, fields, api,_


class PropertyStatus(models.Model):
    _name = 'rs.project.status'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "rs.project.status"
    _rec_name = 'name'

    name = fields.Char(string=_("State"))
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
