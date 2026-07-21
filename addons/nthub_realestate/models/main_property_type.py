# -*- coding: utf-8 -*-
from odoo import models, fields, api,_


class MainPropertyType(models.Model):
    _name = 'rs.project.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "rs.project.type"
    _rec_name = "name"

    name = fields.Char(string=_("Type"))
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)



