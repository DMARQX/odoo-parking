from odoo import models, fields, api, _

class ParkingVehicle(models.Model):
    _name = "parking.vehicle"
    _description = "Vehicle"
    _rec_name = "display_name"
    _order = "license_plate"

    license_plate = fields.Char(string="License Plate", required=True)
    brand = fields.Char(string="Brand")
    model = fields.Char(string="Model")
    color = fields.Char(string="Color")
    year = fields.Integer(string="Year")
    owner_id = fields.Many2one("res.partner", string="Owner")
    active = fields.Boolean(default=True)
    notes = fields.Text(string="Notes")
    display_name = fields.Char(string="Vehicle", compute="_compute_display_name", store=True)

    contract_ids = fields.Many2many("parking.contract", string="Contracts")

    image_front = fields.Binary(string="Front View", attachment=True)
    image_back = fields.Binary(string="Rear View", attachment=True)
    image_left = fields.Binary(string="Left Side", attachment=True)
    image_right = fields.Binary(string="Right Side", attachment=True)
    image_interior = fields.Binary(string="Interior", attachment=True)
    image_license_doc = fields.Binary(string="License Document", attachment=True)
    image_owner_id_doc = fields.Binary(string="Owner ID", attachment=True)

    inspection_ids = fields.One2many("parking.vehicle.inspection", "vehicle_id", string="Inspections")
    inspection_count = fields.Integer(string="Inspections", compute="_compute_inspection_count")

    movement_ids = fields.One2many("parking.vehicle.movement", "vehicle_id", string="Movements")
    movement_count = fields.Integer(string="Movements", compute="_compute_movement_count")

    transfer_ids = fields.One2many("parking.vehicle.transfer", "vehicle_id", string="Transfers")
    transfer_count = fields.Integer(string="Transfers", compute="_compute_transfer_count")
    wash_ids = fields.One2many("parking.contract.wash", "vehicle_id", string="Car Washes")
    wash_count = fields.Integer(string="Total Washes", compute="_compute_wash_count", store=True)
    last_wash_date = fields.Datetime(string="Last Wash Date", compute="_compute_last_wash", store=True)
    next_allowed_wash = fields.Datetime(string="Next Wash", compute="_compute_next_allowed_wash", store=True)

    @api.depends("license_plate", "brand", "model", "color")
    def _compute_display_name(self):
        for r in self:
            parts = [r.license_plate or ""]
            if r.brand:
                parts.append(r.brand)
            if r.model:
                parts.append(r.model)
            if r.color:
                parts.append(r.color)
            r.display_name = " / ".join(parts)

    @api.depends("inspection_ids")
    def _compute_inspection_count(self):
        for r in self:
            r.inspection_count = len(r.inspection_ids)

    @api.depends("movement_ids")
    def _compute_movement_count(self):
        for r in self:
            r.movement_count = len(r.movement_ids)

    @api.depends("transfer_ids")
    def _compute_transfer_count(self):
        for r in self:
            r.transfer_count = len(r.transfer_ids)

    def action_open_inspections(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Inspections",
            "res_model": "parking.vehicle.inspection",
            "view_mode": "list,form",
            "domain": [("vehicle_id", "=", self.id)],
            "context": {"default_vehicle_id": self.id},
        }

    def _is_arabic_context(self):
        return (self.env.context.get('lang') or self.env.user.lang or '').startswith('ar')

    def action_open_movements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Vehicle Movements",
            "res_model": "parking.vehicle.movement",
            "view_mode": "list,form",
            "domain": [("vehicle_id", "=", self.id)],
            "context": {"default_vehicle_id": self.id},
        }

    def action_open_transfers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Vehicle Transfers",
            "res_model": "parking.vehicle.transfer",
            "view_mode": "list,form",
            "domain": [("vehicle_id", "=", self.id)],
            "context": {"default_vehicle_id": self.id},
        }

    @api.depends("wash_ids", "wash_ids.state")
    def _compute_wash_count(self):
        for r in self:
            r.wash_count = len(r.wash_ids.filtered(lambda w: w.state == "done"))

    @api.depends("wash_ids", "wash_ids.wash_date", "wash_ids.state")
    def _compute_last_wash(self):
        for r in self:
            done_washes = r.wash_ids.filtered(lambda w: w.state == "done")
            last = done_washes.sorted("wash_date", reverse=True)[:1]
            r.last_wash_date = last.wash_date if last else False

    @api.depends("last_wash_date", "contract_ids", "contract_ids.wash_interval_days")
    def _compute_next_allowed_wash(self):
        for r in self:
            if not r.last_wash_date:
                r.next_allowed_wash = fields.Datetime.now()
            else:
                interval = 4
                active_contracts = r.contract_ids.filtered(lambda c: c.state == "active")
                if active_contracts:
                    interval = max(c.wash_interval_days for c in active_contracts) if active_contracts else 4
                from datetime import timedelta
                r.next_allowed_wash = r.last_wash_date + timedelta(days=interval if interval else 4)

    def action_register_wash(self):
        self.ensure_one()
        active_contract = self.contract_ids.filtered(lambda c: c.state == "active")[:1]
        if not active_contract:
            raise UserError(_("No active contract found for vehicle %s.") % self.display_name)
        if active_contract.remaining_washes <= 0:
            raise UserError(_("No free washes remaining on contract %s.") % active_contract.name)
        if self.last_wash_date and self.next_allowed_wash and fields.Datetime.now() < self.next_allowed_wash:
            raise UserError(_(
                "Vehicle %(veh)s was washed on %(date)s. Next wash allowed after %(next)s."
            ) % {
                "veh": self.display_name,
                "date": self.last_wash_date.strftime("%Y-%m-%d %H:%M"),
                "next": self.next_allowed_wash.strftime("%Y-%m-%d %H:%M"),
            })

        # Create wash record
        wash = self.env["parking.contract.wash"].create({
            "contract_id": active_contract.id,
            "vehicle_id": self.id,
            "state": "done",
        })

        # Deduct wash kit supplies from branch stock
        kit_items = self.env["parking.wash.kit.item"].search([])
        location_id = active_contract.location_id.id if active_contract.location_id else False
        if location_id and kit_items:
            for item in kit_items:
                try:
                    self.env["parking.branch.stock"].deduct_stock(
                        item.product_id.id, item.default_quantity, location_id
                    )
                    self.env["parking.branch.stock.move"].create({
                        "location_id": location_id,
                        "product_id": item.product_id.id,
                        "quantity": -item.default_quantity,
                        "move_type": "out",
                        "wash_id": wash.id,
                        "notes": _("Auto-deducted by car wash #%s") % wash.wash_number,
                    })
                except Exception as e:
                    wash.message_post(
                        body=_("Could not deduct '%(item)s': %(error)s") % {
                            "item": item.name, "error": str(e)
                        },
                        subtype_xmlid="mail.mt_note",
                    )

        return {
            "type": "ir.actions.act_window",
            "name": _("Car Wash Record"),
            "res_model": "parking.contract.wash",
            "res_id": wash.id,
            "view_mode": "form",
            "target": "current",
        }