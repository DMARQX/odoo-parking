from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    parking_location_ids = fields.One2many("parking.location", "company_id", string="Parking Branches")