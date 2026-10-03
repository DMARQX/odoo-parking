from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _


PERIODS = ("today", "week", "month", "quarter", "year")


class ParkingDashboard(models.TransientModel):
    _name = "parking.dashboard"
    _description = "Parking Dashboard"

    # ------------------------------------------------------------------
    # Data for the interactive dashboard (client action parking_dashboard)
    # ------------------------------------------------------------------
    @api.model
    def _period_start(self, period, today):
        if period == "today":
            return today
        if period == "week":
            return today - timedelta(days=today.weekday())
        if period == "quarter":
            return today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
        if period == "year":
            return today.replace(month=1, day=1)
        return today.replace(day=1)

    @api.model
    def _allowed_locations(self):
        user = self.env.user
        Location = self.env["parking.location"]
        if user.has_group("parking_management.group_parking_branch_user") and user.parking_location_ids:
            return user.parking_location_ids
        return Location.search([])

    @api.model
    def _low_stock_orderpoints(self, locations):
        """Reordering rules of the branch warehouses whose forecast is under the minimum."""
        if not self.env.user.has_group("stock.group_stock_user"):
            return []
        warehouses = locations.mapped("warehouse_id")
        if not warehouses:
            return []
        points = self.env["stock.warehouse.orderpoint"].search([("warehouse_id", "in", warehouses.ids)])
        return points.filtered(lambda p: p.qty_forecast < p.product_min_qty).ids

    @api.model
    def get_dashboard_data(self, location_id=False, period="month"):
        period = period if period in PERIODS else "month"
        today = fields.Date.context_today(self)
        date_from = self._period_start(period, today)
        dt_from = fields.Datetime.to_datetime(date_from)
        user = self.env.user
        can_invoice = user.has_group("parking_management.group_parking_invoicing")

        locations = self._allowed_locations()
        if location_id and location_id in locations.ids:
            locations = locations.browse(location_id)
        loc_ids = locations.ids
        loc_dom = [("location_id", "in", loc_ids)]

        Spot = self.env["parking.spot"]
        Contract = self.env["parking.contract"]
        Movement = self.env["parking.vehicle.movement"]
        Wash = self.env["parking.contract.wash"]

        # --- spots
        status_counts = dict(Spot._read_group(loc_dom, ["status"], ["__count"]))
        total_spots = sum(status_counts.values())
        in_service = total_spots - status_counts.get("maintenance", 0)
        busy = sum(status_counts.get(s, 0) for s in ("occupied", "client_out", "reserved"))
        occupancy = round(100.0 * busy / in_service, 1) if in_service else 0.0

        # --- contracts
        c_states = dict(Contract._read_group(loc_dom, ["state"], ["__count"]))
        expiring_7 = Contract.search_count(loc_dom + [("is_expiring_soon", "=", True)])
        past_end = Contract.search_count(loc_dom + [("state", "in", ("active", "confirmed")), ("end_date", "<", today)])
        new_contracts = Contract.search_count(loc_dom + [("create_date", ">=", dt_from)])

        # --- movements & washes
        start_today = fields.Datetime.to_datetime(today)
        out_today = Movement.search_count(loc_dom + [("check_out_time", ">=", start_today)])
        in_today = Movement.search_count(loc_dom + [("check_in_time", ">=", start_today)])
        moves_period = Movement.search(loc_dom + [("check_out_time", ">=", dt_from)])
        closed = moves_period.filtered("check_in_time")
        avg_hours = round(sum(closed.mapped("duration_hours")) / len(closed), 1) if closed else 0.0
        washes_period = Wash.search_count(loc_dom + [("state", "=", "done"), ("wash_date", ">=", dt_from)])
        low_stock_ids = self._low_stock_orderpoints(locations)
        low_stock = len(low_stock_ids)

        kpis = {
            "total_spots": total_spots,
            "available": status_counts.get("available", 0),
            "occupied": status_counts.get("occupied", 0),
            "client_out": status_counts.get("client_out", 0),
            "reserved": status_counts.get("reserved", 0),
            "maintenance": status_counts.get("maintenance", 0),
            "occupancy": occupancy,
            "active_contracts": c_states.get("active", 0),
            "confirmed_contracts": c_states.get("confirmed", 0),
            "draft_contracts": c_states.get("draft", 0),
            "expiring_7": expiring_7,
            "past_end": past_end,
            "new_contracts": new_contracts,
            "out_today": out_today,
            "in_today": in_today,
            "avg_hours_out": avg_hours,
            "washes": washes_period,
            "low_stock": low_stock,
            "low_stock_ids": low_stock_ids,
        }

        charts = {
            "spot_status": [
                {"key": key, "label": label, "value": status_counts.get(key, 0)}
                for key, label in Spot._fields["status"]._description_selection(self.env)
            ],
            "branches": self._branch_occupancy(locations),
            "movements": self._movements_by_day(loc_dom, today),
            "contracts_by_month": self._contracts_by_month(loc_dom, today),
        }

        lists = {
            "expiring": [{
                "id": c.id, "name": c.name, "partner": c.partner_id.display_name,
                "spot": c.spot_id.display_name, "end_date": fields.Date.to_string(c.end_date),
                "days": c.days_remaining, "state": c.state,
            } for c in Contract.search(loc_dom + [
                ("state", "in", ("active", "confirmed")),
                ("end_date", "<=", today + timedelta(days=30)),
            ], order="end_date asc", limit=8)],
            "waiting": [{
                "id": s.id, "spot": s.display_name, "plate": s.current_vehicle_plate or "",
                "owner": s.current_owner_id.display_name or "", "hours": round(s.waiting_hours, 1),
            } for s in Spot.search(loc_dom + [("status", "=", "client_out")]).sorted(
                "waiting_hours", reverse=True)[:8]],
            "recent_moves": [{
                "id": m.id, "name": m.name, "vehicle": m.vehicle_id.display_name,
                "spot": m.spot_id.display_name or "", "out": fields.Datetime.to_string(m.check_out_time) if m.check_out_time else "",
                "in": fields.Datetime.to_string(m.check_in_time) if m.check_in_time else "",
                "open": not m.check_in_time,
            } for m in Movement.search(loc_dom, order="write_date desc", limit=8)],
        }

        finance = {}
        if can_invoice:
            finance = self._finance_data(loc_ids, dt_from, date_from, today)
            charts["revenue"] = self._revenue_by_month(loc_ids, today)
            lists["debtors"] = finance.pop("debtors")

        return {
            "period": period,
            "date_from": fields.Date.to_string(date_from),
            "today": fields.Date.to_string(today),
            "location_id": location_id if location_id in loc_ids else False,
            "location_ids": loc_ids,
            "locations": [{"id": l.id, "name": l.display_name} for l in self._allowed_locations()],
            "currency_id": self.env.company.currency_id.id,
            "rights": {
                "invoice": can_invoice,
                "checkinout": user.has_group("parking_management.group_parking_checkinout"),
                "contract": user.has_group("parking_management.group_parking_contract"),
                "manager": user.has_group("parking_management.group_parking_manager"),
            },
            "kpis": kpis,
            "finance": finance,
            "charts": charts,
            "lists": lists,
        }

    @api.model
    def _branch_occupancy(self, locations):
        rows = self.env["parking.spot"]._read_group(
            [("location_id", "in", locations.ids)], ["location_id", "status"], ["__count"])
        data = {}
        for loc, status, count in rows:
            data.setdefault(loc.id, {"id": loc.id, "name": loc.name})[status] = count
        return sorted(data.values(), key=lambda d: d["name"] or "")

    @api.model
    def _movements_by_day(self, loc_dom, today):
        start = today - timedelta(days=13)
        days = [start + timedelta(days=i) for i in range(14)]
        Movement = self.env["parking.vehicle.movement"]
        outs = dict(Movement._read_group(
            loc_dom + [("check_out_time", ">=", fields.Datetime.to_datetime(start))],
            ["check_out_time:day"], ["__count"]))
        ins = dict(Movement._read_group(
            loc_dom + [("check_in_time", ">=", fields.Datetime.to_datetime(start))],
            ["check_in_time:day"], ["__count"]))

        def at(mapping, day):
            # Datetime groups come back as datetimes, date groups as dates.
            return sum(v for k, v in mapping.items()
                       if k and (k.date() if isinstance(k, datetime) else k) == day)

        return {
            "labels": [fields.Date.to_string(d) for d in days],
            "out": [at(outs, d) for d in days],
            "in": [at(ins, d) for d in days],
        }

    @api.model
    def _contracts_by_month(self, loc_dom, today):
        start = (today - relativedelta(months=11)).replace(day=1)
        rows = dict(self.env["parking.contract"]._read_group(
            loc_dom + [("start_date", ">=", start)], ["start_date:month"], ["__count"]))
        months = [start + relativedelta(months=i) for i in range(12)]
        return {
            "labels": [m.strftime("%Y-%m") for m in months],
            "values": [sum(v for k, v in rows.items() if k and (k.year, k.month) == (m.year, m.month)) for m in months],
        }

    @api.model
    def _invoice_domain(self, loc_ids):
        return [("parking_contract_id", "!=", False), ("parking_location_id", "in", loc_ids),
                ("move_type", "in", ("out_invoice", "out_refund")), ("state", "=", "posted")]

    @api.model
    def _revenue_by_month(self, loc_ids, today):
        start = (today - relativedelta(months=11)).replace(day=1)
        rows = self.env["account.move"].sudo()._read_group(
            self._invoice_domain(loc_ids) + [("invoice_date", ">=", start)],
            ["invoice_date:month"], ["amount_untaxed_signed:sum", "amount_residual_signed:sum"])
        months = [start + relativedelta(months=i) for i in range(12)]
        invoiced, due = [], []
        for m in months:
            match = [r for r in rows if r[0] and (r[0].year, r[0].month) == (m.year, m.month)]
            invoiced.append(sum(r[1] for r in match))
            due.append(sum(r[2] for r in match))
        return {"labels": [m.strftime("%Y-%m") for m in months], "invoiced": invoiced, "due": due}

    @api.model
    def _finance_data(self, loc_ids, dt_from, date_from, today):
        Move = self.env["account.move"].sudo()
        base = self._invoice_domain(loc_ids)
        period_moves = Move.search(base + [("invoice_date", ">=", date_from)])
        open_moves = Move.search(base + [("payment_state", "in", ("not_paid", "partial"))])
        overdue = open_moves.filtered(lambda m: m.invoice_date_due and m.invoice_date_due < today)
        debtors = Move._read_group(
            base + [("payment_state", "in", ("not_paid", "partial"))],
            ["partner_id"], ["amount_residual_signed:sum"], order="amount_residual_signed:sum desc", limit=6)
        return {
            "invoiced": sum(period_moves.mapped("amount_untaxed_signed")),
            "invoiced_total": sum(period_moves.mapped("amount_total_signed")),
            "collected": sum(period_moves.mapped("amount_total_signed")) - sum(period_moves.mapped("amount_residual_signed")),
            "outstanding": sum(open_moves.mapped("amount_residual_signed")),
            "overdue": sum(overdue.mapped("amount_residual_signed")),
            "overdue_count": len(overdue),
            "debtors": [{"id": p.id, "name": p.display_name, "amount": amount} for p, amount in debtors if p],
        }
