# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
from dateutil.relativedelta import relativedelta
import calendar
from datetime import datetime, date, timedelta as td


class OwnershipContract(models.Model):
    _name = 'ownership.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Ownership Contract"

    name = fields.Char(string=_("Reference"), readonly=True)
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user, )
    partner_id = fields.Many2one("res.partner", string=_("Customer"), domain="[('is_owner','=',True)]")
    date = fields.Date()
    date_payment = fields.Date(string=_("First Payment Date"))
    reservation_id = fields.Many2one('unit.reservation', string=_("Reservation"))
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    rs_project = fields.Many2one('rs.project', string=_("Project"))
    rs_project_code = fields.Char(string=_("Project Code"))
    no_of_floors = fields.Integer(string=_('Floors'))
    region = fields.Many2one('regions', string=_("Region"))

    rs_project_unit = fields.Many2one('sub.property', string=_("Project Unit"))
    unit_code = fields.Char(string=_("Unit Code"))
    floor = fields.Char(string=_("Floor"))
    address = fields.Char(string=_('Address'))
    pricing = fields.Integer('Price')
    type = fields.Many2one('rs.project.type', string=_('Property Type'))
    status = fields.Many2one('rs.project.status', string=_('Property Status'))
    rs_project_area = fields.Float('Project Unit Area m^2')
    template_id = fields.Many2one('installment.template', string=_('Payment Template'), required=True)

    maintenance = fields.Float(string=_('Maintenance'))
    maintenance_installment = fields.Boolean(string='Installment')
    maintenance_template_id = fields.Many2one('installment.template', 'Installment Payment Template', )
    club = fields.Float(string=_('Club'))
    garage = fields.Float(string=_('Garage'))
    elevator = fields.Float(string=_('Elevator'))
    other = fields.Float(string=_('Other Expenses'))

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('canceled', 'Canceled')], default='draft')
    ownership_maintenance_line_ids = fields.One2many('ownership.contract.maintenance.line', 'oc_id')
    oc_line_ids = fields.One2many('ownership.contract.line', 'oc_id')
    oc_attachment_ids = fields.One2many('ownership.attachment.line', 'ownership_attachment_id')
    furniture_line_ids = fields.One2many('owner.contract.furniture', 'contract_id')
    date_maintenance = fields.Date()
    date_club = fields.Date()
    date_garage = fields.Date()
    date_elevator = fields.Date()
    date_other = fields.Date()

    paid = fields.Float(compute='_check_amounts', string='Paid', )
    balance = fields.Float(compute='_check_amounts', string='Balance', )
    amount_total = fields.Float(compute='_check_amounts', string='Total', )
    furniture_price = fields.Float(string=_('Furniture Price'), compute='_calc_sum_furniture_price', store=True)
    paid_maintenance = fields.Float(compute='_check_maintenance_amounts', string='Paid', )
    balance_maintenance = fields.Float(compute='_check_maintenance_amounts', string='Balance', )
    amount_total_maintenance = fields.Float(compute='_check_maintenance_amounts', string='Total', )

    @api.depends("furniture_line_ids", "furniture_line_ids.list_price")
    def _calc_sum_furniture_price(self):
        """
        This method calculates the total price of furniture
        by summing the list prices of all associated furniture items."""
        for rec in self:
            rec.furniture_price = sum(rec.furniture_line_ids.mapped('list_price'))

    def action_confirm(self):
        """
           This method is used to confirm a contract.
           It performs various checks to ensure that all necessary
           information is provided before confirming the contract."""
        if not self.partner_id:
            raise UserError(_('You can not confirm a contract with no customer selected!'))

        if not self.rs_project_unit:
            raise UserError(_('You can not confirm a contract with no rs_project_unit selected!'))

        if not self.date_payment:
            raise UserError(_('You can not confirm a contract with no payment date!'))

        if not self.template_id:
            raise UserError(_('You can not confirm a contract with no Payment template!'))

        if not self.oc_line_ids:
            raise UserError(_('You can not confirm a contract with no installment line!'))

        else:
            unit = self.rs_project_unit
            unit.write({'state': 'sold'})
            self.write({'state': 'confirmed'})
            self.reservation_id.state = 'contracted'
            for line in self.oc_line_ids:
                line.make_invoice()
            for line in self.ownership_maintenance_line_ids:
                line.make_invoice()

            self.transfer_furniture_products()

    def action_cancel(self):
        """
        This method is used to cancel a contract. It performs the following actions:
        This indicates that the unit is no longer under contract.
        """
        unit = self.rs_project_unit
        unit.write({'state': 'free'})
        self.write({'state': 'canceled'})
        for line in self.oc_line_ids:
            line.invoice_id.button_draft()
            line.invoice_id.button_cancel()

    @api.model
    def create(self, vals):
        """
           This method is called to create a new OwnershipContract record.
           It assigns a unique name using an IR sequence and t
           hen calls the parent's create method to perform the actual creation. """
        vals['name'] = self.env['ir.sequence'].next_by_code('ownership.contract')
        contract = super(OwnershipContract, self).create(vals)
        return contract

    def unlink(self):
        """
            This method is used to delete OwnershipContract records. However,
            it enforces a constraint that prevents the deletion of contracts that are not in 'draft' state."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('You can not delete a contract not in draft state'))
        super(OwnershipContract, self).unlink()

    @api.depends('oc_line_ids.amount', 'oc_line_ids.amount_residual')
    def _check_amounts(self):
        """
            This method is used to calculate and update various financial amounts related to an OwnershipContract record.
            It computes the total paid amount, total unpaid amount, and the total contract amount. """
        total_paid = 0
        total_unpaid = 0
        amount_total = 0
        for rec in self:
            for line in rec.oc_line_ids:
                amount_total += line.amount
                total_unpaid += line.amount_residual
                total_paid += (line.amount - line.amount_residual)

        self.paid = total_paid
        self.balance = total_unpaid
        self.amount_total = amount_total

    @api.depends('ownership_maintenance_line_ids.amount', 'ownership_maintenance_line_ids.amount_residual')
    def _check_maintenance_amounts(self):
        """
            This method is used to calculate and update various financial amounts related to an OwnershipContract Maintenance record.
            It computes the total paid amount, total unpaid amount, and the total contract amount. """
        total_paid = 0
        total_unpaid = 0
        amount_total = 0
        for rec in self:
            for line in rec.ownership_maintenance_line_ids:
                amount_total += line.amount
                total_unpaid += line.amount_residual
                total_paid += (line.amount - line.amount_residual)

        self.paid_maintenance = total_paid
        self.balance_maintenance = total_unpaid
        self.amount_total_maintenance = amount_total

    def transfer_furniture_products(self):
        lines_stock = []
        location_id = int(self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.location_id'))
        location_dest_id = int(self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.location_dest_id'))
        if not location_id:
            raise UserError(_('Please set source location from setting!'))
        if not location_dest_id:
            raise UserError(_('Please set destination location from setting!'))

        for rec in self:
            if rec.furniture_line_ids:
                for line in rec.furniture_line_ids:
                    if not line.product_id or not line.product_qty:
                        raise UserError(_("You cannot validate a transfer if no Products or quantities are reserved."))
                    if not line.transfer and line.check:
                        lines_stock.append((0, 0, {
                            'name': line.product_id.name,
                            'product_id': line.product_id.id,
                            'product_uom': line.product_id.uom_id.id,
                            'location_id': location_id,
                            'location_dest_id': location_dest_id,
                            'product_uom_qty': line.product_qty,
                            # 'quantity_done' is removed here
                        }))

                picking_order = self.env['stock.picking'].create({
                    'picking_type_id': self.env.ref('stock.picking_type_internal').id,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'immediate_transfer': True,
                    'move_ids_without_package': lines_stock
                })

                # Set quantity_done after creation
                for move in picking_order.move_ids_without_package:
                    move.quantity_done = move.product_uom_qty

                picking_order.button_validate()

                for line in rec.furniture_ids:
                    if line.check:
                        line.transfer = True
                        line.check = False
            else:
                raise UserError(_("You cannot validate a transfer if no Products are reserved."))

    @api.onchange('rs_project')
    def onchange_rs_project(self):
        """
           This method is an Odoo `@api.onchange` function that triggers when the 'project' field is changed.
            It populates fields and filters options based on the selected project. """
        if self.rs_project:
            units = self.env['sub.property'].search(
                [('rs_project_id', '=', self.rs_project.id), ('state', '=', 'free')])
            unit_ids = []
            for u in units: unit_ids.append(u.id)
            rs_project = self.env['rs.project'].browse(self.rs_project.id)
            code = rs_project.code
            no_of_floors = rs_project.no_of_floors
            region = rs_project.region.id
            if rs_project:
                self.rs_project_code = code
                self.region = region
                self.no_of_floors = no_of_floors
                return {'domain': {'rs_project_unit': [('id', 'in', unit_ids)]}}

    @api.onchange('rs_project_unit')
    def onchange_unit(self):
        """
          This method is triggered when the 'rs_project_unit' field is changed. It updates various fields on the current object
          based on the selected 'rs_project_unit'. """
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
        self.pricing = self.rs_project_unit.pricing
        self.type = self.rs_project_unit.ptype
        self.address = full_address
        self.status = self.rs_project_unit.status
        self.rs_project_area = self.rs_project_unit.rs_project_area
        self.rs_project = self.rs_project_unit.rs_project_id.id
        self.region = self.rs_project_unit.region.id

    @api.onchange('reservation_id')
    def onchange_reservation(self):
        """
            Update fields on the current object based on the selected reservation.
            This function is triggered when the 'reservation_id' field is changed """
        self.rs_project = self.reservation_id.rs_project.id
        self.region = self.reservation_id.region.id
        self.rs_project_code = self.reservation_id.rs_project_code
        self.partner_id = self.reservation_id.partner_id.id
        self.rs_project_unit = self.reservation_id.rs_project_unit.id
        self.unit_code = self.reservation_id.unit_code
        self.address = self.reservation_id.address
        self.floor = self.reservation_id.floor
        self.rs_project_unit = self.reservation_id.rs_project_unit.id
        self.pricing = self.reservation_id.rs_project_unit.pricing
        self.type = self.reservation_id.type
        self.status = self.reservation_id.status
        self.rs_project_area = self.reservation_id.rs_project_area

    @api.onchange('maintenance_installment')
    def onchange_maintenance(self):
        if self.maintenance_installment == False:
            self.maintenance_template_id = ''

    def compute_action(self):
        # Call a function to prepare lines
        self._prepare_lines()
        self._prepare_maintenance_lines()

    def add_months(self, sourcedate, months):
        """
           Add a specified number of months to a given date."""
        month = sourcedate.month - 1 + months
        year = int(sourcedate.year + month / 12)
        month = month % 12 + 1
        day = min(sourcedate.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    def _prepare_lines(self):
        """
        :This function prepares a list of loan lines (oc_line_ids) based on the values provided in various fields of the instance """
        # self.oc_line_ids = None
        for line in self.oc_line_ids:
            self.write({'oc_line_ids': [(2, line.id, False)]})
        
        loan_lines = []
        if self.template_id:
            ind = 1
            pricing = self.pricing
            mon = self.template_id.duration_month
            yr = self.template_id.duration_year
            repetition = self.template_id.repetition_rate
            advance_percent = self.template_id.adv_payment_rate
            deduct = self.template_id.deduct
            first_date = self.date_payment
            if not first_date:
                raise UserError(_('Please select first payment date!'))
            adv_payment = pricing * float(advance_percent) / 100
            if mon > 12:
                x = mon / 12
                mon = (x * 12) + mon % 12
            mons = mon + (yr * 12)
            if adv_payment:
                loan_lines.append(
                    (0, 0, {'serial': ind, 'amount': adv_payment, 'date': first_date, 'name': _('Advance Payment')}))
                ind += 1
                if deduct:
                    pricing -= adv_payment
            loan_amount = (pricing / float(mons)) * repetition
            m = 0
            while m < mons:
                loan_lines.append(
                    (0, 0, {'serial': ind, 'amount': loan_amount, 'date': first_date, 'name': _('Loan Installment')}))
                ind += 1
                first_date = self.add_months(first_date, repetition)
                m += repetition
            if self.club:
                loan_lines.append(
                    (0, 0, {'serial': ind, 'amount': self.club, 'date': self.date_club, 'name': _('Club Payment')}))
                ind += 1
            if self.maintenance and self.maintenance_installment == False:
                loan_lines.append((0, 0, {'serial': ind, 'amount': self.maintenance, 'date': self.date_maintenance,
                                          'name': _('Maintenance Payment')}))
                ind += 1
            if self.garage:
                loan_lines.append((0, 0, {'serial': ind, 'amount': self.garage, 'date': self.date_garage,
                                          'name': _('Garage Payment')}))
                ind += 1
            if self.elevator:
                loan_lines.append((0, 0, {'serial': ind, 'amount': self.elevator, 'date': self.date_elevator,
                                          'name': _('Elevator Payment')}))
                ind += 1
            if self.other:
                loan_lines.append(
                    (0, 0, {'serial': ind, 'amount': self.other, 'date': self.date_other, 'name': _('Other Payment')}))
                ind += 1

        self.oc_line_ids = loan_lines

    def _prepare_maintenance_lines(self):
        self.ownership_maintenance_line_ids = None
        maintenance_lines = []
        if self.maintenance_installment and self.maintenance_template_id:
            ind = 1
            pricing = self.maintenance
            mon = self.maintenance_template_id.duration_month
            yr = self.maintenance_template_id.duration_year
            repetition = self.maintenance_template_id.repetition_rate
            advance_percent = self.maintenance_template_id.adv_payment_rate
            deduct = self.maintenance_template_id.deduct
            first_date = self.date_maintenance
            if not first_date:
                raise UserError(_('Please select first payment date!'))
            adv_payment = pricing * float(advance_percent) / 100
            if mon > 12:
                x = mon / 12
                mon = (x * 12) + mon % 12
            mons = mon + (yr * 12)
            if adv_payment:
                maintenance_lines.append(
                    (0, 0, {'serial': ind, 'amount': adv_payment, 'date': first_date, 'name': _('Advance Payment')}))
                ind += 1
                if deduct:
                    pricing -= adv_payment
            loan_amount = (pricing / float(mons)) * repetition
            m = 0
            while m < mons:
                maintenance_lines.append(
                    (0, 0, {'serial': ind, 'amount': loan_amount, 'date': first_date, 'name': _('Maintenance Installment')}))
                ind += 1
                first_date = self.add_months(first_date, repetition)
                m += repetition

        self.ownership_maintenance_line_ids = maintenance_lines

    @api.onchange('rs_project_unit')
    def _onchange_rs_project_unit(self):
        """
           Update furniture lines based on the selected rs_project unit.
           This function is triggered when the 'rs_project_unit' field is changed. """
        self.furniture_line_ids = [(5, 0, 0)]
        if self.rs_project_unit:
            furniture_lines = []
            for furniture in self.rs_project_unit.furniture_ids:
                furniture_lines.append((0, 0, {
                    'product_id': furniture.product_id.id,
                    'description': furniture.description,
                    'list_price': furniture.list_price,
                    'product_qty': furniture.product_qty,
                }))
            self.furniture_line_ids = furniture_lines


class OwnershipContractLine(models.Model):
    _name = 'ownership.contract.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Ownership Contract Line"

    name = fields.Char(string=_("Reference"), required=True)
    serial = fields.Char("#")
    date = fields.Date()
    invoice_id = fields.Many2one('account.move', string='Invoice', )
    payment_state = fields.Selection(related='invoice_id.payment_state', readonly=True, store=True)
    invoice_state = fields.Selection(related='invoice_id.state', readonly=True, store=True)
    amount = fields.Float(string=_("Payment"))
    amount_residual = fields.Monetary(related='invoice_id.amount_residual', readonly=True, )
    currency_id = fields.Many2one(related='invoice_id.currency_id', readonly=True)
    oc_id = fields.Many2one('ownership.contract')
    reference = fields.Char(string="Reference", related='oc_id.name', store=True)
    customer_id = fields.Many2one(related='oc_id.partner_id', store=True)
    delay_amount = fields.Float(string=_('Delay Amount'))
    d_invoice_id = fields.Many2one('account.move')
    delay_payment_state = fields.Selection(related='d_invoice_id.payment_state', readonly=True, store=True)
    delay_state = fields.Selection([(' ', ' '),
                                    ('draft', 'Draft'),
                                    ('invoiced', 'Invoiced'),
                                    ('dismissed', 'Dismissed')], default=' ')

    def make_invoice(self):
        """
            Create and post an invoice for a given record.
            This function generates an invoice for the current record and posts it in the
            accounting system. """
        for rec in self:
            account_move = self.env['account.move']
            journal_pool = self.env['account.journal']
            journal = journal_pool.search([('type', '=', 'sale')], limit=1)
            if rec.name == 'Loan Installment':
                account_in = int(
                    self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.ownership_settlement_account'))
            elif rec.name == 'Advance Payment':
                account_in = int(
                    self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.ownership_settlement_account'))
            elif rec.name == 'Maintenance Payment':
                account_in = int(
                    self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.ownership_maintenance_account'))
            elif rec.name == 'Club Payment':
                account_in = int(
                    self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.ownership_extras_account'))
            elif rec.name == 'Garage Payment':
                account_in = int(
                    self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.ownership_extras_account'))
            elif rec.name == 'Elevator Payment':
                account_in = int(
                    self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.ownership_extras_account'))
            elif rec.name == 'Other Payment':
                account_in = int(
                    self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.ownership_extras_account'))
            if not account_in:
                raise UserError(_('Please set income account for ownership from setting!'))
            invoice = account_move.create({
                'journal_id': journal.id,
                'partner_id': rec.oc_id.partner_id.id,
                'move_type': 'out_invoice',
                'ownership_line_id': rec.id,
                'invoice_date_due': rec.date,
                'ref': (rec.oc_id.name + ' - ' + rec.name),
                'invoice_line_ids': [(0, None, {
                    'name': (rec.oc_id.name + ' - ' + rec.name),
                    'quantity': 1,
                    'account_id': account_in,
                    'price_unit': rec.amount, })]
            })
            invoice.action_post()
            self.invoice_id = invoice.id

    def view_invoice(self):
        """
           This function retrieves the associated invoice record (account.move) based on the
           'ownership_line_id' field and displays it in a form view for viewing or editing. """
        move = self.env['account.move'].sudo().search([('ownership_line_id', '=', self.id)])
        return {
            'name': _('Invoice'),
            'view_type': 'form',
            'res_id': move.id,
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def get_delay_amount(self):
        """
        Calculate and update delay amounts for unpaid and overdue installment lines.
         This function searches for installment lines that are marked as not paid and have no delay state set
        """
        installment_line = self.env['ownership.contract.line'].search(
            [('payment_state', '=', 'not_paid'), ('delay_state', '=', ' ')])
        for record in installment_line:
            if record.oc_id.template_id and record.date:
                today_date = fields.Date.today()
                delay_days = (today_date - record.date).days
            if delay_days >= record.oc_id.template_id.delay_process:
                record.delay_amount = record.amount * record.oc_id.template_id.delay_penalty
                record.delay_state = 'draft'
            else:
                record.delay_amount = 0.0

    def create_delay_invoice(self):
        """
           Create a delay invoice for overdue installment lines with a 'draft' delay state.
           This function checks if the delay amount is greater than zero and the delay state is
           'draft' for each installment line """
        for record in self:
            if record.delay_amount > 0 and record.delay_state == 'draft':
                account_in = int(
                    self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.ownership_delay_account'))
                invoice_vals = {
                    'partner_id': record.oc_id.partner_id.id,
                    'ownership_delay_line_id': record.id,
                    'move_type': 'out_invoice',
                    'invoice_line_ids': [
                        (0, 0, {
                            'name': 'Delay Amount',
                            'quantity': 1,
                            'account_id': account_in,
                            'price_unit': record.delay_amount,
                        }),
                    ],
                }
                invoice = self.env['account.move'].create(invoice_vals)
                invoice.action_post()
                record.d_invoice_id = invoice.id
                record.delay_state = 'invoiced'

    def view_delay_invoice(self):
        """
            Open the associated delay invoice record for the current installment line."""
        move = self.env['account.move'].sudo().search([('ownership_delay_line_id', '=', self.id)])
        return {
            'name': _('Invoice'),
            'view_type': 'form',
            'res_id': move.id,
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def set_delay_state_dismissed(self):
        """
            Set the delay_state field to 'dismissed' for the selected records. """
        for record in self:
            if record.delay_state != 'dismissed':
                record.delay_state = 'dismissed'

    def send_email_to_partner(self):
        """
           Send an email notification to the partner for overdue property installment amounts. """
        over_due_days = 3
        today = fields.date.today()
        invoice = self.env['ownership.contract.line'].search([('payment_state', '=', 'not_paid'), ('date', '<', today)])
        components = {}
        for m in invoice:
            over_date = (today - m.date).days
            if over_date >= over_due_days:
                components = {
                    'user_name': m.oc_id.partner_id.name,
                    'user_email': m.oc_id.partner_id.email,
                    'deadline': m.date,
                    'amount': m.amount, }
                print(components, 'components')

            template_id = self.env.ref('nthub_realestate.loan_installment_email_template').id
            self.env['mail.template'].browse(template_id).with_context(components).send_mail(m.id, force_send=True)


class OwnershipAttachmentLine(models.Model):
    _name = 'ownership.attachment.line'
    _description = "ownership.attachment.line"

    name = fields.Char(string=_("Name"))
    file = fields.Binary(string=_("File"))
    ownership_attachment_id = fields.Many2one("ownership.contract")


class OwnerContractFurniture(models.Model):
    _name = 'owner.contract.furniture'
    _description = "owner contract furniture"

    product_id = fields.Many2one("product.product", string=_("Product"), domain="[('furniture', '=', True)]")
    description = fields.Char(string=_('Description'))
    list_price = fields.Float(related="product_id.list_price", store=True)
    contract_id = fields.Many2one("ownership.contract")
    product_qty = fields.Integer(string=_("Quantity"), default=1)


class OwnerContractMaintenance(models.Model):
    _name = 'ownership.contract.maintenance.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Ownership Contract Maintenance'

    name = fields.Char(string=_("Reference"), required=True)
    serial = fields.Char("#")
    date = fields.Date()
    invoice_id = fields.Many2one('account.move', string='Invoice', )
    payment_state = fields.Selection(related='invoice_id.payment_state', readonly=True, store=True)
    invoice_state = fields.Selection(related='invoice_id.state', readonly=True, store=True)
    amount = fields.Float(string=_("Payment"))
    amount_residual = fields.Monetary(related='invoice_id.amount_residual', readonly=True, )
    currency_id = fields.Many2one(related='invoice_id.currency_id', readonly=True)
    oc_id = fields.Many2one('ownership.contract')
    reference = fields.Char(string="Reference", related='oc_id.name', store=True)
    customer_id = fields.Many2one(related='oc_id.partner_id', store=True)

    def make_invoice(self):
        """
            Create and post an invoice for a given record.
            This function generates an invoice for the current record and posts it in the
            accounting system. """
        for rec in self:
            account_move = self.env['account.move']
            journal_pool = self.env['account.journal']
            journal = journal_pool.search([('type', '=', 'sale')], limit=1)
            account_in = int(self.env['ir.config_parameter'].sudo().get_param('nthub_realestate.ownership_maintenance_account'))
            if not account_in:
                raise UserError(_('Please set income account for maintenance from setting!'))
            invoice = account_move.create({
                'journal_id': journal.id,
                'partner_id': rec.oc_id.partner_id.id,
                'move_type': 'out_invoice',
                'ownership_maintenance_line_id': rec.id,
                'invoice_date_due': rec.date,
                'ref': (rec.oc_id.name + ' - ' + rec.name),
                'invoice_line_ids': [(0, None, {
                    'name': (rec.oc_id.name + ' - ' + rec.name),
                    'quantity': 1,
                    'account_id': account_in,
                    'price_unit': rec.amount, })]
            })
            invoice.action_post()
            self.invoice_id = invoice.id

    def view_invoice(self):
        """
           This function retrieves the associated invoice record (account.move) based on the
           'ownership_maintenance_line_id' field and displays it in a form view for viewing or editing. """
        move = self.env['account.move'].sudo().search([('ownership_maintenance_line_id', '=', self.id)])
        return {
            'name': _('Invoice'),
            'view_type': 'form',
            'res_id': move.id,
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }