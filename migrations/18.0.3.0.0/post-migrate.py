from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Give contracts and movements saved with the placeholder name a real number.

    Before 18.0.3.0.0 a contract created from an Arabic session kept the
    translated placeholder ("جديد") as its reference.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    contracts = env["parking.contract"].with_context(active_test=False).search(
        [("name", "in", ("New", "جديد", "/"))], order="create_date, id")
    for contract in contracts:
        contract.name = env["ir.sequence"].next_by_code("parking.contract") or contract.name

    # Same placeholder problem for vehicle movements created from the form.
    movements = env["parking.vehicle.movement"].search(
        [("name", "in", ("New", "جديد", "/"))], order="create_date, id")
    for movement in movements:
        movement.name = env["ir.sequence"].next_by_code("parking.vehicle.movement") or movement.name
