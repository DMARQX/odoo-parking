from odoo import models, fields, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    parking_deposit_account_id = fields.Many2one(
        related="company_id.parking_deposit_account_id", readonly=False)
    parking_auto_post_invoices = fields.Boolean(
        related="company_id.parking_auto_post_invoices", readonly=False)
    parking_analytic_plan_id = fields.Many2one(
        related="company_id.parking_analytic_plan_id", readonly=False)
    parking_use_deferred_revenue = fields.Boolean(
        related="company_id.parking_use_deferred_revenue", readonly=False)
    parking_invoice_stock_moves = fields.Boolean(
        related="company_id.parking_invoice_stock_moves", readonly=False)
    parking_invoice_lang = fields.Selection(
        related="company_id.parking_invoice_lang", readonly=False)
    parking_use_deposit = fields.Boolean(
        related="company_id.parking_use_deposit", readonly=False)
    parking_prorate = fields.Boolean(
        related="company_id.parking_prorate", readonly=False)
    parking_stock_shortage = fields.Selection(
        related="company_id.parking_stock_shortage", readonly=False)
    parking_wash_interval_days = fields.Integer(
        related="company_id.parking_wash_interval_days", readonly=False)
    parking_wash_consume_stock = fields.Boolean(
        related="company_id.parking_wash_consume_stock", readonly=False)
    parking_wash_location_id = fields.Many2one(
        related="company_id.parking_wash_location_id", readonly=False)
    parking_wash_carry_over = fields.Boolean(
        related="company_id.parking_wash_carry_over", readonly=False)
    parking_phone_country_code = fields.Char(
        related="company_id.parking_phone_country_code", readonly=False)
    parking_sms_gateway_id = fields.Many2one(
        related="company_id.parking_sms_gateway_id", readonly=False)
    parking_whatsapp_gateway_id = fields.Many2one(
        related="company_id.parking_whatsapp_gateway_id", readonly=False)

    def action_parking_create_branch_analytics(self):
        self.ensure_one()
        created = self.env["parking.location"].search(
            [("company_id", "=", self.company_id.id)])._ensure_analytic_account()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success" if created else "info",
                "message": _("%(count)s branch analytic account(s) created.", count=len(created)),
                "sticky": False,
            },
        }

    def action_parking_apply_wash_interval(self):
        """Give the default interval to the company's current contracts (draft, confirmed, active)."""
        self.ensure_one()
        contracts = self.env["parking.contract"].search([
            ("company_id", "=", self.company_id.id), ("state", "in", ("draft", "confirmed", "active"))])
        contracts.write({"wash_interval_days": self.parking_wash_interval_days})
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"type": "success", "message": _(
                "%(count)s contract(s) now allow a wash every %(days)s day(s).",
                count=len(contracts), days=self.parking_wash_interval_days)},
        }
