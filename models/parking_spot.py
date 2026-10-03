from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ParkingSpot(models.Model):
    _name = "parking.spot"
    _description = "Parking Spot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "full_name"
    _order = "location_id, sequence, id"

    name = fields.Char(string="Spot Number", readonly=True, copy=False)
    sequence = fields.Integer(string="Sequence", default=0, copy=False)
    location_id = fields.Many2one("parking.location", string="Branch", required=True, tracking=True)
    full_name = fields.Char(string="Full Name", compute="_compute_full_name", store=True)
    spot_type = fields.Selection([
        ("standard", "Standard"),
        ("large", "Large / SUV"),
        ("motorcycle", "Motorcycle"),
        ("vip", "VIP"),
    ], string="Spot Type", required=True, default="standard")
    spot_type_id = fields.Many2one("parking.spot.type", string="Spot Type", ondelete="restrict", tracking=True)
    status = fields.Selection([
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("occupied", "Occupied"),
        ("client_out", "Client Out"),
        ("maintenance", "Maintenance"),
    ], string="Status", default="available", required=True, tracking=True)
    floor = fields.Char(string="Floor / Zone")
    price_tmpl_id = fields.Many2one("parking.price.template", string="Price Template", tracking=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color Index", compute="_compute_color")
    contract_ids = fields.One2many("parking.contract", "spot_id", string="Contracts")
    current_contract_id = fields.Many2one("parking.contract", string="Current Contract", compute="_compute_current_contract")
    current_vehicle_plate = fields.Char(string="License Plate", compute="_compute_current_vehicle", store=False)
    current_vehicle_brand = fields.Char(string="Brand", compute="_compute_current_vehicle", store=False)
    current_vehicle_model = fields.Char(string="Model", compute="_compute_current_vehicle", store=False)
    current_owner_id = fields.Many2one("res.partner", string="Owner", compute="_compute_current_vehicle", store=False)
    current_owner_mobile = fields.Char(string="Owner Mobile", compute="_compute_current_vehicle", store=False)
    current_vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", compute="_compute_current_vehicle")
    current_vehicle_count = fields.Integer(compute="_compute_current_vehicle")
    current_brand_id = fields.Many2one("parking.vehicle.brand", string="Vehicle Brand", compute="_compute_current_vehicle")
    current_brand_logo = fields.Image(string="Brand Logo", compute="_compute_current_vehicle")
    current_brand_color = fields.Char(compute="_compute_current_vehicle")
    current_brand_initials = fields.Char(compute="_compute_current_vehicle")
    current_contract_end = fields.Date(string="Contract Ends", compute="_compute_current_vehicle")
    current_days_left = fields.Integer(string="Days Left", compute="_compute_current_vehicle")
    status_log_ids = fields.One2many("parking.spot.status.log", "spot_id", string="Status History")
    movement_ids = fields.One2many("parking.vehicle.movement", "spot_id", string="Vehicle Movements")
    last_movement_id = fields.Many2one("parking.vehicle.movement", string="Last Movement", compute="_compute_last_movement")
    last_movement_out = fields.Datetime(string="Last Check Out", compute="_compute_last_movement")
    last_movement_in = fields.Datetime(string="Last Check In", compute="_compute_last_movement")
    waiting_hours = fields.Float(string="Waiting Hours", compute="_compute_waiting_hours", search="_search_waiting_hours")
    waiting_label = fields.Char(string="Out For", compute="_compute_waiting_hours")
    _sql_constraints = [
        ("spot_name_location_unique", "unique(location_id, name)", "Spot number must be unique within the same branch!"),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        # Track the last number per branch so spots created together get
        # consecutive numbers instead of all reading the same "last" spot.
        next_seq = {}
        for vals in vals_list:
            loc_id = vals.get("location_id")
            if loc_id and not vals.get("sequence"):
                if loc_id not in next_seq:
                    last = self.with_context(active_test=False).search(
                        [("location_id", "=", loc_id)], order="sequence desc", limit=1)
                    next_seq[loc_id] = last.sequence or 0
                next_seq[loc_id] += 1
                vals["sequence"] = next_seq[loc_id]
            if not vals.get("name") and loc_id:
                location = self.env["parking.location"].browse(loc_id)
                code = location.code or "SP"
                vals["name"] = f"{code}-{vals.get('sequence') or 0:04d}"
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
        for spot in self.sudo():
            if spot.contract_ids.filtered(lambda c: c.state == "active"):
                continue
            if spot.contract_ids.filtered(lambda c: c.state == "confirmed"):
                if spot.status in ("occupied", "client_out"):
                    spot._set_status("reserved")
            elif spot.status in ("occupied", "client_out", "reserved"):
                spot._set_status("available")

    @api.depends("current_contract_id", "current_contract_id.vehicle_ids", "current_contract_id.partner_id",
                 "current_contract_id.vehicle_ids.brand_id", "current_contract_id.end_date")
    def _compute_current_vehicle(self):
        today = fields.Date.context_today(self)
        for r in self:
            contract = r.current_contract_id
            v = contract.vehicle_ids[:1] if contract else self.env["parking.vehicle"]
            brand = v.brand_id
            r.current_vehicle_id = v
            r.current_vehicle_count = len(contract.vehicle_ids) if contract else 0
            r.current_vehicle_plate = v.license_plate or ""
            r.current_vehicle_brand = brand.name or v.brand or ""
            r.current_vehicle_model = v.model or ""
            r.current_brand_id = brand
            r.current_brand_logo = brand.logo
            r.current_brand_color = brand.color or "#64748b"
            r.current_brand_initials = brand.initials or (v.brand or "")[:2].upper()
            r.current_owner_id = contract.partner_id if contract else False
            r.current_owner_mobile = (contract.partner_id.mobile or contract.partner_id.phone or "") if contract else ""
            r.current_contract_end = contract.end_date if contract else False
            r.current_days_left = (contract.end_date - today).days if contract and contract.end_date else 0

    def action_check_in(self):
        self._set_status("occupied")

    def action_check_out(self):
        self._set_status("available")

    def action_maintenance(self):
        if self.filtered("current_contract_id"):
            raise UserError(_("A spot with an active contract cannot be put under maintenance."))
        self._set_status("maintenance")

    def action_set_available(self):
        if self.filtered(lambda s: s.status != "maintenance"):
            raise UserError(_("Only spots under maintenance can be put back in service."))
        for spot in self:
            spot._set_status("available")
            spot._update_status_from_contracts()

    def _set_status(self, new_status):
        """Change the status and log the transition with the real previous status.

        Runs as superuser: contract and check-in staff move spots through their
        own actions without holding write access on spots or the status log.
        """
        logs = []
        for spot in self.sudo():
            if spot.status == new_status:
                continue
            logs.append({
                "spot_id": spot.id,
                "old_status": spot.status,
                "new_status": new_status,
                "operator_id": self.env.user.id,
            })
            spot.status = new_status
        if logs:
            self.env["parking.spot.status.log"].sudo().create(logs)

    def _create_status_log(self, new_status):
        # Kept for callers outside this file; prefer _set_status.
        self._set_status(new_status)

    def _handover_context(self):
        self.ensure_one()
        contract = self.current_contract_id
        if not contract:
            raise UserError(_("No active contract found for this spot."))
        vehicle = contract.vehicle_ids[:1]
        if not vehicle:
            raise UserError(_("No vehicles found in the active contract."))
        return contract, vehicle

    def action_vehicle_checkout(self):
        """Deliver the parked vehicle to the customer through the handover wizard."""
        self.ensure_one()
        if self.status != "occupied":
            raise UserError(_("Only occupied spots can be checked out."))
        contract, vehicle = self._handover_context()
        return self.env["parking.reception.wizard"]._open_for(
            "check_out", spot=self, vehicle=vehicle, contract=contract)

    def action_vehicle_checkin(self):
        """Receive the vehicle back through the handover wizard."""
        self.ensure_one()
        if self.status != "client_out":
            raise UserError(_("Only spots with Client Out status can be checked in."))
        contract, vehicle = self._handover_context()
        return self.env["parking.reception.wizard"]._open_for(
            "check_in", spot=self, vehicle=vehicle, contract=contract)

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
                hours = int(r.waiting_hours)
                if hours < 1:
                    r.waiting_label = _("%s min", max(int(delta.total_seconds() // 60), 1))
                elif hours < 48:
                    r.waiting_label = _("%s h", hours)
                else:
                    r.waiting_label = _("%s days", hours // 24)
            else:
                r.waiting_hours = 0
                r.waiting_label = False
