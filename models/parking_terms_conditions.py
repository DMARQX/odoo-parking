from odoo import models, fields, api, _


class ParkingTermsConditions(models.Model):
    _name = "parking.terms.conditions"
    _description = "Terms & Conditions Template"
    _rec_name = "name"
    _order = "sequence, id"

    name = fields.Char(string="Name", required=True, translate=True)
    content = fields.Html(string="Content", required=True, translate=True)
    active = fields.Boolean(string="Active", default=True)
    sequence = fields.Integer(string="Sequence", default=10)
    is_default = fields.Boolean(string="Use as Default")
    auto_sync = fields.Boolean(
        string="Auto Sync",
        default=True,
        help="When enabled, editing this template will automatically update all linked contracts",
    )
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)
    contract_ids = fields.One2many("parking.contract", "terms_id", string="Linked Contracts")
    contract_count = fields.Integer(string="Contract Count", compute="_compute_contract_count")

    @api.model
    def _get_default(self, company=None):
        """The default template of a company: its own first, then its parent's, then a shared one."""
        company = company or self.env.company
        companies = company | company.sudo().parent_ids
        templates = self.sudo().search([("is_default", "=", True), ("company_id", "in", companies.ids + [False])])
        ordered = templates.sorted(lambda t: (
            0 if t.company_id == company else 1 if t.company_id else 2, t.sequence, t.id))
        return ordered[:1].with_env(self.env)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered("is_default")._keep_single_default()
        return records

    def _keep_single_default(self):
        """One default per company: marking a template as default unmarks the previous one."""
        for record in self:
            (self.sudo().search([("is_default", "=", True), ("company_id", "=", record.company_id.id)]) - record
             ).write({"is_default": False})

    @api.depends("contract_ids")
    def _compute_contract_count(self):
        for r in self:
            r.contract_count = len(r.contract_ids)

    def write(self, vals):
        res = super().write(vals)
        if vals.get("is_default"):
            self[-1:]._keep_single_default()
        if "content" in vals:
            for record in self:
                if record.auto_sync and record.contract_ids:
                    record.contract_ids.write({"terms_conditions": record.content})
        return res

    def action_sync_contracts(self):
        self.ensure_one()
        self.contract_ids.write({"terms_conditions": self.content})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Contracts Updated"),
                "message": _("%(count)d contracts have been updated.", count=len(self.contract_ids)),
                "sticky": False,
                "type": "success",
            },
        }

    def action_open_contracts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Linked Contracts"),
            "res_model": "parking.contract",
            "domain": [("terms_id", "=", self.id)],
            "view_mode": "list,form",
            "context": dict(self.env.context, create=False),
        }
