from odoo import models, fields, api, _


class ParkingTransferType(models.Model):
    _name = "parking.transfer.type"
    _description = "Transfer Type"
    _rec_name = "name"
    _order = "sequence, name"

    name = fields.Char(string="Type Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True)
    description = fields.Text(string="Description")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    _sql_constraints = [
        ("unique_code", "unique(code)", "Transfer type code must be unique!"),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = (vals.get("name", "") or "").upper().replace(" ", "_")
        return super().create(vals_list)
