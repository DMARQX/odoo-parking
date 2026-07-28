from odoo import models, fields, api

class ParkingVehicleInspection(models.Model):
    _name = "parking.vehicle.inspection"
    _description = "Vehicle Inspection"
    _order = "date desc, id desc"
    _rec_name = "display_name"

    name = fields.Char(string="Reference", readonly=True, copy=False)
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", required=True)
    date = fields.Datetime(string="Inspection Date", default=fields.Datetime.now, required=True)
    inspector_id = fields.Many2one("res.users", string="Inspector", default=lambda self: self.env.user, required=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("done", "Completed"),
        ("cancelled", "Cancelled"),
    ], string="Status", default="draft", required=True)
    line_ids = fields.One2many("parking.vehicle.inspection.line", "inspection_id", string="Checklist")
    notes = fields.Text(string="Notes")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)
    display_name = fields.Char(string="Display Name", compute="_compute_display_name", store=True)

    @api.depends("name", "vehicle_id", "vehicle_id.display_name")
    def _compute_display_name(self):
        for r in self:
            r.display_name = f"{r.name or 'New'} - {r.vehicle_id.display_name or ''}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("parking.vehicle.inspection") or "INSP-0001"
        records = super().create(vals_list)
        for record in records:
            record._auto_create_lines()
        return records

    def _auto_create_lines(self):
        existing = self.line_ids.mapped("checkpoint_id")
        checkpoints = self.env["parking.vehicle.checkpoint"].search([("active", "=", True)])
        new = checkpoints - existing
        for cp in new:
            self.line_ids.create({
                "inspection_id": self.id,
                "checkpoint_id": cp.id,
            })

    def action_done(self):
        self.state = "done"

    def action_cancel(self):
        self.state = "cancelled"

    def action_draft(self):
        self.state = "draft"

    def _is_arabic_context(self):
        return (self.env.context.get('lang') or self.env.user.lang or '').startswith('ar')

    def action_reload_checkpoints(self):
        self._auto_create_lines()
        return {
            "type": "ir.actions.act_window",
            "res_model": "parking.vehicle.inspection",
            "res_id": self.id,
            "view_mode": "form",
            "target": "main",
        }
