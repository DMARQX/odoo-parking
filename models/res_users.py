from odoo import models, fields


class ResUsers(models.Model):
    _inherit = "res.users"

    parking_location_ids = fields.Many2many(
        "parking.location",
        string="Allowed Parking Branches",
        help="Parking branches this user is allowed to see and operate. "
             "Leave empty to grant access to all branches.",
    )

    def write(self, vals):
        res = super().write(vals)
        if "parking_location_ids" in vals:
            # Branch record rules read this field; drop cached rule domains
            # so a new branch assignment applies without a server restart.
            self.env.registry.clear_cache()
        return res
