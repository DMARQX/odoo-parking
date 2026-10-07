import logging
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

class ParkingContractWash(models.Model):
    _name = "parking.contract.wash"
    _description = "Car Wash Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "wash_date desc, id desc"
    _rec_name = "display_name"

    contract_id = fields.Many2one("parking.contract", string="Contract", required=True, ondelete="cascade")
    vehicle_id = fields.Many2one("parking.vehicle", string="Vehicle", required=True)
    partner_id = fields.Many2one("res.partner", string="Customer", related="contract_id.partner_id", store=True)
    location_id = fields.Many2one("parking.location", string="Branch", related="contract_id.location_id", store=True)
    wash_date = fields.Datetime(string="Wash Date", required=True, default=fields.Datetime.now)
    washed_by = fields.Many2one("res.users", string="Washed By", default=lambda self: self.env.user, tracking=True)
    wash_number = fields.Integer(string="Wash #", readonly=True, copy=False)
    state = fields.Selection([
        ("draft", "Draft"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ], string="Status", default="draft", tracking=True)
    line_ids = fields.One2many("parking.contract.wash.line", "wash_id", string="Consumed Supplies")
    notes = fields.Text(string="Notes")
    display_name = fields.Char(string="Wash", compute="_compute_display_name", store=True)
    company_id = fields.Many2one("res.company", related="contract_id.company_id", store=True)
    stock_move_ids = fields.Many2many("stock.move", string="Supply Moves", readonly=True, copy=False,
        help="Supplies taken from the branch warehouse for this wash (and put back if it was cancelled).")

    @api.depends("vehicle_id", "wash_date", "wash_number")
    def _compute_display_name(self):
        for r in self:
            veh = r.vehicle_id.display_name or r.vehicle_id.license_plate or ""
            date_str = r.wash_date.strftime("%Y-%m-%d %H:%M") if r.wash_date else ""
            r.display_name = f"{veh} - Wash #{r.wash_number} - {date_str}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            contract = self.env["parking.contract"].browse(vals.get("contract_id"))
            vehicle = self.env["parking.vehicle"].browse(vals.get("vehicle_id"))

            # Check remaining washes
            if contract.remaining_washes <= 0:
                raise UserError(_("No free washes remaining for this contract."))

            # Check wash interval
            last_wash = self.search([
                ("vehicle_id", "=", vehicle.id),
                ("state", "=", "done"),
            ], order="wash_date desc", limit=1)
            interval_days = contract.wash_interval_days
            if last_wash and interval_days > 0:
                next_allowed = last_wash.wash_date + timedelta(days=interval_days)
                if fields.Datetime.now() < next_allowed:
                    remaining_hours = (next_allowed - fields.Datetime.now()).total_seconds() / 3600
                    raise UserError(_(
                        "Vehicle %(veh)s was washed on %(date)s. "
                        "Next wash allowed after %(interval)d days (%(next)s). "
                        "Please wait %(hours).0f more hour(s)."
                    ) % {
                        "veh": vehicle.display_name,
                        "date": last_wash.wash_date.strftime("%Y-%m-%d %H:%M"),
                        "interval": interval_days,
                        "next": next_allowed.strftime("%Y-%m-%d %H:%M"),
                        "hours": remaining_hours,
                    })

            # Auto-number wash
            last = self.search([("vehicle_id", "=", vehicle.id)], order="wash_number desc", limit=1)
            vals["wash_number"] = (last.wash_number or 0) + 1
        records = super().create(vals_list)
        for rec in records.filtered(lambda w: w.state == "done"):
            rec._consume_supplies()
            rec._notify_customer()
        return records

    def action_done(self):
        for r in self.filtered(lambda w: w.state != "done"):
            r.state = "done"
            r._consume_supplies()
            r._notify_customer()

    def _notify_customer(self):
        self.env["parking.notification.rule"]._notify("wash_done", self, self.partner_id)

    def action_cancel(self):
        for r in self:
            if r.state == "done":
                r._return_supplies()
            r.state = "cancelled"

    # ------------------------------------------------------------------
    # Supplies through Odoo inventory
    # ------------------------------------------------------------------
    def _supply_items(self):
        """(product, qty) used by this wash: its own lines, else the company's wash kit."""
        self.ensure_one()
        if self.line_ids:
            items = [(l.product_id, l.quantity) for l in self.line_ids]
        else:
            kit = self.env["parking.wash.kit.item"].sudo().search(
                [("company_id", "in", (self.company_id.id, False)), ("product_id", "!=", False)])
            items = [(k.product_id, k.default_quantity) for k in kit]
        return [(p, q) for p, q in items if p.is_storable and q > 0]

    def _wash_locations(self):
        self.ensure_one()
        company = self.company_id.sudo()
        warehouse = self.location_id.warehouse_id or self.env["stock.warehouse"].sudo().search(
            [("company_id", "=", company.id)], limit=1)
        dest = company.parking_wash_location_id
        if not dest:
            parent = self.env.ref("stock.stock_location_locations_virtual", raise_if_not_found=False)
            dest = self.env["stock.location"].sudo().create({
                "name": _("Parking Wash Consumption"),
                "usage": "inventory",
                "location_id": parent.id if parent else False,
                "company_id": company.id,
            })
            company.parking_wash_location_id = dest
        return warehouse, dest

    def _consume_supplies(self):
        """Take the wash supplies out of the branch warehouse; their cost is booked as an expense."""
        for wash in self.filtered(lambda w: w.company_id.parking_wash_consume_stock and not w.stock_move_ids):
            items = wash._supply_items()
            if not items:
                continue
            warehouse, dest = wash._wash_locations()
            if not warehouse:
                wash._message_log(body=_("No warehouse for branch %s: supplies were not taken from stock.",
                                         wash.location_id.display_name or "-"))
                continue
            source = warehouse.lot_stock_id
            short = [
                "%s (%s / %s)" % (p.display_name, p.with_context(location=source.id).qty_available, q)
                for p, q in items
                if float_compare(p.with_context(location=source.id).qty_available, q,
                                 precision_rounding=p.uom_id.rounding) < 0]
            if short and wash.company_id.parking_stock_shortage == "block":
                wash._message_log(body=_("Supplies short, nothing taken from stock: %s", ", ".join(short)))
                continue
            try:
                with self.env.cr.savepoint():
                    moves = wash._move_supplies(items, source, dest)
            except Exception as e:
                _logger.exception("Wash supplies for %s failed", wash.display_name)
                wash._message_log(body=_("Supplies could not be taken from stock: %s", e))
                continue
            wash.sudo().stock_move_ids = moves
            if short:
                wash._message_log(body=_("Supplies taken with insufficient stock (available / used): %s",
                                         ", ".join(short)))

    def _return_supplies(self):
        """A cancelled wash puts its supplies back."""
        for wash in self.filtered("stock_move_ids"):
            done = wash.stock_move_ids.filtered(lambda m: m.state == "done" and m.quantity)
            if not done:
                continue
            items = [(m.product_id, m.quantity) for m in done]
            try:
                with self.env.cr.savepoint():
                    back = wash._move_supplies(items, done[0].location_dest_id, done[0].location_id)
                wash.sudo().stock_move_ids = [(4, m.id) for m in back]
            except Exception as e:
                _logger.exception("Returning wash supplies for %s failed", wash.display_name)
                wash._message_log(body=_("Supplies could not be put back in stock: %s", e))

    def _move_supplies(self, items, source, dest):
        self.ensure_one()
        Move = self.env["stock.move"].sudo()
        moves = Move.create([{
            "name": _("Car wash %s", self.display_name),
            "product_id": product.id,
            "product_uom_qty": qty,
            "product_uom": product.uom_id.id,
            "location_id": source.id,
            "location_dest_id": dest.id,
            "company_id": self.company_id.id,
            "origin": self.contract_id.name,
        } for product, qty in items])
        moves._action_confirm()
        for move in moves:
            move.quantity = move.product_uom_qty
            move.picked = True
        moves._action_done()
        analytic = self.location_id.analytic_account_id
        if analytic:
            # Branch profitability: the supplies' cost lands on the branch.
            for line in moves.account_move_ids.line_ids.filtered(lambda l: l.account_id.account_type in ("expense", "expense_direct_cost")):
                line.analytic_distribution = {str(analytic.id): 100}
        return moves

class ParkingContractWashLine(models.Model):
    _name = "parking.contract.wash.line"
    _description = "Wash Consumed Supply Line"
    _order = "id"

    wash_id = fields.Many2one("parking.contract.wash", string="Wash", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Supply Item", required=True)
    name = fields.Char(string="Description", related="product_id.name", readonly=True)
    quantity = fields.Float(string="Quantity Consumed", required=True, default=1.0)
    uom_id = fields.Many2one("uom.uom", string="Unit", related="product_id.uom_id", readonly=True)
    price_unit = fields.Monetary(string="Unit Cost", currency_field="company_currency_id")
    company_id = fields.Many2one("res.company", related="wash_id.company_id", store=True)
    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")