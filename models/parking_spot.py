from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ParkingSpot(models.Model):
    _name = "parking.spot"
    _description = "Parking Spot"
    _rec_name = "full_name"
    _order = "location_id, sequence, id"

    name = fields.Char(string="Spot Number", readonly=True, copy=False)
    sequence = fields.Integer(string="Sequence", default=0, copy=False)
    location_id = fields.Many2one("parking.location", string="Branch", required=True)
    full_name = fields.Char(string="Full Name", compute="_compute_full_name", store=True)
    spot_type = fields.Selection([
        ("standard", "Standard"),
        ("large", "Large / SUV"),
        ("motorcycle", "Motorcycle"),
        ("vip", "VIP"),
    ], string="Spot Type", required=True, default="standard")
    spot_type_id = fields.Many2one("parking.spot.type", string="Spot Type", ondelete="restrict")
    status = fields.Selection([
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("occupied", "Occupied"),
        ("client_out", "Client Out"),
        ("maintenance", "Maintenance"),
    ], string="Status", default="available", required=True)
    floor = fields.Char(string="Floor / Zone")
    price_tmpl_id = fields.Many2one("parking.price.template", string="Price Template")
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color Index", compute="_compute_color")
    contract_ids = fields.One2many("parking.contract", "spot_id", string="Contracts")
    current_contract_id = fields.Many2one("parking.contract", string="Current Contract", compute="_compute_current_contract")
    current_vehicle_plate = fields.Char(string="License Plate", compute="_compute_current_vehicle", store=False)
    current_vehicle_brand = fields.Char(string="Brand", compute="_compute_current_vehicle", store=False)
    current_vehicle_model = fields.Char(string="Model", compute="_compute_current_vehicle", store=False)
    current_owner_id = fields.Many2one("res.partner", string="Owner", compute="_compute_current_vehicle", store=False)
    current_owner_mobile = fields.Char(string="Owner Mobile", compute="_compute_current_vehicle", store=False)
    status_log_ids = fields.One2many("parking.spot.status.log", "spot_id", string="Status History")
    movement_ids = fields.One2many("parking.vehicle.movement", "spot_id", string="Vehicle Movements")
    last_movement_id = fields.Many2one("parking.vehicle.movement", string="Last Movement", compute="_compute_last_movement")
    last_movement_out = fields.Datetime(string="Last Check Out", compute="_compute_last_movement")
    last_movement_in = fields.Datetime(string="Last Check In", compute="_compute_last_movement")
    waiting_hours = fields.Float(string="Waiting Hours", compute="_compute_waiting_hours", search="_search_waiting_hours")
    _sql_constraints = [
        ("spot_name_location_unique", "unique(location_id, name)", "Spot number must be unique within the same branch!"),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            loc_id = vals.get("location_id")
            if not vals.get("sequence") or loc_id:
                last = self.search([("location_id", "=", loc_id)], order="sequence desc", limit=1)
                vals["sequence"] = (last.sequence or 0) + 1
            if not vals.get("name") and loc_id:
                location = self.env["parking.location"].browse(loc_id)
                code = location.code or "SP"
                vals["name"] = f"{code}-{vals['sequence']:04d}"
            elif not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("parking.spot") or "SP-0001"
        return super().create(vals_list)

    @api.depends("name", "location_id", "location_id.code")
    def _compute_full_name(self):
        for r in self:
            code = r.location_id.code if r.location_id else ""
            r.full_name = f"[{code}] {r.name}"

    @api.depends("contract_ids", "contract_ids.state")
    def _compute_current_contract(self):
        for r in self:
            active_contract = r.contract_ids.filtered(lambda c: c.state == "active")
            r.current_contract_id = active_contract[:1] if active_contract else False

    def _update_status_from_contracts(self):
        for spot in self:
            active = spot.contract_ids.filtered(lambda c: c.state == "active")
            if not active and spot.status in ("occupied", "client_out", "reserved"):
                spot.status = "available"

    @api.depends("current_contract_id", "current_contract_id.vehicle_ids", "current_contract_id.partner_id")
    def _compute_current_vehicle(self):
        for r in self:
            contract = r.current_contract_id
            if contract and contract.vehicle_ids:
                v = contract.vehicle_ids[0]
                r.current_vehicle_plate = v.license_plate
                r.current_vehicle_brand = v.brand
                r.current_vehicle_model = v.model
            else:
                r.current_vehicle_plate = ""
                r.current_vehicle_brand = ""
                r.current_vehicle_model = ""
            r.current_owner_id = contract.partner_id if contract else False
            r.current_owner_mobile = contract.partner_id.mobile if contract and contract.partner_id else ""

    def action_check_in(self):
        self.status = "occupied"
        self._create_status_log("occupied")

    def action_check_out(self):
        self.status = "available"
        self._create_status_log("available")

    def action_maintenance(self):
        self.status = "maintenance"
        self._create_status_log("maintenance")

    def _create_status_log(self, new_status):
        self.env["parking.spot.status.log"].create({
            "spot_id": self.id,
            "old_status": self._original_status if hasattr(self, "_original_status") else self.status,
            "new_status": new_status,
            "operator_id": self.env.user.id,
        })

    def action_vehicle_checkout(self):
        self.ensure_one()
        if self.status != "occupied":
            raise UserError(_("Only occupied spots can be checked out."))
        contract = self.current_contract_id
        if not contract:
            raise UserError(_("No active contract found for this spot."))
        vehicle = contract.vehicle_ids[:1] if contract.vehicle_ids else False
        if not vehicle:
            raise UserError(_("No vehicles found in the active contract."))
        old_status = self.status
        self.env["parking.vehicle.movement"].create({
            "spot_id": self.id,
            "contract_id": contract.id,
            "vehicle_id": vehicle.id,
            "check_out_time": fields.Datetime.now(),
            "operator_out_id": self.env.user.id,
        })
        self.status = "client_out"
        self.env["parking.spot.status.log"].create({
            "spot_id": self.id,
            "old_status": old_status,
            "new_status": "client_out",
            "operator_id": self.env.user.id,
        })

    def action_vehicle_checkin(self):
        self.ensure_one()
        if self.status != "client_out":
            raise UserError(_("Only spots with Client Out status can be checked in."))
        contract = self.current_contract_id
        if not contract:
            contract = self.contract_ids.filtered(lambda c: c.state == "active")[:1]
        if not contract:
            raise UserError(_("No active contract found for this spot."))
        movement = self.env["parking.vehicle.movement"].search([
            ("spot_id", "=", self.id),
            ("contract_id", "=", contract.id),
            ("check_in_time", "=", False),
        ], order="check_out_time desc", limit=1)
        if movement:
            movement.write({
                "check_in_time": fields.Datetime.now(),
                "operator_in_id": self.env.user.id,
            })
        old_status = self.status
        self.status = "occupied"
        self.env["parking.spot.status.log"].create({
            "spot_id": self.id,
            "old_status": old_status,
            "new_status": "occupied",
            "operator_id": self.env.user.id,
        })

    @api.depends("movement_ids", "movement_ids.check_out_time", "movement_ids.check_in_time")
    def _compute_last_movement(self):
        for r in self:
            moves = r.movement_ids.sorted(key=lambda m: m.check_out_time or m.create_date or fields.Datetime.now(), reverse=True)
            r.last_movement_id = moves[:1] if moves else False
            r.last_movement_out = moves[0].check_out_time if moves else False
            r.last_movement_in = moves[0].check_in_time if moves else False

    def _search_waiting_hours(self, operator, operand):
        from datetime import timedelta
        cutoff = fields.Datetime.now() - timedelta(hours=operand)
        if operator in (">", ">="):
            return [("status", "=", "client_out"), ("last_movement_out", "<=", cutoff)]
        elif operator in ("<", "<="):
            return [("status", "=", "client_out"), ("last_movement_out", ">=", cutoff)]
        return [("status", "=", "client_out"), ("last_movement_out", "!=", False)]

    @api.depends("status", "last_movement_out")
    def _compute_color(self):
        for r in self:
            if r.status == "client_out" and r.last_movement_out:
                delta = fields.Datetime.now() - r.last_movement_out
                hours = delta.total_seconds() / 3600
                if hours > 4:
                    r.color = 10
                elif hours > 1:
                    r.color = 3
                else:
                    r.color = 2
            else:
                r.color = 0

    def _is_arabic_context(self):
        return (self.env.context.get('lang') or self.env.user.lang or '').startswith('ar')

    @api.depends("status", "last_movement_out")
    def _compute_waiting_hours(self):
        now = fields.Datetime.now()
        for r in self:
            if r.status == "client_out" and r.last_movement_out:
                delta = now - r.last_movement_out
                r.waiting_hours = delta.total_seconds() / 3600
            else:
                r.waiting_hours = 0
