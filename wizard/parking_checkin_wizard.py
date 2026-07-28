from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ParkingCheckinCheckoutWizard(models.TransientModel):
    _name = "parking.checkin.checkout.wizard"
    _description = "Check In/Out Wizard"

    operation = fields.Selection([
        ("check_in", "Check In (Return)"),
        ("check_out", "Check Out (Exit)"),
    ], string="Operation", required=True, default="check_out")

    partner_id = fields.Many2one("res.partner", string="Owner", help="Select vehicle owner to find their vehicles")
    vehicle_id = fields.Many2one("parking.vehicle", string="License Plate", help="Search vehicle by plate directly")

    vehicle_ids = fields.Many2many("parking.vehicle", string="Vehicles to Process")
    vehicle_found = fields.Boolean(default=False)
    search_done = fields.Boolean(default=False)
    search_message = fields.Char(string="Result")

    def action_search(self):
        self.vehicle_ids = [(5, 0, 0)]
        self.vehicle_found = False
        self.search_done = False
        self.search_message = ""

        domain = []
        if self.partner_id:
            domain += [("owner_id", "=", self.partner_id.id)]
        if self.vehicle_id:
            domain += [("id", "=", self.vehicle_id.id)]

        if not domain:
            raise UserError(_("Please select a customer or a vehicle to search."))

        vehicles = self.env["parking.vehicle"].search(domain, limit=50)
        count = len(vehicles)

        if count == 0:
            self.search_message = _("No vehicles found matching your criteria.")
            self.search_done = True
            return self._reload()

        self.vehicle_ids = [(6, 0, vehicles.ids)]
        self.vehicle_found = True
        self.search_done = True
        return self._reload()

    def action_confirm(self):
        self.ensure_one()
        if not self.vehicle_ids:
            raise UserError(_("Please select at least one vehicle."))

        processed = 0
        errors = []

        for vehicle in self.vehicle_ids:
            active_contract = self.env["parking.contract"].search([
                ("vehicle_ids", "in", vehicle.id), ("state", "=", "active")
            ], limit=1)
            spot = active_contract.spot_id if active_contract else False

            try:
                if self.operation == "check_out":
                    movement_vals = {
                        "vehicle_id": vehicle.id,
                        "check_out_time": fields.Datetime.now(),
                        "operator_out_id": self.env.user.id,
                    }
                    if active_contract:
                        movement_vals["contract_id"] = active_contract.id
                    if spot:
                        movement_vals["spot_id"] = spot.id
                    self.env["parking.vehicle.movement"].create(movement_vals)
                    if spot and spot.status == "occupied":
                        old_status = spot.status
                        spot.status = "client_out"
                        spot.env["parking.spot.status.log"].create({
                            "spot_id": spot.id,
                            "old_status": old_status,
                            "new_status": "client_out",
                            "operator_id": self.env.user.id,
                        })
                    processed += 1

                elif self.operation == "check_in":
                    movement = self.env["parking.vehicle.movement"].search([
                        ("vehicle_id", "=", vehicle.id),
                        ("check_in_time", "=", False),
                    ], order="check_out_time desc", limit=1)
                    if movement:
                        movement.write({
                            "check_in_time": fields.Datetime.now(),
                            "operator_in_id": self.env.user.id,
                        })
                        if movement.spot_id and movement.spot_id.status == "client_out":
                            old_status = movement.spot_id.status
                            movement.spot_id.status = "occupied"
                            movement.spot_id.env["parking.spot.status.log"].create({
                                "spot_id": movement.spot_id.id,
                                "old_status": old_status,
                                "new_status": "occupied",
                                "operator_id": self.env.user.id,
                            })
                        processed += 1
                    else:
                        movement_vals = {
                            "vehicle_id": vehicle.id,
                            "check_in_time": fields.Datetime.now(),
                            "operator_in_id": self.env.user.id,
                            "check_out_time": False,
                        }
                        if active_contract:
                            movement_vals["contract_id"] = active_contract.id
                        if spot:
                            movement_vals["spot_id"] = spot.id
                        self.env["parking.vehicle.movement"].create(movement_vals)
                        processed += 1
            except Exception as e:
                errors.append(f"{vehicle.display_name}: {e}")

        result_msg = _("%d vehicle(s) processed successfully.") % processed
        if errors:
            result_msg += "\n" + _("Errors: %s") % "; ".join(errors)

        if processed > 0:
            return {
                "type": "ir.actions.act_window_close",
            }
        else:
            raise UserError(result_msg)

    def _reload(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "parking.checkin.checkout.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }
