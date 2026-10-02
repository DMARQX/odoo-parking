from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Deposits become an option, contracts follow their branch's company.

    The deposit option is switched on only where a deposits account is set: without one a
    deposit would be booked as revenue, which is now refused.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Contract = env["parking.contract"].with_context(active_test=False)
    for company in env["res.company"].search([("parking_deposit_account_id", "!=", False)]):
        if Contract.search_count([("company_id", "=", company.id), ("deposit_amount", ">", 0)]):
            company.parking_use_deposit = True
    # Contracts without invoices move to their branch's company (invoiced ones keep their books).
    for contract in Contract.search([]):
        branch_company = contract.location_id.company_id
        if branch_company and contract.company_id != branch_company and not contract.invoice_ids.filtered(
                lambda m: m.state != "cancel"):
            contract.company_id = branch_company
