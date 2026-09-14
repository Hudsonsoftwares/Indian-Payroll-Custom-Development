import uuid

from odoo import models, fields, api
from ..utils import get_pos_categories, get_fulfillment_type, get_line_note, get_table_number


class PosOrder(models.Model):
    _inherit = 'pos.order'

    prep_order_ids = fields.One2many('pos.prep.order', 'pos_order_id', string='Kitchen Orders')
    kitchen_access_token = fields.Char(default=lambda self: str(uuid.uuid4()), copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._send_to_kitchen_displays()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if 'lines' in vals or 'state' in vals:
            self._send_to_kitchen_displays(force=True)
        return res

    def action_manual_send_to_kitchen(self):
        """Manual re-send: pushes any order lines that haven't reached a
        display yet (e.g. items added after the initial send, or a kiosk/
        self-order flow that bypassed the normal create hook). Safe to call
        repeatedly - it never duplicates a line that's already on a display."""
        for order in self:
            order._send_to_kitchen_displays(force=True)
        return True

    def _send_to_kitchen_displays(self, force=False):
        PrepDisplay = self.env['pos.prep.display'].sudo()
        for order in self:
            config = order.config_id if ('config_id' in order._fields and order.config_id) else (order.session_id.config_id if 'session_id' in order._fields else False)
            if config:
                displays = PrepDisplay.search([
                    '|', ('pos_config_ids', '=', False), ('pos_config_ids', 'in', config.id),
                ])
            else:
                displays = PrepDisplay.search([])
            if not displays:
                continue

            fulfillment = get_fulfillment_type(order)
            already_sent_products = set()
            if order.prep_order_ids:
                if not force:
                    continue
                for prep in order.prep_order_ids:
                    already_sent_products.update(prep.line_ids.mapped('product_id.id'))

            table = order.table_id if 'table_id' in order._fields else False
            num = get_table_number(table)
            if num is not False and num is not None and str(num).strip():
                tbl_name = f"T{num}" if str(num).isdigit() else str(num)
            else:
                tbl_name = order.pos_reference.split()[-1] if order.pos_reference else ''
            cust_count = getattr(order, 'customer_count', 0) or getattr(table, 'seats', 0) or 1

            for display in displays:
                lines = []
                for line in order.lines:
                    if line.product_id.id in already_sent_products:
                        continue
                    categs = get_pos_categories(line.product_id)
                    if display.category_ids and not (display.category_ids & categs):
                        continue
                    product_name = getattr(line, 'full_product_name', False) or line.product_id.display_name or getattr(line, 'name', 'Item')
                    lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'name': product_name,
                        'qty': line.qty,
                        'note': get_line_note(line),
                    }))
                if not lines:
                    continue
                first_stage = display.stage_ids.sorted('sequence')[:1]
                if not first_stage:
                    continue
                prep_order = self.env['pos.prep.order'].sudo().create({
                    'pos_order_id': order.id,
                    'display_id': display.id,
                    'stage_id': first_stage.id,
                    'fulfillment_type': fulfillment,
                    'table_name': tbl_name,
                    'customer_count': cust_count,
                    'line_ids': lines,
                })
                prep_order._notify_display()
