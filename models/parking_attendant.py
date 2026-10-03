import re
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.http import request


def new_qr_token():
    return secrets.token_urlsafe(12)


class ParkingQrMixin(models.AbstractModel):
    """A random token per record, printed as a QR code that opens the attendant screen."""
    _name = "parking.qr.mixin"
    _description = "Parking QR Code"
    _qr_prefix = "x"

    qr_token = fields.Char(string="QR Token", copy=False, readonly=True, index=True)
    qr_url = fields.Char(string="QR Link", compute="_compute_qr_url")

    def _compute_qr_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for r in self:
            r.qr_url = "%s/parking/%s/%s" % (base, self._qr_prefix, r.qr_token) if r.qr_token else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("qr_token", new_qr_token())
        return super().create(vals_list)

    def action_reset_qr(self):
        """A new code: printed labels of the old one stop working (lost or copied tag)."""
        for r in self:
            r.qr_token = new_qr_token()


class ParkingVehicleQr(models.Model):
    _name = "parking.vehicle"
    _inherit = ["parking.vehicle", "parking.qr.mixin"]
    _qr_prefix = "v"


class ParkingSpotQr(models.Model):
    _name = "parking.spot"
    _inherit = ["parking.spot", "parking.qr.mixin"]
    _qr_prefix = "s"


class ParkingAttendant(models.AbstractModel):
    """Data and actions of the attendant's mobile screen."""
    _name = "parking.attendant"
    _description = "Parking Attendant Screen"

    _BOARD_STATES = ("client_out", "occupied", "reserved")

    @api.model
    def get_board(self, search=""):
        Spot = self.env["parking.spot"]
        domain = [("status", "in", self._BOARD_STATES)]
        spots = Spot.search(domain, order="location_id, sequence, name")
        items = [self._spot_item(s) for s in spots]
        term = (search or "").strip().lower()
        if term:
            items = [i for i in items if term in " ".join(
                str(i.get(k) or "") for k in ("plate", "spot", "customer", "brand", "model", "mobile")).lower()]
        board = {state: [i for i in items if i["status"] == state] for state in self._BOARD_STATES}
        board["client_out"].sort(key=lambda i: -(i["waiting_hours"] or 0))
        return {"board": board, "can_operate": self.env.user.has_group("parking_management.group_parking_checkinout")}

    @api.model
    def get_spot(self, spot_id):
        spot = self.env["parking.spot"].browse(int(spot_id)).exists()
        if not spot:
            raise UserError(_("This spot no longer exists."))
        return self._spot_item(spot)

    def _spot_item(self, spot):
        vehicle = spot.current_vehicle_id
        brand = vehicle.brand_id
        contract = spot.current_contract_id
        key_status = dict(vehicle._fields["key_status"]._description_selection(self.env)).get(vehicle.key_status) \
            if vehicle else False
        return {
            "spot_id": spot.id,
            "spot": spot.name,
            "branch": spot.location_id.name,
            "floor": spot.floor or "",
            "status": spot.status,
            "status_label": dict(spot._fields["status"]._description_selection(self.env)).get(spot.status),
            "vehicle_id": vehicle.id or False,
            "plate": vehicle.license_plate or "",
            "brand": brand.name or vehicle.brand or "",
            "model": vehicle.model or "",
            "color": vehicle.color or "",
            "logo": "/web/image/parking.vehicle.brand/%s/logo/96x96" % brand.id if brand.logo else False,
            "initials": brand.initials or (vehicle.brand or "")[:2].upper(),
            "brand_color": brand.color or "#64748b",
            "customer": contract.partner_id.display_name or "",
            "mobile": contract.partner_id.mobile or contract.partner_id.phone or "",
            "contract": contract.name or "",
            "contract_id": contract.id or False,
            "days_left": spot.current_days_left if contract else False,
            "key_tag": vehicle.key_tag or "",
            "key_slot": vehicle.key_slot or "",
            "key_status": key_status or "",
            "waiting_label": spot.waiting_label or "",
            "waiting_hours": spot.waiting_hours or 0,
            "remaining_washes": contract.remaining_washes if contract else 0,
        }

    @api.model
    def resolve(self, code):
        """Spot for a scanned or typed code: a QR link, a QR token, a plate or a spot number."""
        code = (code or "").strip()
        if not code:
            return False
        match = re.search(r"/parking/([vs])/([\w-]+)", code)
        kind, token = (match.group(1), match.group(2)) if match else (None, code)
        Vehicle, Spot = self.env["parking.vehicle"], self.env["parking.spot"]
        if kind in (None, "s"):
            spot = Spot.search([("qr_token", "=", token)], limit=1)
            if spot:
                return spot.id
        if kind in (None, "v"):
            vehicle = Vehicle.search([("qr_token", "=", token)], limit=1)
            if vehicle:
                return self._spot_of_vehicle(vehicle)
        if not match:
            norm = re.sub(r"\s+", "", code).lower()
            vehicle = Vehicle.search([("license_plate", "=ilike", code)], limit=1) or Vehicle.search([]).filtered(
                lambda v: re.sub(r"\s+", "", v.license_plate or "").lower() == norm)[:1]
            if vehicle:
                return self._spot_of_vehicle(vehicle)
            spot = Spot.search([("name", "=ilike", code)], limit=1)
            if spot:
                return spot.id
        return False

    def _spot_of_vehicle(self, vehicle):
        contract = vehicle.contract_ids.filtered(lambda c: c.state in ("active", "confirmed"))[:1]
        if not contract.spot_id:
            raise UserError(_("Vehicle %s has no active contract with a spot.", vehicle.display_name))
        return contract.spot_id.id

    @api.model
    def pop_scan(self):
        """Spot opened from a QR link (the link stores it in the session before opening this screen)."""
        if not request:
            return False
        target = request.session.pop("parking_scan", False)
        return target or False

    @api.model
    def run(self, spot_id, operation):
        return self._client_action(self._run(spot_id, operation))

    @staticmethod
    def _client_action(action):
        """Actions returned to the screen by a direct call need their views list (buttons get it from the server)."""
        if isinstance(action, dict) and action.get("type") == "ir.actions.act_window" and not action.get("views"):
            action = dict(action, views=[(False, mode) for mode in (action.get("view_mode") or "form").split(",")])
        return action

    def _run(self, spot_id, operation):
        spot = self.env["parking.spot"].browse(int(spot_id)).exists()
        if not spot:
            raise UserError(_("This spot no longer exists."))
        if operation == "deliver":
            return spot.action_vehicle_checkout()
        if operation == "receive":
            return spot.action_vehicle_checkin()
        if operation == "wash":
            if not spot.current_vehicle_id:
                raise UserError(_("No vehicle on spot %s.", spot.name))
            return spot.current_vehicle_id.action_register_wash()
        if operation == "open":
            return {"type": "ir.actions.act_window", "res_model": "parking.spot", "res_id": spot.id,
                    "view_mode": "form", "views": [(False, "form")]}
        raise UserError(_("Unknown operation."))

    @api.model
    def new_reception(self):
        return self._client_action(
            self.env["ir.actions.act_window"]._for_xml_id("parking_management.action_parking_reception_wizard"))
