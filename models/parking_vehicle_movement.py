from odoo import models, fields, api, _

class ParkingVehicleMovement(models.Model):
    _name = "parking.vehicle.movement"
    _description = "Unified Vehicle Movement Log"
    _order = "check_out_time desc, id desc"
    _rec_name = "display_name"
    _inherit = ["mail.thread"]

    name = fields.Char(string="Reference", readonly=True, copy=False, default=lambda self: _("New"))
    operation = fields.Selection([
        ("check_out", "Check Out / Exit"),
        ("check_in", "Check In / Return"),
    ], string="Operation", required=True, default="check_out")

    spot_id = fields.Many2one("parking.spot", string="Spot")
    contract_id = fields.Many2one("parking.contract", string="Contract")
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", required=True)
    partner_id = fields.Many2one("res.partner", string="Customer",
        related="contract_id.partner_id", store=True, readonly=True)
    location_id = fields.Many2one("parking.location", string="Branch",
        related="spot_id.location_id", store=True, readonly=True)

    check_out_time = fields.Datetime(string="Check Out")
    check_in_time = fields.Datetime(string="Check In")
    operator_out_id = fields.Many2one("res.users", string="Operator (Exit)", default=lambda self: self.env.user)
    operator_in_id = fields.Many2one("res.users", string="Operator (Return)")
    notes = fields.Text(string="Notes")

    state = fields.Selection([
        ("open", "Open"),
        ("closed", "Closed"),
    ], string="Status", compute="_compute_state")

    inspection_id = fields.Many2one("parking.vehicle.inspection", string="Inspection")
    duration_hours = fields.Float(string="Duration (Hours)", compute="_compute_duration", store=True)
    display_name = fields.Char(string="Movement", compute="_compute_display_name", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("parking.vehicle.movement") or "MV-0001"
        return super().create(vals_list)

    @api.depends("check_out_time", "check_in_time")
    def _compute_duration(self):
        for r in self:
            if r.check_out_time and r.check_in_time:
                delta = r.check_in_time - r.check_out_time
                r.duration_hours = delta.total_seconds() / 3600
            else:
                r.duration_hours = 0

    @api.depends("check_in_time")
    def _compute_state(self):
        for r in self:
            if r.check_in_time:
                r.state = "closed"
            else:
                r.state = "open"

    @api.depends("vehicle_id", "operation", "check_out_time", "check_in_time")
    def _compute_display_name(self):
        for r in self:
            veh = r.vehicle_id.display_name or r.vehicle_id.license_plate or ""
            parts = [r.name or "", veh]
            op_label = dict(self._fields["operation"].selection).get(r.operation, "")
            if op_label:
                parts.append(op_label)
            if r.check_out_time:
                parts.append("OUT: %s" % r.check_out_time.strftime("%Y-%m-%d %H:%M"))
            if r.check_in_time:
                parts.append("IN: %s" % r.check_in_time.strftime("%Y-%m-%d %H:%M"))
            r.display_name = " - ".join(parts)

    def action_register_check_in(self):
        """Close an open movement by registering the return of the vehicle."""
        self.ensure_one()
        if not self.check_in_time:
            self.write({
                "check_in_time": fields.Datetime.now(),
                "operator_in_id": self.env.user.id,
            })
        return True