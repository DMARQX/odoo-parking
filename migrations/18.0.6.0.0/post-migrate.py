import base64

from odoo import api, SUPERUSER_ID
from odoo.tools import file_open


def migrate(cr, version):
    """Link existing vehicles to the brand list by their typed brand ("bmw x5" -> BMW)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Brand = env["parking.vehicle.brand"]
    # Brand records are noupdate: give the shipped logo to brands that have none (never replace an upload).
    slugs = {"gac": "gac-group"}
    for xmlid in env["ir.model.data"].search([("module", "=", "parking_management"),
                                              ("model", "=", "parking.vehicle.brand")]):
        brand = Brand.browse(xmlid.res_id).exists()
        if not brand or brand.logo:
            continue
        name = xmlid.name[len("brand_"):]
        path = "parking_management/static/img/brands/%s.png" % slugs.get(name, name.replace("_", "-"))
        try:
            with file_open(path, "rb") as f:
                brand.logo = base64.b64encode(f.read())
        except FileNotFoundError:
            pass
    for vehicle in env["parking.vehicle"].with_context(active_test=False).search(
            [("brand_id", "=", False), ("brand", "!=", False)]):
        match = Brand._match(vehicle.brand)
        if match:
            # Keep the typed text as it was; only the link is added.
            vehicle.with_context(tracking_disable=True).write({"brand_id": match.id, "brand": vehicle.brand})
