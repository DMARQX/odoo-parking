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
