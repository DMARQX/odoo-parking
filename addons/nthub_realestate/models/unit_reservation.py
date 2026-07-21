# -*- coding: utf-8 -*-

from odoo import api, fields, models
import datetime
from odoo.tools.translate import _
import calendar
from odoo.exceptions import UserError, AccessError
from datetime import time, datetime, date,timedelta


class Reservation(models.Model):
    _name = 'unit.reservation'
    _description = 'Unit Reservation'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Reference', size=64, readonly=True)
    quotation_reference = fields.Char('Quotation Reference', readonly=True, 
                                       help='Quotation number that created this reservation')
    contract_count_own = fields.Integer(compute='_contract_count_own', string='Sales')
    contract_count_rent = fields.Integer(compute='_contract_count_rent', string='Rentals')
    deposit_count = fields.Integer(compute='_deposit_count', string='First Payments')
    date = fields.Datetime('Reservation Date', default=fields.Datetime.now())
    rs_project = fields.Many2one('rs.project', string='Project',)
    rs_project_code = fields.Char('Project Code', size=16)
    rs_project_unit = fields.Many2one('sub.property','Project Unit', required=True, domain="[('state', '=', 'free')]")
    unit_code = fields.Char('Unit Code', size=16)
    floor = fields.Char('Floor', size=16)
    address = fields.Char('Address')
    pricing = fields.Integer('ٍPricing',)
    contract_id_own = fields.Many2one('ownership.contract','Ownership Contract',)
    contract_id_rent = fields.Many2one('rental.contract','Rental Contract',)
    type = fields.Many2one('rs.project.type','Property Type',)
    status = fields.Many2one('rs.project.status','Property Status',)
    region = fields.Many2one('regions','Region',)
    user_id = fields.Many2one('res.users','Responsible', default=lambda self: self.env.user,)
    partner_id = fields.Many2one('res.partner','Customer')
    rs_project_area = fields.Integer('Project Unit Area m²',)
    state = fields.Selection([('draft','Draft'),
                             ('confirmed','Confirmed'),
                             ('contracted','Contracted'),
                             ('canceled','Canceled')
                             ], 'State', default='draft')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    deposit = fields.Float('First Payment', digits=(16, 2),)

    def _contract_count_own(self):
        """This function calculates and updates the 'contract_count_own' field with the count of ownership contracts associated with the reservation."""
        ownership = self.env['ownership.contract']
        own_ids = ownership.search([('reservation_id', '=', self.id)])
        self.contract_count_own = len(own_ids)

    def _contract_count_rent(self):
        """This function calculates and updates the 'contract_count_rent' field with the count of rental contracts associated with the reservation."""
        rental = self.env['rental.contract']
        rent_ids = rental.search([('reservation_id', '=', self.id)])
        self.contract_count_rent = len(rent_ids)

    def _deposit_count(self):
        """This function calculates and updates the 'deposit_count' field with the count of payments associated with the reservation."""
        payment = self.env['account.payment']
        payment_ids = payment.search([('reservation_id', '=', self.id)])
        self.deposit_count = len(payment_ids)

    def unlink(self):
        """This method allows the deletion of reservations in the 'draft' state, raising a user error if the reservation is in any other state."""
        for rec in self:
            if self.state != 'draft':
                raise UserError(_('You can not delete a reservation not in draft state'))
            super(Reservation, rec).unlink()

    #This SQL constraint enforces uniqueness on the 'name' field, ensuring that no duplicate values are allowed for reservation numbers in the database.
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Reservation Number record must be unique !')]

    @api.onchange('rs_project_unit')
    def onchange_unit(self):
        """This method updates various fields based on the selected 'rs_project_unit,' including 'unit_code,' 'floor,' 'type,' 'address,' 'status,' 'rs_project_area,' 'rs_project,' 'rs_project_code,' and 'region,' by concatenating address components and copying values from the rs_project unit."""
        full_address = ""
        if self.rs_project_unit.street:
            full_address += self.rs_project_unit.street
        if self.rs_project_unit.street2:
            if full_address:
                full_address += ", " + self.rs_project_unit.street2
            else:
                full_address += self.rs_project_unit.street2
        if self.rs_project_unit.city:
            if full_address:
                full_address += ", " + self.rs_project_unit.city
            else:
                full_address += self.rs_project_unit.city
        if self.rs_project_unit.zip:
            if full_address:
                full_address += ", " + self.rs_project_unit.zip
            else:
                full_address += self.rs_project_unit.zip
        self.unit_code = self.rs_project_unit.code
        self.floor = self.rs_project_unit.floor
        self.type = self.rs_project_unit.ptype
        self.address = full_address
        self.status = self.rs_project_unit.status
        self.rs_project_area = self.rs_project_unit.rs_project_area
        self.rs_project = self.rs_project_unit.rs_project_id.id
        self.rs_project_code = self.rs_project_unit.rs_project_id.code
        self.region = self.rs_project_unit.region.id

    @api.onchange('rs_project')
    def onchange_rs_project(self):
        """This method updates the 'rs_project_code' and 'region' fields based on the selected 'rs_project,' and filters the available 'rs_project' options based on the chosen rs_project."""
        if self.rs_project:
            units = self.env['sub.property'].search(
                [('rs_project_id', '=', self.rs_project.id), ('state', '=', 'free')])
            unit_ids = []
            for u in units: unit_ids.append(u.id)
            rs_project = self.env['rs.project'].browse(self.rs_project.id)
            code = rs_project.code
            region = rs_project.region.id
            if rs_project:
                self.rs_project_code = code
                self.region = region
                return {'domain': {'rs_project_unit': [('id', 'in', unit_ids)]}}

    def action_cancel(self):
        """This function cancels an action, changing the state of the current record to 'canceled' and updating the state of the associated 'rs_project_unit' to 'free'."""
        self.write({'state': 'canceled'})
        unit = self.rs_project_unit
        unit.write({'state':  'free'})

    def unit_status(self):
        """This function returns the current status of the associated 'rs_project_unit.'"""
        return self.rs_project_unit.state

    def action_confirm(self):
        """This function confirms an action, changing the state of the current record to 'confirmed' and updating the state of the associated 'rs_project_unit' to 'reserved'."""
        self.write({'state': 'confirmed'})
        unit = self.rs_project_unit
        unit.write({'state': 'reserved'})

    def action_receive_deposit(self):
        """This function initiates the process for receiving a first payment associated with the reservation, opening a payment form view with pre-filled information for creating a payment record."""
        if not self.deposit:
            raise UserError(_('Please set the first payment amount!'))
        return {
            'name': _('Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.payment',
            'view_id': self.env.ref('account.view_account_payment_form').id,
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'default_amount': self.deposit,
                'default_partner_id': self.partner_id.id,
                'default_reservation_id': self.id,
            },

        }

    def view_deposits(self):
        """This function retrieves and displays a list of payments associated with the selected reservation in the Odoo user interface, allowing users to view and manage the payments."""
        payment = self.env['account.payment']
        payment_ids = payment.search([('reservation_id', '=', self.id)])

        return {
            'name': _('Payments'),
            'domain': [('id', 'in', payment_ids.ids)],
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'account.payment',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'target': 'current',
        }

    def action_contract_ownership(self):
        """This function opens a form view for creating an ownership contract, pre-filling it with relevant information from the current reservation in the Odoo user interface."""
        return {
            'name': _('Ownership Contract'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'ownership.contract',
            'view_id': self.env.ref('nthub_realestate.ownership_contract_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_rs_project': self.rs_project.id,
                'default_region': self.region.id,
                'default_rs_project_code': self.rs_project_code,
                'default_partner_id': self.partner_id.id,
                'default_rs_project_unit': self.rs_project_unit.id,
                'default_unit_code': self.unit_code,
                'default_floor': self.floor,
                'default_type': self.type.id,
                'default_status': self.status.id,
                'default_rs_project_area': self.rs_project_area,
                'default_reservation_id': self.id,
            },
            'target': 'current'
        }

    def action_contract_rental(self):
        """This function opens a form view for creating a rental contract, pre-filling it with relevant information from the current reservation in the Odoo user interface."""
        return {
            'name': _('Rental Contract'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'rental.contract',
            'view_id': self.env.ref('nthub_realestate.rental_contract_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_rs_project': self.rs_project.id,
                'default_region': self.region.id,
                'default_rs_project_code': self.rs_project_code,
                'default_partner_id': self.partner_id.id,
                'default_rs_project_unit': self.rs_project_unit.id,
                'default_unit_code': self.unit_code,
                'default_floor': self.floor,
                'default_type': self.type.id,
                'default_status': self.status.id,
                'default_rs_project_area': self.rs_project_area,
                'default_reservation_id': self.id,
            },
            'target': 'current'
        }

    def view_contract_own(self):
        """This function retrieves and displays a list of ownership contracts associated with the selected reservation in the Odoo user interface, allowing users to view and manage the ownership contracts."""
        own_obj = self.env['ownership.contract']
        own_ids = own_obj.search([('reservation_id', '=', self.id)])
        return {
            'name': _('Ownership Contract'),
            'domain': [('id', 'in', own_ids.ids)],
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'ownership.contract',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'target': 'current',
        }

    def view_contract_rent(self):
        """This function retrieves and displays a list of rental contracts associated with the selected reservation in the Odoo user interface, allowing users to view and manage the rental contracts."""
        rent_obj = self.env['rental.contract']
        rent_ids = rent_obj.search([('reservation_id', '=', self.id)])
        return {
            'name': _('Rental Contract'),
            'domain': [('id', 'in', rent_ids.ids)],
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'rental.contract',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'target': 'current',
        }

    @api.model
    def create(self, vals):
        """This method creates a new reservation record and generates a unique reservation number using an incremental sequence in Odoo."""
        vals['name'] = self.env['ir.sequence'].next_by_code('unit.reservation')
        reservation = super(Reservation, self).create(vals)
        return reservation

    def auto_cancel_reservation(self):
        """This function automatically cancels confirmed reservations and updates the state of associated rs_project units to 'free' if the reservation date is older than a specified number of days, with error handling for potential exceptions."""
        try:
            reservation_pool = self.env['unit.reservation']
            reservation_days = int(self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.reservation_days'))
            reservation_ids = reservation_pool.search(
                [('state', '=', 'confirmed'), ('date', '<=', str(datetime.now() - timedelta(days=reservation_days)))])
            for reservation in reservation_ids:
                reservation.write({'state': 'canceled'})
                unit = reservation.rs_project_unit
                unit.write({'state': 'free'})
        except:
            return "internal error"
