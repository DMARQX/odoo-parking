import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ParkingVehicleTransfer(models.Model):
    _name = "parking.vehicle.transfer"
    _description = "Vehicle Transfer"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "transfer_date desc, id desc"

    name = fields.Char(string="Reference", readonly=True, copy=False)
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", string="Customer", required=True, tracking=True)
    contract_id = fields.Many2one(
        "parking.contract", string="Contract", tracking=True,
        domain="[('partner_id', '=', partner_id), ('state', 'in', ('confirmed', 'active'))]",
        help="The vehicle's contract. The transfer is invoiced through it so it shows on the contract's statement.")
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    transfer_type_id = fields.Many2one("parking.transfer.type", string="Transfer Type", required=True, tracking=True)
    transfer_type_code = fields.Char(string="Transfer Type Code", related="transfer_type_id.code", store=True, readonly=True)
    destination_kind = fields.Selection(related="transfer_type_id.destination_kind", string="Destination")
    transfer_date = fields.Datetime(string="Transfer Date", default=fields.Datetime.now, required=True)
    completed_date = fields.Datetime(string="Completed On", readonly=True, copy=False)
    operator_id = fields.Many2one("res.users", string="Operator", default=lambda self: self.env.user)
    state = fields.Selection([
        ("draft", "Draft"),
        ("in_transit", "In Transit"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ], string="Status", default="draft", required=True, tracking=True, copy=False)

    source_location_id = fields.Many2one("parking.location", string="Source Branch")
    source_spot_id = fields.Many2one("parking.spot", string="Source Spot",
        domain="[('location_id', '=', source_location_id)]")

    destination_location_id = fields.Many2one("parking.location", string="Destination Branch")
    destination_spot_id = fields.Many2one("parking.spot", string="Destination Spot",
        domain="[('location_id', '=', destination_location_id), ('status', '=', 'available')]", tracking=True,
        help="A free spot in the destination branch. When the transfer is completed the vehicle's "
             "contract moves to it, provided it is still available.")
    contract_moved = fields.Boolean(string="Contract Moved", readonly=True, copy=False)

    service_center_name = fields.Char(string="Service Center Name")
    service_center_phone = fields.Char(string="Service Center Phone")
    service_center_address = fields.Text(string="Service Center Address")

    destination_partner_id = fields.Many2one("res.partner", string="Delivery Customer")
    destination_address = fields.Text(string="Delivery Address")

    # The driver is needed to start the transfer, not to plan it; a transporter (tow truck) is optional.
    driver_id = fields.Many2one("parking.driver", string="Driver", tracking=True)
    transporter_vehicle_id = fields.Many2one("parking.transporter.vehicle", string="Transporter Vehicle")
    transporter_notes = fields.Text(string="Transporter Notes")

    price = fields.Monetary(string="Price", currency_field="currency_id", tracking=True,
        help="Charged to the customer when the transfer is completed. Comes from the transfer type; excludes VAT.")
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True, copy=False)
    invoice_state = fields.Selection(related="invoice_id.state", string="Invoice Status")
    invoice_payment_state = fields.Selection(related="invoice_id.payment_state", string="Payment")

    notes = fields.Text(string="Notes")
    display_name = fields.Char(string="Transfer", compute="_compute_display_name", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("parking.vehicle.transfer") or "TR-001"
            if "price" not in vals and vals.get("transfer_type_id"):
                vals["price"] = self.env["parking.transfer.type"].browse(vals["transfer_type_id"]).price
        return super().create(vals_list)

    @api.depends("name", "vehicle_id", "transfer_type_id")
    def _compute_display_name(self):
        for r in self:
            parts = [r.name or ""]
            if r.vehicle_id:
                parts.append(r.vehicle_id.display_name or r.vehicle_id.license_plate or "")
            if r.transfer_type_id:
                parts.append(r.transfer_type_id.name or "")
            r.display_name = " - ".join(parts)

    # ------------------------------------------------------------------
    # The vehicle brings its customer, contract and current spot
    # ------------------------------------------------------------------
    @api.onchange("vehicle_id")
    def _onchange_vehicle_id(self):
        self._fill_from_vehicle(set_partner=True)

    def _fill_from_vehicle(self, set_partner):
        vehicle = self.vehicle_id
        if not vehicle:
            return
        contract = vehicle.current_contract_id
        if set_partner and vehicle.customer_id:
            self.partner_id = vehicle.customer_id
        # The contract only if it is this customer's (owner and contract holder can differ).
        if contract and contract.partner_id == self.partner_id:
            self.contract_id = contract
            if contract.spot_id:
                self.source_location_id = contract.location_id
                self.source_spot_id = contract.spot_id
            if contract.company_id:
                self.company_id = contract.company_id
        else:
            self.contract_id = False

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if not self.partner_id:
            return
        if self.vehicle_id and self.vehicle_id.customer_id == self.partner_id:
            return
        if not self.vehicle_id:
            # A customer with a single vehicle: no need to pick it. The chosen customer is kept.
            vehicles = self.partner_id._parking_vehicles()
            if len(vehicles) == 1:
                self.vehicle_id = vehicles
                self._fill_from_vehicle(set_partner=False)
        if self.contract_id and self.contract_id.partner_id != self.partner_id:
            self.contract_id = False

    @api.onchange("transfer_type_id")
    def _onchange_transfer_type_id(self):
        if self.transfer_type_id:
            self.price = self.transfer_type_id.price

    @api.onchange("destination_kind", "partner_id")
    def _onchange_destination_kind(self):
        if self.destination_kind == "customer":
            if not self.destination_partner_id:
                self.destination_partner_id = self.partner_id
            if not self.destination_address and self.destination_partner_id:
                address = (self.destination_partner_id._display_address(without_company=True) or "").strip()
                if address:
                    self.destination_address = address

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def _check_state(self, allowed, action):
        bad = self.filtered(lambda t: t.state not in allowed)
        if bad:
            raise UserError(_("You cannot %(action)s transfer(s) in this status: %(names)s",
                              action=action, names=", ".join(bad.mapped("name"))))

    def _check_ready(self):
        for r in self:
            if not r.driver_id:
                raise UserError(_("Choose the driver before starting transfer %s.", r.name))
            kind = r.destination_kind
            if kind == "branch" and not r.destination_location_id:
                raise UserError(_("Choose the destination branch of transfer %s.", r.name))
            if kind == "service_center" and not r.service_center_name:
                raise UserError(_("Enter the service center of transfer %s.", r.name))
            if kind == "customer" and not (r.destination_address or r.destination_partner_id):
                raise UserError(_("Enter the delivery address of transfer %s.", r.name))

    def action_draft(self):
        self._check_state(("cancelled",), _("reset to draft"))
        self.write({"state": "draft"})

    def action_in_transit(self):
        self._check_state(("draft",), _("start"))
        self._check_ready()
        self.write({"state": "in_transit"})

    def action_complete(self):
        self._check_state(("in_transit",), _("complete"))
        self.write({"state": "completed", "completed_date": fields.Datetime.now()})
        for r in self:
            r._move_contract_spot()
        for r in self.filtered(lambda t: t.price > 0 and not t._live_invoice()):
            # The vehicle has arrived either way: an accounting problem must not undo the completion.
            try:
                with self.env.cr.savepoint():
                    r._create_invoice()
            except UserError as e:
                r._message_log(body=_("The invoice could not be created: %s Use \"Create Invoice\" once this is fixed.",
                                      e.args[0] if e.args else e))
            except Exception as e:
                _logger.exception("Invoice of transfer %s failed", r.name)
                r._message_log(body=_("The invoice could not be created: %s Use \"Create Invoice\" once this is fixed.", e))

    def _move_contract_spot(self):
        """Branch transfer: the contract follows the vehicle to the destination spot, only when that
        spot is available. Otherwise the contract stays where it is and the reason is logged."""
        self.ensure_one()
        contract, spot = self.contract_id.sudo(), self.destination_spot_id.sudo()
        if self.destination_kind != "branch" or not contract or contract.state not in ("active", "confirmed"):
            return
        if not spot:
            self._message_log(body=_("No destination spot was chosen: contract %s stays on spot %s.",
                                     contract.name, contract.spot_id.full_name))
            return
        if spot == contract.spot_id:
            return
        reason = False
        if spot.status != "available":
            reason = _("spot %s is not available", spot.full_name)
        elif spot.location_id.company_id and spot.location_id.company_id != contract.company_id:
            reason = _("spot %(spot)s belongs to another company (%(company)s)",
                       spot=spot.full_name, company=spot.location_id.company_id.name)
        if not reason:
            old_spot = contract.spot_id
            try:
                with self.env.cr.savepoint():
                    contract.write({"spot_id": spot.id})
                    spot._set_status("occupied" if contract.state == "active" else "reserved")
            except (UserError, ValidationError) as e:
                reason = e.args[0] if e.args else str(e)
            else:
                self.sudo().contract_moved = True
                body = _("Contract %(contract)s moved from spot %(old)s to spot %(new)s by transfer %(ref)s.",
                         contract=contract.name, old=old_spot.full_name, new=spot.full_name, ref=self.name)
                self._message_log(body=body)
                contract._message_log(body=body)
                return
        self._message_log(body=_("Contract %(contract)s was not moved: %(reason)s. It stays on spot %(old)s.",
                                 contract=contract.name, reason=reason, old=contract.spot_id.full_name))

    def action_cancel(self):
        self._check_state(("draft", "in_transit"), _("cancel"))
        self.write({"state": "cancelled"})

    # ------------------------------------------------------------------
    # Invoicing: one invoice per transfer, priced by the transfer type
    # ------------------------------------------------------------------
    def _live_invoice(self):
        self.ensure_one()
        return self.invoice_id if self.invoice_id.state != "cancel" else self.env["account.move"]

    def _invoice_line_name(self):
        self.ensure_one()
        return _("Vehicle transfer %(ref)s - %(type)s - %(vehicle)s",
                 ref=self.name, type=self.transfer_type_id.name, vehicle=self.vehicle_id.license_plate or "")

    def _create_invoice(self):
        """Invoice the transfer: through the vehicle's contract when there is one (it then shows on
        the contract's statement), else straight to the customer."""
        self.ensure_one()
        if self._live_invoice():
            raise UserError(_("Transfer %s is already invoiced.", self.name))
        if self.price <= 0:
            raise UserError(_("Transfer %s has no price to invoice.", self.name))
        product = self.transfer_type_id.product_id
        contract = self.contract_id
        if contract:
            lang_contract = contract._invoice_ctx()
            name = self.with_context(lang=lang_contract.env.lang)._invoice_line_name()
            invoice = contract._create_charge_invoice(
                [{"product": product, "name": name, "quantity": 1.0, "price_unit": self.price}],
                origin="%s - %s" % (contract.name, self.name), credit_washes=False)
        else:
            company = self.company_id
            lang = company.parking_invoice_lang or self.partner_id.lang or self.env.lang
            fiscal_position = self.env["account.fiscal.position"].sudo().with_company(company)._get_fiscal_position(
                self.partner_id)
            taxes = product.taxes_id.filtered(lambda t: t.company_id in (company | company.parent_ids)) \
                or company.account_sale_tax_id
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)
            invoice = self.env["account.move"].sudo().with_company(company).create({
                "move_type": "out_invoice",
                "partner_id": self.partner_id.id,
                "invoice_date": fields.Date.context_today(self),
                "invoice_origin": self.name,
                "fiscal_position_id": fiscal_position.id,
                "invoice_line_ids": [(0, 0, {
                    "name": self.with_context(lang=lang)._invoice_line_name(),
                    "quantity": 1.0,
                    "price_unit": self.price,
                    "product_id": product.id or False,
                    "tax_ids": [(6, 0, taxes.ids)],
                })],
            })
            if company.parking_auto_post_invoices and invoice.amount_total > 0:
                invoice.action_post()
        self.sudo().invoice_id = invoice
        self._message_log(body=_("Transfer invoiced: %s", invoice._get_html_link()))
        return invoice

    def action_create_invoice(self):
        self.ensure_one()
        self._check_state(("completed",), _("invoice"))
        self._create_invoice()
        return self.action_view_invoice()

    def action_view_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
        }
