from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

FUEL_LEVELS = [
    ("empty", "Empty"),
    ("quarter", "1/4"),
    ("half", "1/2"),
    ("three_quarters", "3/4"),
    ("full", "Full"),
]


class ParkingVehicleMovement(models.Model):
    """One movement = one trip of a vehicle out of its spot and back.

    Delivery to the customer opens the trip (check_out_time); the return closes it
    (check_in_time). A vehicle received for the first time with no open trip is
    recorded as a "first arrival". Times are only set through _parking_deliver /
    _parking_receive so the spot status, key status and notifications stay in step.
    """
    _name = "parking.vehicle.movement"
    _description = "Vehicle Movement"
    _order = "id desc"
    _rec_name = "display_name"
    _inherit = ["mail.thread"]

    name = fields.Char(string="Reference", readonly=True, copy=False, default=lambda self: _("New"))
    movement_type = fields.Selection([
        ("trip", "Trip (out and back)"),
        ("arrival", "First arrival"),
    ], string="Type", required=True, default="trip", readonly=True)
    state = fields.Selection([
        ("out", "With the customer"),
        ("returned", "Returned"),
        ("arrival", "Arrived"),
    ], string="Status", compute="_compute_state", store=True, index=True)

    spot_id = fields.Many2one("parking.spot", string="Spot", readonly=True)
    contract_id = fields.Many2one("parking.contract", string="Contract", readonly=True)
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", required=True, readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer",
        related="contract_id.partner_id", store=True, readonly=True)
    location_id = fields.Many2one("parking.location", string="Branch",
        related="spot_id.location_id", store=True, readonly=True)

    # Delivery to the customer
    check_out_time = fields.Datetime(string="Delivered At", readonly=True)
    operator_out_id = fields.Many2one("res.users", string="Delivered By", readonly=True)
    out_handover_to = fields.Char(string="Handed To", help="Person who took the vehicle.")
    out_odometer = fields.Integer(string="Odometer Out (km)")
    out_fuel = fields.Selection(FUEL_LEVELS, string="Fuel Out")
    out_signature = fields.Binary(string="Customer Signature (Out)", attachment=True, copy=False)
    out_attachment_ids = fields.Many2many(
        "ir.attachment", "parking_movement_out_attachment_rel", "movement_id", "attachment_id",
        string="Photos (Out)")

    # Return to the parking
    check_in_time = fields.Datetime(string="Returned At", readonly=True)
    operator_in_id = fields.Many2one("res.users", string="Received By", readonly=True)
    in_received_from = fields.Char(string="Received From", help="Person who brought the vehicle back.")
    in_odometer = fields.Integer(string="Odometer In (km)")
    in_fuel = fields.Selection(FUEL_LEVELS, string="Fuel In")
    in_signature = fields.Binary(string="Customer Signature (In)", attachment=True, copy=False)
    in_attachment_ids = fields.Many2many(
        "ir.attachment", "parking_movement_in_attachment_rel", "movement_id", "attachment_id",
        string="Photos (In)")
    key_slot = fields.Char(string="Key Box Slot", help="Where the key was stored on return.")

    notes = fields.Text(string="Notes")
    inspection_id = fields.Many2one("parking.vehicle.inspection", string="Inspection")
    duration_hours = fields.Float(string="Duration (Hours)", compute="_compute_duration", store=True)
    distance_km = fields.Integer(string="Distance (km)", compute="_compute_duration", store=True)
    needs_review = fields.Boolean(
        string="Needs Review", compute="_compute_needs_review", store=True,
        help="Inconsistent times recorded before this was enforced (return before exit, return "
             "without exit, or no time at all). Check and correct them.")
    display_name = fields.Char(string="Movement", compute="_compute_display_name", store=True)

    # ------------------------------------------------------------ computes
    @api.depends("movement_type", "check_out_time", "check_in_time")
    def _compute_state(self):
        for r in self:
            if r.movement_type == "arrival":
                r.state = "arrival"
            elif r.check_in_time:
                r.state = "returned"
            else:
                r.state = "out"

    @api.depends("check_out_time", "check_in_time", "out_odometer", "in_odometer")
    def _compute_duration(self):
        for r in self:
            if r.check_out_time and r.check_in_time and r.check_in_time >= r.check_out_time:
                r.duration_hours = (r.check_in_time - r.check_out_time).total_seconds() / 3600
            else:
                r.duration_hours = 0
            r.distance_km = max(r.in_odometer - r.out_odometer, 0) if r.out_odometer and r.in_odometer else 0

    @api.depends("movement_type", "check_out_time", "check_in_time")
    def _compute_needs_review(self):
        for r in self:
            if r.movement_type == "arrival":
                r.needs_review = not r.check_in_time
            else:
                r.needs_review = (not r.check_out_time
                                  or bool(r.check_in_time and r.check_in_time < r.check_out_time))

    @api.depends("name", "vehicle_id", "state")
    def _compute_display_name(self):
        states = dict(self._fields["state"]._description_selection(self.env))
        for r in self:
            veh = r.vehicle_id.license_plate or r.vehicle_id.display_name or ""
            r.display_name = " - ".join(p for p in [r.name or "", veh, states.get(r.state, "")] if p)

    @api.constrains("check_out_time", "check_in_time")
    def _check_times(self):
        for r in self:
            if r.check_out_time and r.check_in_time and r.check_in_time < r.check_out_time:
                raise ValidationError(_("The return time cannot be before the delivery time."))

    @api.constrains("out_odometer", "in_odometer")
    def _check_odometer(self):
        for r in self:
            if r.out_odometer and r.in_odometer and r.in_odometer < r.out_odometer:
                raise ValidationError(_("The odometer on return (%(in)s) is lower than on delivery (%(out)s).",
                                        **{"in": r.in_odometer, "out": r.out_odometer}))

    # -------------------------------------------------------------- CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # The form sends the translated placeholder ("New" / "جديد").
            if not vals.get("name") or vals.get("name") in ("New", "جديد", "/", _("New")):
                vals["name"] = self.env["ir.sequence"].next_by_code("parking.vehicle.movement") or "MV-0001"
        records = super().create(vals_list)
        for rec in records:
            if rec.check_in_time:
                rec._notify_customer("vehicle_received")
            elif rec.check_out_time:
                rec._notify_customer("vehicle_delivered")
            rec._link_attachments()
        return records

    def write(self, vals):
        newly_back = self.filtered(lambda m: not m.check_in_time) if vals.get("check_in_time") else self.browse()
        res = super().write(vals)
        for rec in newly_back:
            rec._notify_customer("vehicle_received")
        if "out_attachment_ids" in vals or "in_attachment_ids" in vals:
            self._link_attachments()
        return res

    def _link_attachments(self):
        """Attach uploaded photos to the movement so they follow its access rights."""
        for rec in self:
            (rec.out_attachment_ids | rec.in_attachment_ids).sudo().filtered(
                lambda a: a.res_model != self._name or a.res_id != rec.id
            ).write({"res_model": self._name, "res_id": rec.id})

    def _notify_customer(self, event):
        partner = self.partner_id or self.vehicle_id.owner_id
        self.env["parking.notification.rule"]._notify(event, self, partner)

    # ------------------------------------------------------- the one path
    @api.model
    def _parking_deliver(self, spot, contract, vehicle, values=None):
        """Hand the vehicle to the customer: open a trip, free the spot, key goes with it."""
        values = dict(values or {})
        if not contract:
            raise UserError(_("Delivering a vehicle requires an active contract."))
        if self.search_count([("vehicle_id", "=", vehicle.id), ("state", "=", "out")]):
            raise UserError(_("Vehicle %s is already out with the customer; receive it back first.",
                              vehicle.display_name))
        movement = self.create(dict(values, **{
            "movement_type": "trip",
            "spot_id": spot.id,
            "contract_id": contract.id,
            "vehicle_id": vehicle.id,
            "check_out_time": fields.Datetime.now(),
            "operator_out_id": self.env.user.id,
        }))
        if spot.status == "occupied":
            spot._set_status("client_out")
        vehicle.sudo().key_status = "with_customer"
        return movement

    @api.model
    def _parking_receive(self, spot, contract, vehicle, values=None):
        """Take the vehicle back: close its open trip, or record its first arrival."""
        values = dict(values or {})
        now = fields.Datetime.now()
        movement = self.search([("vehicle_id", "=", vehicle.id), ("state", "=", "out")],
                               order="check_out_time desc", limit=1)
        if movement:
            movement.write(dict(values, **{"check_in_time": now, "operator_in_id": self.env.user.id}))
            spot = spot or movement.spot_id
        else:
            movement = self.create(dict(values, **{
                "movement_type": "arrival",
                "spot_id": spot.id,
                "contract_id": contract.id if contract else False,
                "vehicle_id": vehicle.id,
                "check_in_time": now,
                "operator_in_id": self.env.user.id,
            }))
        if spot and spot.status != "maintenance":
            spot._set_status("occupied")
        vehicle.sudo().write({"key_status": "in_box", "key_slot": values.get("key_slot") or vehicle.key_slot})
        return movement

    # ------------------------------------------------------------ actions
    def action_register_check_in(self):
        """Receive the vehicle back through the handover wizard (keeps everything in step)."""
        self.ensure_one()
        if self.state != "out":
            raise UserError(_("This vehicle is not out with the customer."))
        return self.env["parking.reception.wizard"]._open_for(
            "check_in", spot=self.spot_id, vehicle=self.vehicle_id, contract=self.contract_id)

    def action_print_handover(self):
        return self.env.ref("parking_management.action_report_vehicle_handover").report_action(self)
