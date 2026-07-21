# -*- coding: utf-8 -*-
from odoo import models, fields, api,_


class Furniture(models.Model):
    _inherit = 'product.template'

    furniture = fields.Boolean(string=_("Furniture"))

