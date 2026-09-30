from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    parking_location_ids = fields.One2many("parking.location", "company_id", string="Parking Branches")

    # Accounting
    parking_deposit_account_id = fields.Many2one(
        "account.account", string="Customer Deposits Account",
        domain="[('account_type', 'in', ('liability_current', 'liability_non_current'))]",
        help="Refundable deposits are invoiced on this liability account instead of revenue.")
    parking_auto_post_invoices = fields.Boolean(
        string="Post Automatic Invoices",
        help="Post contract invoices as soon as they are generated instead of leaving them as drafts.")
    parking_analytic_plan_id = fields.Many2one(
        "account.analytic.plan", string="Branch Analytic Plan",
        help="Each branch gets an analytic account in this plan; parking invoice lines are "
             "distributed to the branch so its profitability can be measured.")
    parking_invoice_stock_moves = fields.Boolean(
        string="Move Stock on Invoicing",
        help="When a parking invoice is posted, storable products on it are delivered from the "
             "branch warehouse (a credit note brings them back), so stock and cost of goods stay right.")
    parking_use_deferred_revenue = fields.Boolean(
        string="Defer Multi-Month Revenue",
        help="Invoice lines covering several months carry their service period so revenue "
             "is recognised month by month (requires deferred revenue in Accounting settings).")

    # Car washes
    parking_wash_carry_over = fields.Boolean(
        string="Carry Over Unused Washes", default=True,
        help="On: washes left from a month stay in the balance. Off: unused monthly washes expire "
             "when the next month's washes are added (purchased washes never expire).")

    # Messaging
    parking_phone_country_code = fields.Char(
        string="Default Country Code", default="966",
        help="Used to turn local mobile numbers (05xxxxxxxx) into international format.")
    parking_sms_gateway_id = fields.Many2one(
        "parking.messaging.gateway", string="SMS Gateway", domain="[('channel', '=', 'sms')]")
    parking_whatsapp_gateway_id = fields.Many2one(
        "parking.messaging.gateway", string="WhatsApp Gateway", domain="[('channel', '=', 'whatsapp')]")
