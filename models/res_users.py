from odoo import models, fields


class ResUsers(models.Model):
    _inherit = "res.users"

    parking_location_ids = fields.Many2many(
        "parking.location",
        string="Allowed Parking Branches",
        help="Parking branches this user is allowed to see and operate. "
             "Leave empty to grant access to all branches.",
    )