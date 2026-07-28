from odoo import models, fields, api, _

class ParkingVehicleMovement(models.Model):
    _name = "parking.vehicle.movement"
    _description = "Vehicle Check In/Out Movement"
    _order = "check_out_time desc, id desc"
    _rec_name = "display_name"

    spot_id = fields.Many2one("parking.spot", string="Spot")
    contract_id = fields.Many2one("parking.contract", string="Contract")
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", required=True)
    check_out_time = fields.Datetime(string="Check Out")
    check_in_time = fields.Datetime(string="Check In")
    operator_out_id = fields.Many2one("res.users", string="Operator (Exit)", default=lambda self: self.env.user)
    operator_in_id = fields.Many2one("res.users", string="Operator (Return)")
    duration_hours = fields.Float(string="Duration (Hours)", compute="_compute_duration", store=True)
    display_name = fields.Char(string="Movement", compute="_compute_display_name", store=True)

    @api.depends("check_out_time", "check_in_time")
    def _compute_duration(self):
        for r in self:
            if r.check_out_time and r.check_in_time:
                delta = r.check_in_time - r.check_out_time
                r.duration_hours = delta.total_seconds() / 3600
            else:
                r.duration_hours = 0

    @api.depends("vehicle_id", "check_out_time", "check_in_time")
    def _compute_display_name(self):
        for r in self:
            veh = r.vehicle_id.display_name or r.vehicle_id.license_plate or ""
            parts = [veh]
            if r.check_out_time:
                parts.append(r.check_out_time.strftime("%Y-%m-%d %H:%M"))
            if r.check_in_time:
                parts.append(f"IN: {r.check_in_time.strftime('%Y-%m-%d %H:%M')}")
            r.display_name = " - ".join(parts)
