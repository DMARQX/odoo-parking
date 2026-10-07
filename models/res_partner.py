from odoo import models, fields, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    parking_contract_count = fields.Integer(string="Parking Contracts", compute="_compute_parking_contract_count")

    def _compute_parking_contract_count(self):
        Contract = self.env["parking.contract"]
        for partner in self:
            partner.parking_contract_count = Contract.search_count(
                [("partner_id", "child_of", partner.commercial_partner_id.id)]) if partner.id else 0

    def _parking_contracts(self):
        self.ensure_one()
        return self.env["parking.contract"].sudo().search(
            [("partner_id", "child_of", self.commercial_partner_id.id)])

    def _get_parking_statement_data(self):
        """All parking contracts of the customer, plus payments not yet matched to an invoice."""
        self.ensure_one()
        contracts = self._parking_contracts()
        data = contracts._get_statement_data()
        unallocated = self.env["account.move.line"].sudo().search([
            ("partner_id", "child_of", self.commercial_partner_id.id),
            ("parent_state", "=", "posted"),
            ("account_id.account_type", "=", "asset_receivable"),
            ("amount_residual", "<", 0),
            ("move_id.move_type", "=", "entry"),
            ("company_id", "in", (contracts.company_id | self.env.company).ids),
        ])
        for line in unallocated:
            data["rows"].append({
                "date": line.date, "ref": line.move_id.name, "contract": "",
                "label": _("Payment not yet allocated to an invoice"),
                "debit": 0.0, "credit": -line.amount_residual, "due_date": False, "kind": "payment",
            })
        data["rows"].sort(key=lambda r: (r["date"] or fields.Date.today(), 0 if r["kind"] != "payment" else 1))
        balance = 0.0
        for row in data["rows"]:
            balance += row["debit"] - row["credit"]
            row["balance"] = balance
        data["paid"] += sum(-l.amount_residual for l in unallocated)
        data["balance"] = balance
        data["balance_with_drafts"] = balance + data["draft_total"]
        data["contracts"] = contracts
        return data

    def action_view_parking_contracts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Parking Contracts"),
            "res_model": "parking.contract",
            "view_mode": "list,kanban,form",
            "domain": [("partner_id", "child_of", self.commercial_partner_id.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_print_parking_statement(self):
        return self.env.ref("parking_management.action_report_parking_partner_statement").report_action(self)
