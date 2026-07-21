# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class StockPicking(models.Model):
    """Inherit stock.picking to add job order reference"""
    _inherit = 'stock.picking'

    x_job_order_id = fields.Many2one(
        'maintenance.job.order',
        string='Job Order / أمر العمل',
        tracking=True,
        help='Maintenance job order related to this transfer'
    )

    x_maintenance_request_id = fields.Many2one(
        'rental.maintenance.request',
        string='Maintenance Request / طلب الصيانة',
        related='x_job_order_id.maintenance_request_id',
        readonly=True,
        store=True,
        help='Related maintenance request'
    )
