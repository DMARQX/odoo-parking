from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """0 used to mean "4 days" (hard-coded); it now means "no minimum". Contracts at 0 keep their
    previous behaviour by getting the company default (4 days unless changed in settings)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env["res.company"].search([]):
        if not company.parking_wash_interval_days:
            company.parking_wash_interval_days = 4
        env["parking.contract"].with_context(active_test=False).search([
            ("company_id", "=", company.id), ("wash_interval_days", "=", 0),
        ]).write({"wash_interval_days": company.parking_wash_interval_days})
