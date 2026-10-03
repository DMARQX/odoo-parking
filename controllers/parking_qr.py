from odoo import http
from odoo.exceptions import UserError
from odoo.http import request


class ParkingQrController(http.Controller):
    """QR codes on vehicle tags and spot labels open the attendant screen on that spot."""

    def _open(self, model, token):
        record = request.env[model].search([("qr_token", "=", token)], limit=1) if token else None
        if record:
            try:
                spot_id = record.id if model == "parking.spot" else request.env["parking.attendant"].resolve(
                    "/parking/v/%s" % token)
            except UserError:
                spot_id = False  # vehicle without an active contract: the screen opens on its board
            request.session["parking_scan"] = spot_id or False
        return request.redirect("/odoo/action-parking_management.action_parking_attendant")

    @http.route("/parking/v/<string:token>", type="http", auth="user")
    def vehicle_qr(self, token, **kw):
        return self._open("parking.vehicle", token)

    @http.route("/parking/s/<string:token>", type="http", auth="user")
    def spot_qr(self, token, **kw):
        return self._open("parking.spot", token)
