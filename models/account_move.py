import logging

from odoo import models, fields, _

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    parking_contract_id = fields.Many2one("parking.contract", string="Parking Contract")
    parking_location_id = fields.Many2one("parking.location", string="Parking Branch",
        related="parking_contract_id.location_id", store=True, readonly=True)
    parking_picking_id = fields.Many2one("stock.picking", string="Parking Stock Transfer",
        readonly=True, copy=False,
        help="Delivery (or return, for a credit note) of the storable products on this invoice.")

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        for move in posted.filtered(lambda m: m.parking_contract_id and not m.parking_picking_id
                                    and m.move_type in ("out_invoice", "out_refund")
                                    and m.company_id.parking_invoice_stock_moves):
            try:
                with self.env.cr.savepoint():
                    move.sudo()._parking_create_stock_picking()
            except Exception as e:
                # The invoice stays posted; the warehouse team fixes the transfer by hand.
                _logger.exception("Parking stock transfer for %s failed", move.name)
                move.sudo()._message_log(body=_("Stock transfer could not be created: %s", e))
        return posted

    def _parking_create_stock_picking(self):
        """Deliver (invoice) or take back (credit note) the storable products from the branch warehouse.

        Parking invoices are not created from sale orders, so nothing else moves this stock.
        """
        self.ensure_one()
        lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == "product" and l.product_id.is_storable and l.quantity)
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
        customers = self.env.ref("stock.stock_location_customers")
        refund = self.move_type == "out_refund"
        picking_type = warehouse.in_type_id if refund else warehouse.out_type_id
        source, dest = (customers, warehouse.lot_stock_id) if refund else (warehouse.lot_stock_id, customers)
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "location_id": source.id,
            "location_dest_id": dest.id,
            "company_id": self.company_id.id,
            "move_ids": [(0, 0, {
                "name": line.name or line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity,
                "product_uom": (line.product_uom_id or line.product_id.uom_id).id,
                "location_id": source.id,
                "location_dest_id": dest.id,
                "company_id": self.company_id.id,
            }) for line in lines],
        })
        picking.action_confirm()
        for stock_move in picking.move_ids:
            stock_move.quantity = stock_move.product_uom_qty
            stock_move.picked = True
        picking._action_done()
        self.parking_picking_id = picking
        self._message_log(body=_("Stock transfer %s done.", picking._get_html_link()))
        return picking

    def action_view_parking_picking(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.parking_picking_id.id,
            "view_mode": "form",
        }
