# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SubPropertyRepeatWizard(models.TransientModel):
    _name = 'subproperty.repeat.wizard'
    _description = 'تكرار الوحدة'

    rs_project_id = fields.Many2one('your.main.model', string="Project", required=True)
    current_floor = fields.Integer(string="Current Floor")
    current_unit = fields.Integer(string="Current Unit")
    last_subproperty_id = fields.Many2one('sub.property', string="Last Unit", readonly=True)

    def action_repeat_unit(self):
        project = self.rs_project_id
        floor = self.current_floor
        unit = self.current_unit + 1

        if unit > project.props_per_floor:
            unit = 1
            floor += 1

        if floor > project.no_of_floors:
            raise ValidationError("تم إنشاء جميع الوحدات.")

        name = f'{project.code}-{floor}-{unit}'

        sub = self.env['sub.property'].create({
            'name': name,
            'code': name,
            'rs_project_id': project.id,
            'ptype': project.property_type.id,
            'status': project.property_status.id,
            'region': project.region.id,
            'street': project.street,
            'street2': project.street2,
            'country_id': project.country_id.id,
            'zip': project.zip,
            'state_id': project.state_id.id,
            'floor': str(floor),
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'subproperty.repeat.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_rs_project_id': project.id,
                'default_current_floor': floor,
                'default_current_unit': unit,
                'default_last_subproperty_id': sub.id,
            }
        }
