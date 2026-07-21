# -*- coding: utf-8 -*-
from odoo import fields, models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    x_maintenance_job_id = fields.Many2one(
        'maintenance.job.order',
        string='Maintenance Job Order',
        help='Link to maintenance job order that created this PO'
    )
    
    def action_view_maintenance_job_order(self):
        """Smart button action to view the related maintenance job order"""
        self.ensure_one()
        if not self.x_maintenance_job_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('No job order linked to this purchase order.'),
                    'type': 'warning',
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance Job Order'),
            'res_model': 'maintenance.job.order',
            'res_id': self.x_maintenance_job_id.id,
            'view_mode': 'form',
            'target': 'current',
        }