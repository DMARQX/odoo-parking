from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ParkingReceptionServiceLine(models.TransientModel):
    _name = "parking.reception.service.line"
    _description = "Reception Wizard Service Line"

    wizard_id = fields.Many2one("parking.reception.wizard", string="Wizard", ondelete="cascade")
    service_id = fields.Many2one("parking.service", string="Service", required=True)
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    price_unit = fields.Monetary(string="Unit Price", currency_field="company_currency_id")
    price_subtotal = fields.Monetary(string="Subtotal", compute="_compute_subtotal",
                                     currency_field="company_currency_id", store=True)
    company_currency_id = fields.Many2one("res.currency", related="wizard_id.company_currency_id")
    company_id = fields.Many2one("res.company", related="wizard_id.company_id")

    @api.onchange("service_id")
    def _onchange_service_id(self):
        if self.service_id and not self.price_unit:
            self.price_unit = self.service_id.price

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for r in self:
            r.price_subtotal = r.quantity * (r.price_unit or 0)


class ParkingReceptionWizard(models.TransientModel):
    _name = "parking.reception.wizard"
    _description = "Vehicle Reception / Delivery Wizard"

    step = fields.Selection([
        ("1", "Operation"),
        ("2", "Customer & Vehicle"),
        ("3", "Inspection & Handover"),
        ("4", "Spot"),
        ("5", "Services"),
        ("6", "Summary"),
    ], string="Step", default="1", required=True)

    operation = fields.Selection([
        ("check_out", "Check Out (Delivery)"),
        ("check_in", "Check In (Reception)"),
    ], string="Operation", required=True, default="check_out")

    # Step 2 - Customer & Vehicle
    partner_id = fields.Many2one("res.partner", string="Customer",
        help="Select the customer to find their active contracts.")
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle",
        help="Select the vehicle by license plate.")
    contract_id = fields.Many2one("parking.contract", string="Contract",
        help="Active subscription contract for the selected vehicle.")
    contract_found = fields.Boolean(string="Contract Found", compute="_compute_contract")

    # Step 3 - Inspection & handover record
    do_inspection = fields.Boolean(string="Register Inspection", default=True)
    inspection_notes = fields.Text(string="Inspection Notes")
    odometer = fields.Integer(string="Odometer (km)")
    fuel = fields.Selection([
        ("empty", "Empty"), ("quarter", "1/4"), ("half", "1/2"), ("three_quarters", "3/4"), ("full", "Full"),
    ], string="Fuel Level")
    counterpart = fields.Char(string="Handed To / Received From",
        help="Name of the person taking the vehicle (delivery) or bringing it back (reception).")
    photo_ids = fields.Many2many("ir.attachment", "parking_reception_wizard_attachment_rel",
                                 "wizard_id", "attachment_id", string="Photos")
    signature = fields.Binary(string="Customer Signature")
    key_slot = fields.Char(string="Key Box Slot", help="Where the key is stored after reception.")

    # Step 4 - Spot
    spot_id = fields.Many2one("parking.spot", string="Spot",
        domain="[('status', 'in', ['available', 'occupied', 'client_out'])]")

    # Step 5 - Services
    service_line_ids = fields.One2many("parking.reception.service.line", "wizard_id", string="Additional Services")
    services_total = fields.Monetary(string="Services Total", compute="_compute_services_total",
                                     currency_field="company_currency_id")

    # Step 6 - Summary
    movement_id = fields.Many2one("parking.vehicle.movement", string="Movement", readonly=True)

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")

    @api.model
    def _open_for(self, operation, spot=None, vehicle=None, contract=None):
        """Open the wizard at the handover step for a known vehicle (spot or movement buttons)."""
        ctx = {
            "default_operation": operation,
            "default_spot_id": spot.id if spot else False,
            "default_vehicle_id": vehicle.id if vehicle else False,
            "default_contract_id": contract.id if contract else False,
            "default_partner_id": contract.partner_id.id if contract else False,
            "default_step": "3",
            "default_key_slot": vehicle.key_slot if vehicle else False,
        }
        return {
            "name": _("Deliver Vehicle") if operation == "check_out" else _("Receive Vehicle"),
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        # Opened from "Receive" / "Deliver" (dashboard, spot, menu shortcut):
        # the operation is already known, so start at the vehicle step.
        if ctx.get("default_operation") and "step" in fields_list and not ctx.get("default_step"):
            res["step"] = "2"
        spot = self.env["parking.spot"].browse(ctx.get("default_spot_id") or [])
        if spot and "vehicle_id" in fields_list and not res.get("vehicle_id"):
            contract = spot.current_contract_id
            if contract:
                res.update({
                    "contract_id": contract.id,
                    "partner_id": contract.partner_id.id,
                    "vehicle_id": contract.vehicle_ids[:1].id,
                })
        return res

    @api.onchange("operation")
    def _onchange_operation(self):
        if not self.env.context.get("default_operation"):
            self.step = "1"

    @api.onchange("contract_id")
    def _onchange_contract_id_spot(self):
        if self.contract_id.spot_id and not self.spot_id:
            self.spot_id = self.contract_id.spot_id

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id and not self.vehicle_id:
            domain = [("partner_id", "=", self.partner_id.id), ("state", "=", "active")]
            contracts = self.env["parking.contract"].search(domain, limit=1)
            if contracts:
                self.contract_id = contracts.id

    @api.onchange("vehicle_id")
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            contract = self.env["parking.contract"].search([
                ("vehicle_ids", "in", [self.vehicle_id.id]), ("state", "=", "active"),
            ], limit=1)
            self.contract_id = contract.id or False
            if contract:
                self.partner_id = contract.partner_id.id
                self.spot_id = contract.spot_id.id
            elif not self.partner_id:
                vehicle = self.vehicle_id
                if vehicle.owner_id:
                    self.partner_id = vehicle.owner_id.id

    @api.depends("contract_id", "contract_id.state")
    def _compute_contract(self):
        for r in self:
            r.contract_found = bool(r.contract_id and r.contract_id.state == "active")

    def action_next(self):
        self.ensure_one()
        if self.step == "1":
            self.step = "2"
        elif self.step == "2":
            if not self.vehicle_id:
                raise UserError(_("Please select a vehicle to continue."))
            if self.operation == "check_out" and not self.contract_id:
                raise UserError(_("No active contract found for this vehicle. Check-out requires an active subscription."))
            self.step = "3"
        elif self.step == "3":
            self.step = "4"
        elif self.step == "4":
            if not self.spot_id:
                raise UserError(_("Please choose the parking spot."))
            self.step = "5"
        elif self.step == "5":
            self.step = "6"
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "res_id": self.id, "view_mode": "form", "target": "new",
                "context": self.env.context}

    def action_back(self):
        self.ensure_one()
        steps = ["1", "2", "3", "4", "5", "6"]
        if self.step in steps:
            idx = steps.index(self.step)
            self.step = steps[max(0, idx - 1)]
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "res_id": self.id, "view_mode": "form", "target": "new",
                "context": self.env.context}

    @api.depends("service_line_ids", "service_line_ids.price_subtotal")
    def _compute_services_total(self):
        for r in self:
            r.services_total = sum(r.service_line_ids.mapped("price_subtotal"))

    def _handover_values(self, inspection):
        """Movement fields for this side of the handover (out = delivery, in = reception)."""
        side = "out" if self.operation == "check_out" else "in"
        values = {
            "%s_odometer" % side: self.odometer or 0,
            "%s_fuel" % side: self.fuel or False,
            "%s_signature" % side: self.signature or False,
            "%s_attachment_ids" % side: [(6, 0, self.photo_ids.ids)],
            ("out_handover_to" if side == "out" else "in_received_from"): self.counterpart or False,
        }
        if self.inspection_notes:
            values["notes"] = self.inspection_notes
        if inspection:
            values["inspection_id"] = inspection.id
        if side == "in":
            values["key_slot"] = self.key_slot or False
        return values

    def _register_inspection(self):
        if not self.do_inspection:
            return False
        return self.env["parking.vehicle.inspection"].create({
            "vehicle_id": self.vehicle_id.id,
            "notes": self.inspection_notes or False,
        })

    def _add_service_lines(self, contract):
        """Services sold at the counter are invoiced on their own; subscription add-ons join the contract."""
        lines = self.service_line_ids.filtered("service_id")
        if not lines or not contract:
            return
        recurring = lines.filtered(lambda l: l.service_id.billing_type == "recurring")
        for line in recurring:
            self.env["parking.contract.service.line"].sudo().create({
                "contract_id": contract.id,
                "service_id": line.service_id.id,
                "quantity": line.quantity,
                "price_unit": line.price_unit or line.service_id.price,
                "billing_type": "recurring",
            })
        if recurring:
            contract._onchange_service_line_ids_wash()
        sales = lines - recurring
        if sales:
            contract._create_charge_invoice([{
                "service": l.service_id, "product": l.service_id.product_id, "name": l.service_id.name,
                "quantity": l.quantity, "price_unit": l.price_unit or l.service_id.price,
            } for l in sales])

    def action_confirm(self):
        self.ensure_one()
        if not self.vehicle_id:
            raise UserError(_("Please select a vehicle."))
        if not self.spot_id:
            raise UserError(_("Please choose the parking spot."))
        if self.operation == "check_out" and not self.contract_id:
            raise UserError(_("No active contract found for this vehicle. Check-out requires an active subscription."))

        contract = self.contract_id
        inspection = self._register_inspection()
        values = self._handover_values(inspection)
        Movement = self.env["parking.vehicle.movement"]
        if self.operation == "check_out":
            movement = Movement._parking_deliver(self.spot_id, contract, self.vehicle_id, values)
        else:
            movement = Movement._parking_receive(self.spot_id, contract, self.vehicle_id, values)
        if inspection:
            inspection.write({"state": "done"})

        self.movement_id = movement.id
        self._add_service_lines(contract)

        return {
            "name": _("Movement Registered"),
            "type": "ir.actions.act_window",
            "res_model": "parking.vehicle.movement",
            "res_id": movement.id,
            "view_mode": "form",
            "target": "current",
        }