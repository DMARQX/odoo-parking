from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Contract totals changed meaning (rent, recurring and one-time services, period amount):
    stored values are recomputed for every contract, they do not refresh by themselves."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    contracts = env["parking.contract"].with_context(active_test=False).search([])
    for name in ("rent_amount", "recurring_services_total", "one_time_services_total",
                 "services_total", "amount_total"):
        env.add_to_compute(contracts._fields[name], contracts)
    contracts.flush_recordset()
