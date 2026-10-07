import logging

from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    parking_contract_id = fields.Many2one("parking.contract", string="Parking Contract")
    parking_location_id = fields.Many2one("parking.location", string="Parking Branch",
        related="parking_contract_id.location_id", store=True, readonly=True)
    parking_picking_id = fields.Many2one("stock.picking", string="Parking Stock Transfer",
        readonly=True, copy=False,
        help="Delivery (or return, for a credit note) of the storable products on this invoice.")
    parking_invoice_kind = fields.Selection([
        ("period", "Subscription period"),
        ("prepaid", "Remaining term paid in advance"),
        ("sale", "Separate sale"),
        ("final", "Final invoice"),
        ("deposit_refund", "Deposit refund"),
        ("prepaid_refund", "Unused prepaid months"),
    ], string="Parking Invoice Type", readonly=True, copy=False)
    parking_period_start = fields.Date(string="Service From", readonly=True, copy=False)
    parking_period_end = fields.Date(string="Service To", readonly=True, copy=False)
    parking_return_goods = fields.Boolean(
        string="Return Goods to Stock", copy=False,
        help="Credit notes only: bring the storable products back into the branch warehouse. "
             "Leave off for a price correction where nothing comes back.")

    # ------------------------------------------------------------------
    # Posting, cancelling, resetting
    # ------------------------------------------------------------------
    def _post(self, soft=True):
        self.filtered("parking_contract_id")._parking_check_vat()
        posted = super()._post(soft=soft)
        for move in posted.filtered(lambda m: m.parking_contract_id and not m.parking_picking_id
                                    and m.company_id.parking_invoice_stock_moves
                                    and (m.move_type == "out_invoice"
                                         or (m.move_type == "out_refund" and m.parking_return_goods))):
            try:
                with self.env.cr.savepoint():
                    move.sudo()._parking_create_stock_picking()
            except Exception as e:
                # The invoice stays posted; the warehouse team fixes the transfer by hand.
                _logger.exception("Parking stock transfer for %s failed", move.name)
                move.sudo()._message_log(body=_("Stock transfer could not be created: %s", e))
        return posted

    def _parking_check_vat(self):
        """A parking sale line without VAT is an error (ZATCA), unless a fiscal position exempts the customer.

        Deposit lines carry no VAT by nature; credit notes reversing an invoice mirror it as it was.
        """
        problems = []
        for move in self.filtered(lambda m: m.move_type in ("out_invoice", "out_refund")
                                  and not m.fiscal_position_id and not m.reversed_entry_id):
            deposit_account = move.company_id.parking_deposit_account_id
            for line in move.invoice_line_ids.filtered(lambda l: l.display_type == "product"):
                if line.tax_ids or not line.price_subtotal or line.parking_line_kind == "deposit":
                    continue
                if deposit_account and line.account_id == deposit_account:
                    continue
                name = (line.name or "").lower()
                if not line.parking_line_kind and any(w in name for w in ("deposit", "insurance", "تأمين")):
                    continue  # deposit lines of invoices issued before the line type existed
                problems.append("%s: %s" % (move.invoice_origin or move.name or _("Draft"), line.name))
        if problems:
            raise UserError(_(
                "These parking invoice lines have no VAT:\n%s\n\nAdd the VAT (15%%) to the lines, or set the "
                "customer's fiscal position on the invoice if the customer is exempt.", "\n".join(problems)))

    def button_draft(self):
        parking = self.filtered("parking_contract_id")
        # The goods come back now; posting again delivers what the edited invoice says.
        parking.sudo()._parking_undo_stock()
        return super().button_draft()

    def button_cancel(self):
        parking = self.filtered("parking_contract_id")
        parking.sudo()._parking_undo_stock()
        res = super().button_cancel()
        parking.filtered(lambda m: m.state == "cancel").sudo()._parking_release_contract()
        return res

    def _parking_release_contract(self):
        """A cancelled invoice gives back what it billed so it can be billed again."""
        for move in self:
            contract = move.parking_contract_id
            notes = []
            lines = contract.service_line_ids.filtered(lambda l: l.invoice_id == move)
            if lines:
                lines.write({"invoice_id": False})
                notes.append(_("one-time items back to billing: %s", ", ".join(lines.mapped("name"))))
            if move.move_type == "out_invoice" and contract.deposit_invoiced and move._parking_has_deposit():
                contract.deposit_invoiced = False
                notes.append(_("deposit back to billing"))
            credits = contract.wash_credit_ids.filtered(lambda c: c.invoice_id == move and c.quantity > 0)
            if credits:
                washes = sum(credits.mapped("quantity"))
                contract._add_wash_credit(-washes, "cancel", move, note=_("Invoice %s cancelled", move.name))
                notes.append(_("%s wash(es) removed", washes))
            if move.parking_invoice_kind == "prepaid" and contract.prepaid_until:
                contract.write({"prepaid_until": False,
                                "recurring_next_date": move.parking_period_start or fields.Date.today()})
                notes.append(_("periodic invoicing resumed"))
            if move.parking_invoice_kind == "deposit_refund":
                contract.deposit_refunded = False
                notes.append(_("deposit refund undone"))
            if notes:
                contract._message_log(body=_("Invoice %(inv)s cancelled: %(what)s.",
                                             inv=move._get_html_link(), what="; ".join(notes)))

    def _parking_has_deposit(self):
        self.ensure_one()
        deposit_account = self.company_id.parking_deposit_account_id
        return any(l.parking_line_kind == "deposit"
                   or (not l.parking_line_kind and deposit_account and l.account_id == deposit_account)
                   for l in self.invoice_line_ids)

    # ------------------------------------------------------------------
    # Stock
    # ------------------------------------------------------------------
    def _parking_stock_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product" and l.product_id.is_storable and l.quantity)

    def _parking_create_stock_picking(self):
        """Deliver (invoice) or take back (credit note) the storable products from the branch warehouse.

        Parking invoices are not created from sale orders, so nothing else moves this stock.
        """
        self.ensure_one()
        lines = self._parking_stock_lines()
        if not lines:
            return False
        tracked = lines.filtered(lambda l: l.product_id.tracking != "none")
        if tracked:
            self._message_log(body=_(
                "Lot/serial tracked products are not moved automatically: %s",
                ", ".join(tracked.product_id.mapped("display_name"))))
            lines -= tracked
            if not lines:
                return False
        warehouse = self.parking_location_id.warehouse_id or self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_id.id)], limit=1)
        if not warehouse:
            self._message_log(body=_("No warehouse found for branch %s; stock was not moved.",
                                     self.parking_location_id.display_name or "-"))
            return False
        refund = self.move_type == "out_refund"
        quantities = {line: line.quantity for line in lines}
        if refund:
            quantities = self._parking_returnable_quantities(quantities)
            if not quantities:
                self._message_log(body=_("Nothing to return: the original invoice delivered no stock."))
                return False
        elif self._parking_stock_short(warehouse, quantities):
            return False
        customers = self.env.ref("stock.stock_location_customers")
        picking_type = warehouse.in_type_id if refund else warehouse.out_type_id
        source, dest = (customers, warehouse.lot_stock_id) if refund else (warehouse.lot_stock_id, customers)
        picking = self._parking_do_transfer(picking_type, source, dest, [
            (line.product_id, qty, line.product_uom_id or line.product_id.uom_id, line.name)
            for line, qty in quantities.items()])
        self.parking_picking_id = picking
        self._message_log(body=_("Stock transfer %s done.", picking._get_html_link()))
        return picking

    def _parking_returnable_quantities(self, quantities):
        """A credit note returns at most what its invoice delivered, per product."""
        origin = self.reversed_entry_id
        delivered = {}
        for move in origin.parking_picking_id.move_ids.filtered(lambda m: m.state == "done"):
            delivered[move.product_id] = delivered.get(move.product_id, 0.0) + move.quantity
        result = {}
        for line, qty in quantities.items():
            allowed = delivered.get(line.product_id, 0.0)
            if allowed > 0:
                take = min(qty, allowed)
                delivered[line.product_id] = allowed - take
                result[line] = take
        return result

    def _parking_stock_short(self, warehouse, quantities):
        """Check stock; True when the delivery must not happen (company set to block)."""
        short = []
        needed = {}
        for line, qty in quantities.items():
            needed[line.product_id] = needed.get(line.product_id, 0.0) + qty
        for product, qty in needed.items():
            available = product.with_context(location=warehouse.lot_stock_id.id).qty_available
            if float_compare(available, qty, precision_rounding=product.uom_id.rounding) < 0:
                short.append("%s (%s / %s)" % (product.display_name, available, qty))
        if not short:
            return False
        block = self.company_id.parking_stock_shortage == "block"
        body = (_("Stock is short, nothing was delivered: %s", ", ".join(short)) if block
                else _("Delivered with insufficient stock (available / sold): %s", ", ".join(short)))
        self._message_log(body=body)
        if block:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Deliver parking sale %s", self.name),
                note=body,
                user_id=(self.parking_location_id.manager_id or self.invoice_user_id or self.env.user).id)
        return block

    def _parking_do_transfer(self, picking_type, source, dest, items):
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "location_id": source.id,
            "location_dest_id": dest.id,
            "company_id": self.company_id.id,
            "move_ids": [(0, 0, {
                "name": name or product.display_name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": uom.id,
                "location_id": source.id,
                "location_dest_id": dest.id,
                "company_id": self.company_id.id,
            }) for product, qty, uom, name in items],
        })
        picking.action_confirm()
        for stock_move in picking.move_ids:
            stock_move.quantity = stock_move.product_uom_qty
            stock_move.picked = True
        picking._action_done()
        return picking

    def _parking_undo_stock(self):
        """Reverse the transfer of an invoice that is cancelled or set back to draft."""
        for move in self.filtered(lambda m: m.parking_picking_id.state == "done"):
            picking = move.parking_picking_id
            items = [(m.product_id, m.quantity, m.product_uom, m.name)
                     for m in picking.move_ids.filtered(lambda m: m.state == "done" and m.quantity)]
            if not items:
                continue
            warehouse = picking.picking_type_id.warehouse_id
            back_type = (warehouse.in_type_id if picking.picking_type_id == warehouse.out_type_id
                         else warehouse.out_type_id) or picking.picking_type_id
            try:
                with self.env.cr.savepoint():
                    back = move._parking_do_transfer(back_type, picking.location_dest_id,
                                                     picking.location_id, items)
                    back.origin = _("Reversal of %s", picking.name)
                move.parking_picking_id = False
                move._message_log(body=_("Stock transfer %(old)s reversed by %(new)s.",
                                         old=picking._get_html_link(), new=back._get_html_link()))
            except Exception as e:
                _logger.exception("Reversing parking transfer %s failed", picking.name)
                move._message_log(body=_("Stock transfer %(old)s could not be reversed: %(err)s",
                                         old=picking._get_html_link(), err=e))

    def action_view_parking_picking(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.parking_picking_id.id,
            "view_mode": "form",
        }


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    parking_line_kind = fields.Selection([
        ("rent", "Parking rent"),
        ("service", "Service / product"),
        ("deposit", "Deposit"),
    ], string="Parking Line Type", readonly=True, copy=True)


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    parking_has_contract = fields.Boolean(compute="_compute_parking_has_contract")
    parking_return_goods = fields.Boolean(
        string="Return goods to stock", default=True,
        help="Bring the storable products of the parking invoice back into the branch warehouse. "
             "Untick for a price correction where nothing is returned.")

    @api.depends("move_ids")
    def _compute_parking_has_contract(self):
        for wizard in self:
            wizard.parking_has_contract = any(wizard.move_ids.mapped("parking_contract_id"))

    def _prepare_default_reversal(self, move):
        vals = super()._prepare_default_reversal(move)
        if move.parking_contract_id:
            vals["parking_return_goods"] = self.parking_return_goods
        return vals
