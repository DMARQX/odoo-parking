from odoo import http, _
from odoo.http import request


class ParkingPortal(http.Controller):

    def _get_contracts_domain(self):
        user = request.env.user
        if user.has_group("base.group_portal"):
            return [("partner_id", "child_of", user.partner_id.commercial_partner_id.id)]
        return []

    @http.route("/my/contracts", type="http", auth="user", website=True)
    def portal_contracts(self, **kw):
        contracts = request.env["parking.contract"].search(self._get_contracts_domain())
        values = {
            "contracts": contracts,
            "page_name": "contracts",
        }
        return request.render("parking_management.portal_contracts_page", values)

    @http.route("/my/contract/<int:contract_id>", type="http", auth="user", website=True)
    def portal_contract_detail(self, contract_id, **kw):
        contract = request.env["parking.contract"].browse(contract_id)
        if not contract.exists():
            return request.not_found()
        if not request.env.user.has_group("base.group_system"):
            user_partner = request.env.user.partner_id.commercial_partner_id
            if contract.partner_id.commercial_partner_id != user_partner:
                return request.not_found()
        values = {
            "contract": contract,
            "page_name": "contract",
        }
        return request.render("parking_management.portal_contract_detail", values)

    @http.route("/my/vehicles", type="http", auth="user", website=True)
    def portal_vehicles(self, **kw):
        user = request.env.user
        domain = []
        if user.has_group("base.group_portal"):
            domain = [("owner_id", "child_of", user.partner_id.commercial_partner_id.id)]
        vehicles = request.env["parking.vehicle"].search(domain)
        values = {
            "vehicles": vehicles,
            "page_name": "vehicles",
        }
        return request.render("parking_management.portal_vehicles_page", values)

    @http.route("/my/vehicle/<int:vehicle_id>", type="http", auth="user", website=True)
    def portal_vehicle_detail(self, vehicle_id, **kw):
        vehicle = request.env["parking.vehicle"].browse(vehicle_id)
        if not vehicle.exists():
            return request.not_found()
        if not request.env.user.has_group("base.group_system"):
            user_partner = request.env.user.partner_id.commercial_partner_id
            if vehicle.owner_id.commercial_partner_id != user_partner:
                return request.not_found()
        values = {
            "vehicle": vehicle,
            "page_name": "vehicle",
        }
        return request.render("parking_management.portal_vehicle_detail", values)
