from odoo import models, fields, api, _

class ParkingContractHistory(models.Model):
    _name = "parking.contract.history"
    _description = "Contract Check In/Out History"
    _order = "check_in desc"

    contract_id = fields.Many2one("parking.contract", string="Contract", required=True)
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", required=True)
    check_in = fields.Datetime(string="Check In", required=True, default=fields.Datetime.now)
    check_out = fields.Datetime(string="Check Out")
    operator_in_id = fields.Many2one("res.users", string="Operator (In)", default=lambda self: self.env.user)
    operator_out_id = fields.Many2one("res.users", string="Operator (Out)")
    notes = fields.Text(string="Notes")
    duration_hours = fields.Float(string="Duration (Hours)", compute="_compute_duration", store=True)

    spot_id = fields.Many2one("parking.spot", related="contract_id.spot_id", string="Spot", store=True)
    location_id = fields.Many2one("parking.location", related="spot_id.location_id", string="Branch", store=True)

    @api.depends("check_in", "check_out")
    def _compute_duration(self):
        for r in self:
            if r.check_in and r.check_out:
                delta = r.check_out - r.check_in
                r.duration_hours = delta.total_seconds() / 3600
            else:
                r.duration_hours = 0

    def action_check_out(self):
        self.write({
            "check_out": fields.Datetime.now(),
            "operator_out_id": self.env.user.id,
        })
