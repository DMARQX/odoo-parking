# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class InstallmentTemplate(models.Model):
    _name = "installment.template"
    _description = "Installment Template"
    _inherit = ['mail.thread']

    name = fields.Char('Name', required=True)
    duration_month = fields.Integer('Month')
    duration_year = fields.Integer('Year')
    repetition_rate = fields.Integer('Repetition Rate (month)', default=1)
    adv_payment_rate = fields.Integer('Advance Payment %')
    deduct = fields.Boolean('Deducted from amount?')
    note = fields.Html('Note')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    delay_penalty = fields.Float(string='Delay Penalty Percentage')
    delay_process = fields.Float(string='Delay Penalty Process')

    @api.constrains("duration_month", 'duration_year')
    def check_duration_month_and_duration_year(self):
        """Check that both 'duration_month' and 'duration_year' are not zero."""
        if self.duration_month == 0 and self.duration_year == 0:
            raise UserError("Months equal to Zero and Year equal to Zero You should change this Value Months or Year")
        else:
            print("Right")
