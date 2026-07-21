from odoo import models, fields, api, _

class ParkingLocation(models.Model):
    _name = "parking.location"
    _description = "Parking Branch / Location"
    _rec_name = "display_name"
    _order = "code, name"

    name = fields.Char(string="Branch Name", required=True)
    code = fields.Char(string="Branch Code", readonly=True, copy=False)
    city = fields.Char(string="City", required=True)
    address = fields.Text(string="Address")
    phone = fields.Char(string="Phone")
    manager_id = fields.Many2one("res.users", string="Branch Manager")
    active = fields.Boolean(default=True)
    spot_count = fields.Integer(string="Total Spots", compute="_compute_spot_count")
    available_count = fields.Integer(string="Available Spots", compute="_compute_spot_count")
    display_name = fields.Char(string="Display", compute="_compute_display_name", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                seq = self.env["ir.sequence"].next_by_code("parking.location") or "BR-001"
                vals["code"] = seq
        return super().create(vals_list)

    @api.depends("code", "name", "city")
    def _compute_display_name(self):
        for r in self:
            r.display_name = f"[{r.code}] {r.name} - {r.city}"

    @api.depends("spot_ids")
    def _compute_spot_count(self):
        for r in self:
            spots = r.spot_ids
            r.spot_count = len(spots)
            r.available_count = len(spots.filtered(lambda s: s.status == "available"))

    spot_ids = fields.One2many("parking.spot", "location_id", string="Spots")
