from datetime import timedelta
from odoo import models, fields, api


class ParkingDashboard(models.TransientModel):
    _name = "parking.dashboard"
    _description = "Parking Dashboard"

    total_spots = fields.Integer(string="Total Spots")
    available_spots = fields.Integer(string="Available Spots")
    occupied_spots = fields.Integer(string="Occupied Spots")
    reserved_spots = fields.Integer(string="Reserved Spots")
    client_out_spots = fields.Integer(string="Client Out Spots")
    maintenance_spots = fields.Integer(string="Maintenance Spots")

    total_contracts = fields.Integer(string="Total Contracts")
    active_contracts = fields.Integer(string="Active Contracts")
    expired_contracts = fields.Integer(string="Expired Contracts")
    draft_contracts = fields.Integer(string="Draft Contracts")
    near_expiry_contracts = fields.Integer(string="Near Expiry")

    total_vehicles = fields.Integer(string="Total Vehicles")
    total_customers = fields.Integer(string="Total Customers")
    total_revenue = fields.Float(string="Total Revenue")
    monthly_revenue = fields.Float(string="This Month Revenue")
    monthly_new_contracts = fields.Integer(string="New Contracts This Month")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        stats = self._compute_stats()
        res.update(stats)
        return res

    @api.model
    def create(self, vals):
        record = super().create(vals)
        stats = record._compute_stats()
        record.write(stats)
        return record

    def compute(self):
        stats = self._compute_stats()
        self.write(stats)
        return {
            "type": "ir.actions.act_window",
            "res_model": "parking.dashboard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "main",
        }

    def _compute_stats(self):
        today = fields.Date.today()
        first_of_month = today.replace(day=1)
        Spot = self.env["parking.spot"]
        Contract = self.env["parking.contract"]
        Vehicle = self.env["parking.vehicle"]

        return {
            "total_spots": Spot.search_count([]),
            "available_spots": Spot.search_count([("status", "=", "available")]),
            "occupied_spots": Spot.search_count([("status", "=", "occupied")]),
            "reserved_spots": Spot.search_count([("status", "=", "reserved")]),
            "client_out_spots": Spot.search_count([("status", "=", "client_out")]),
            "maintenance_spots": Spot.search_count([("status", "=", "maintenance")]),
            "total_contracts": Contract.search_count([]),
            "active_contracts": Contract.search_count([("state", "=", "active")]),
            "expired_contracts": Contract.search_count([("state", "=", "expired")]),
            "draft_contracts": Contract.search_count([("state", "=", "draft")]),
            "near_expiry_contracts": Contract.search_count([
                ("state", "=", "active"),
                ("end_date", ">=", str(today)),
                ("end_date", "<=", str(today + timedelta(days=7))),
            ]),
            "total_vehicles": Vehicle.search_count([]),
            "total_customers": self.env["res.partner"].search_count([("customer_rank", ">", 0)]),
            "total_revenue": sum(Contract.search([]).mapped("amount_total")),
            "monthly_new_contracts": len(Contract.search([
                ("create_date", ">=", fields.Datetime.to_string(first_of_month))
            ])),
            "monthly_revenue": sum(Contract.search([
                ("create_date", ">=", fields.Datetime.to_string(first_of_month))
            ]).mapped("amount_total")),
        }
