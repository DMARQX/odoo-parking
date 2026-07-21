from odoo import api, fields, models


class ParkingReportWizard(models.TransientModel):
    _name = "parking.report.wizard"
    _description = "Parking Detailed Report Wizard"

    branch_id = fields.Many2one("parking.location", string="Branch")
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    contract_status = fields.Selection(
        [("all", "All"), ("active", "Active"), ("expired", "Expired"), ("near_expiry", "Near Expiration")],
        string="Contract Status",
        default="all",
    )
    include_spots = fields.Boolean(string="Spots Summary", default=True)
    include_contracts = fields.Boolean(string="Contracts Summary", default=True)
    include_vehicles = fields.Boolean(string="Vehicles Registry", default=True)
    include_services = fields.Boolean(string="Additional Services", default=True)

    def _get_contract_domain(self):
        domain = []
        if self.branch_id:
            domain.append(("location_id", "=", self.branch_id.id))
        if self.contract_status == "active":
            domain.append(("state", "=", "active"))
        elif self.contract_status == "expired":
            domain.append(("state", "=", "expired"))
        elif self.contract_status == "near_expiry":
            domain.append(("state", "=", "active"))
            domain.append(("end_date", "<=", fields.Date.add(fields.Date.today(), days=30)))
            domain.append(("end_date", ">=", fields.Date.today()))
        if self.date_from:
            domain.append(("start_date", ">=", self.date_from))
        if self.date_to:
            domain.append(("start_date", "<=", self.date_to))
        return domain

    def _get_spot_domain(self):
        domain = []
        if self.branch_id:
            domain.append(("location_id", "=", self.branch_id.id))
        return domain

    def _get_vehicle_domain(self):
        domain = []
        if self.branch_id:
            contracts = self.env["parking.contract"].search([("location_id", "=", self.branch_id.id)])
            domain.append(("contract_ids", "in", contracts.ids))
        return domain

    def _get_service_domain(self):
        domain = self._get_contract_domain()
        domain.append(("service_line_ids", "!=", False))
        return domain

    def action_print_comprehensive_report(self):
        return self.env.ref("parking_management.action_report_parking_comprehensive").report_action(self)

    def _is_arabic_context(self):
        return (self.env.context.get('lang') or self.env.user.lang or '').startswith('ar')

    def _get_report_data(self):
        spots = self.env["parking.spot"].search(self._get_spot_domain())
        contracts = self.env["parking.contract"].search(self._get_contract_domain())
        vehicles = self.env["parking.vehicle"].search(self._get_vehicle_domain())
        services_contracts = self.env["parking.contract"].search(self._get_service_domain())
        today = fields.Date.today()

        return {
            "branch_name": self.branch_id.display_name or "All Branches",
            "date_from": self.date_from,
            "date_to": self.date_to,
            "contract_status": dict(self._fields["contract_status"].selection).get(self.contract_status, "All"),
            "include_spots": self.include_spots,
            "include_contracts": self.include_contracts,
            "include_vehicles": self.include_vehicles,
            "include_services": self.include_services,
            "spots": spots,
            "contracts": contracts,
            "vehicles": vehicles,
            "services_contracts": services_contracts,
            "available_count": len(spots.filtered(lambda s: s.status == "available")),
            "reserved_count": len(spots.filtered(lambda s: s.status == "reserved")),
            "occupied_count": len(spots.filtered(lambda s: s.status == "occupied")),
            "active_count": len(contracts.filtered(lambda c: c.state == "active")),
            "expired_count": len(contracts.filtered(lambda c: c.state == "expired")),
            "near_expiry_count": len(
                contracts.filtered(
                    lambda c: c.state == "active" and c.end_date
                    and 0 <= (c.end_date - today).days <= 30
                )
            ),
            "total_amount": sum(contracts.mapped("amount_total")),
            "total_vehicles": len(vehicles),
        }
