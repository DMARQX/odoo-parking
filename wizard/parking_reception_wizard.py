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
        ("3", "Inspection"),
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

    # Step 3 - Inspection
    do_inspection = fields.Boolean(string="Register Inspection", default=True)
    inspection_notes = fields.Text(string="Inspection Notes")

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

    @api.onchange("operation")
    def _onchange_operation(self):
        self.step = "1"

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

    def _ensure_check_in_movement(self):
        """Find open movement for this vehicle or create a new one."""
        movement = self.env["parking.vehicle.movement"].search([
            ("vehicle_id", "=", self.vehicle_id.id),
            ("check_in_time", "=", False),
        ], order="check_out_time desc", limit=1)
        if not movement:
            movement = self.env["parking.vehicle.movement"].create({
                "operation": "check_in",
                "vehicle_id": self.vehicle_id.id,
                "contract_id": self.contract_id.id or False,
                "spot_id": self.spot_id.id or False,
                "check_out_time": False,
                "check_in_time": fields.Datetime.now(),
                "operator_in_id": self.env.user.id,
                "notes": self.inspection_notes or False,
            })
        else:
            movement.write({
                "check_in_time": fields.Datetime.now(),
                "operator_in_id": self.env.user.id,
                "notes": self.inspection_notes or False,
            })
        return movement

    def _register_inspection(self):
        if not self.do_inspection:
            return False
        return self.env["parking.vehicle.inspection"].create({
            "vehicle_id": self.vehicle_id.id,
            "notes": self.inspection_notes or False,
        })

    def _add_service_lines(self, contract):
        if not self.service_line_ids or not contract:
            return
        for line in self.service_line_ids:
            if not line.service_id:
                continue
            self.env["parking.contract.service.line"].create({
                "contract_id": contract.id,
                "service_id": line.service_id.id,
                "quantity": line.quantity,
                "price_unit": line.price_unit or line.service_id.price,
            })
        wash_packages = self.service_line_ids.filtered(
            lambda l: l.service_id and l.service_id.category == "wash" and l.service_id.included_washes
        )
        if wash_packages:
            contract.free_wash_count = max(l.service_id.included_washes for l in wash_packages)

    def action_confirm(self):
        self.ensure_one()
        if not self.vehicle_id:
            raise UserError(_("Please select a vehicle."))
        if not self.spot_id:
            raise UserError(_("Please choose the parking spot."))

        contract = self.contract_id
        inspection = self._register_inspection()
        inspection_id = inspection.id if inspection else False

        if self.operation == "check_out":
            movement = self.env["parking.vehicle.movement"].create({
                "operation": "check_out",
                "vehicle_id": self.vehicle_id.id,
                "contract_id": contract.id or False,
                "spot_id": self.spot_id.id,
                "check_out_time": fields.Datetime.now(),
                "operator_out_id": self.env.user.id,
                "inspection_id": inspection_id,
                "notes": self.inspection_notes or False,
            })
            old_status = self.spot_id.status
            if self.spot_id.status == "occupied":
                self.spot_id.status = "client_out"
                self.env["parking.spot.status.log"].create({
                    "spot_id": self.spot_id.id,
                    "old_status": old_status,
                    "new_status": "client_out",
                    "operator_id": self.env.user.id,
                })
            if inspection:
                inspection.write({"state": "done"})
        else:
            movement = self._ensure_check_in_movement()
            if inspection and not movement.inspection_id:
                movement.inspection_id = inspection.id
            old_status = self.spot_id.status
            self.spot_id.status = "occupied"
            self.env["parking.spot.status.log"].create({
                "spot_id": self.spot_id.id,
                "old_status": old_status,
                "new_status": "occupied",
                "operator_id": self.env.user.id,
            })
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