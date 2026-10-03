import re

from odoo import api, fields, models


def _normalize(text):
    """Lowercase letters and digits only, Arabic kept: "Mercedes-Benz" -> "mercedesbenz"."""
    return re.sub(r"[\W_]+", "", (text or "").strip().lower())


class ParkingVehicleBrand(models.Model):
    _name = "parking.vehicle.brand"
    _description = "Vehicle Brand"
    _order = "sequence, name"

    name = fields.Char(string="Brand", required=True)
    name_ar = fields.Char(string="Arabic Name")
    aliases = fields.Char(string="Other Spellings",
        help="Comma-separated spellings matched when a brand is typed, e.g. \"bmw, بي ام, بي ام دبليو\".")
    logo = fields.Image(string="Logo", max_width=256, max_height=256)
    color = fields.Char(string="Badge Colour", default="#334155",
        help="Background of the initials badge shown while the brand has no logo.")
    initials = fields.Char(compute="_compute_initials")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    vehicle_count = fields.Integer(compute="_compute_vehicle_count", string="Vehicles")

    _sql_constraints = [("name_unique", "unique(name)", "This brand already exists.")]

    @api.depends("name")
    def _compute_initials(self):
        for brand in self:
            words = [w for w in re.split(r"[\s\-]+", brand.name or "") if w]
            if len(words) > 1:
                brand.initials = (words[0][0] + words[1][0]).upper()
            else:
                brand.initials = (brand.name or "?")[:3].upper()

    def _compute_vehicle_count(self):
        counts = dict(self.env["parking.vehicle"]._read_group(
            [("brand_id", "in", self.ids)], ["brand_id"], ["__count"]))
        for brand in self:
            brand.vehicle_count = counts.get(brand, 0)

    @api.depends("name", "name_ar")
    def _compute_display_name(self):
        for brand in self:
            brand.display_name = brand.name if not brand.name_ar else "%s - %s" % (brand.name, brand.name_ar)

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=None, order=None):
        if name and operator in ("ilike", "like", "=ilike", "=like", "="):
            domain = ["&", *(domain or []), "|", "|", ("name", operator, name),
                      ("name_ar", operator, name), ("aliases", operator, name)]
            return self._search(domain, limit=limit, order=order)
        return super()._name_search(name, domain=domain, operator=operator, limit=limit, order=order)

    @api.model
    def _match(self, text):
        """Brand for a typed text: exact name, Arabic name or alias, ignoring case and spacing;
        else a known spelling at the start ("bmw x5" -> BMW)."""
        key = _normalize(text)
        if not key:
            return self.browse()
        brands = self.with_context(active_test=False).search([])
        for brand in brands:
            spellings = [brand.name, brand.name_ar] + (brand.aliases or "").split(",")
            if key in {_normalize(s) for s in spellings if s}:
                return brand
        best = self.browse()
        best_len = 0
        for brand in brands:
            spellings = [brand.name, brand.name_ar] + (brand.aliases or "").split(",")
            for s in spellings:
                n = _normalize(s)
                if len(n) >= 3 and key.startswith(n) and len(n) > best_len:
                    best, best_len = brand, len(n)
        return best

    def action_view_vehicles(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "parking.vehicle",
            "view_mode": "list,form",
            "domain": [("brand_id", "=", self.id)],
            "context": {"default_brand_id": self.id},
        }
