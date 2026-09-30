from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Write parking invoice texts in Arabic by default (changeable in Parking settings)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    arabic = env["res.lang"].search([("code", "in", ("ar_001", "ar_SA")), ("active", "=", True)],
                                    order="code", limit=1)
    if arabic:
        env["res.company"].search([("parking_invoice_lang", "=", False)]).write(
            {"parking_invoice_lang": arabic.code})
