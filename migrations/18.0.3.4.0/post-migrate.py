from odoo import api, SUPERUSER_ID

ONE_TIME_CATEGORIES = ("cover", "safety")


def migrate(cr, version):
    """Start the wash balance and split services into subscription add-ons and one-time sales.

    Before 18.0.3.4.0 every contract service line was billed on every invoice and remaining
    washes were "free washes - washes done". Goods (covers, safety items) become one-time
    sales; everything else keeps being billed with each invoice, so current billing is unchanged.
    One-time lines already billed are linked to the invoice that billed them so they are not
    billed again. An opening credit equal to the old free washes keeps remaining washes unchanged.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Service = env["parking.service"].with_context(active_test=False)
    Service.search([("category", "in", ONE_TIME_CATEGORIES)]).write({"billing_type": "one_time"})
    Service.search([("category", "not in", ONE_TIME_CATEGORIES)]).write({"billing_type": "recurring"})

    lines = env["parking.contract.service.line"].search([])
    for line in lines:
        line.billing_type = line.service_id.billing_type
        if line.billing_type != "one_time" or line.invoice_id:
            continue
        invoices = env["account.move"].search([
            ("parking_contract_id", "=", line.contract_id.id),
            ("move_type", "=", "out_invoice"), ("state", "=", "posted")], order="invoice_date, id")
        product = line.service_id.product_id
        for inv in invoices:
            if any((product and l.product_id == product) or l.name == line.service_id.name
                   for l in inv.invoice_line_ids):
                line.invoice_id = inv
                break

    Credit = env["parking.wash.credit"]
    for contract in env["parking.contract"].with_context(active_test=False).search(
            [("free_wash_count", ">", 0), ("wash_credit_ids", "=", False)]):
        Credit.create({
            "contract_id": contract.id,
            "quantity": contract.free_wash_count,
            "kind": "opening",
            "date": contract.start_date or contract.create_date.date(),
            "note": "Balance before the wash ledger",
        })
