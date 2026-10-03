from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Link existing vehicles to the brand list by their typed brand ("bmw x5" -> BMW)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Brand = env["parking.vehicle.brand"]
    for vehicle in env["parking.vehicle"].with_context(active_test=False).search(
            [("brand_id", "=", False), ("brand", "!=", False)]):
        match = Brand._match(vehicle.brand)
        if match:
            # Keep the typed text as it was; only the link is added.
            vehicle.with_context(tracking_disable=True).write({"brand_id": match.id, "brand": vehicle.brand})
