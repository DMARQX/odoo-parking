import secrets

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Give every existing vehicle and spot its own QR token (new records get one on creation)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model in ("parking.vehicle", "parking.spot"):
        for record in env[model].with_context(active_test=False).search([("qr_token", "=", False)]):
            record.qr_token = secrets.token_urlsafe(12)
