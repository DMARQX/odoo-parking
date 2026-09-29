from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ParkingLocation(models.Model):
    _name = "parking.location"
    _description = "Parking Branch / Location"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "code, name"

    name = fields.Char(string="Branch Name", required=True, tracking=True)
    code = fields.Char(string="Branch Code", required=True, copy=False)
    city = fields.Char(string="City", required=True)
    address = fields.Text(string="Address")
    phone = fields.Char(string="Phone")
    manager_id = fields.Many2one("res.users", string="Branch Manager", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    spot_count = fields.Integer(string="Total Spots", compute="_compute_spot_count")
    available_count = fields.Integer(string="Available Spots", compute="_compute_spot_count")
    display_name = fields.Char(string="Display", compute="_compute_display_name", store=True)
    warehouse_id = fields.Many2one(
        "stock.warehouse", string="Warehouse", domain="[('company_id', '=', company_id)]",
        help="Storable products invoiced to this branch's customers leave from this warehouse.")
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Analytic Account", copy=False,
        help="Revenue of this branch is distributed to this analytic account on invoices.")

    _sql_constraints = [
        ("code_unique", "unique(code)", "Branch Code must be unique across all branches!"),
    ]

    @api.constrains("code")
    def _check_code(self):
        for r in self:
            if not r.code or not r.code.strip():
                raise UserError(_("Branch Code cannot be empty."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_analytic_account()
        return records

    def _ensure_analytic_account(self):
        """Give each branch an analytic account in the company's branch plan."""
        created = self.env["account.analytic.account"]
        for branch in self.filtered(lambda b: not b.analytic_account_id):
            plan = branch.company_id.parking_analytic_plan_id
            if not plan:
                continue
            account = self.env["account.analytic.account"].sudo().create({
                "name": branch.name,
                "code": branch.code,
                "plan_id": plan.id,
                "company_id": branch.company_id.id,
            })
            branch.sudo().analytic_account_id = account
            created |= account
        return created

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
