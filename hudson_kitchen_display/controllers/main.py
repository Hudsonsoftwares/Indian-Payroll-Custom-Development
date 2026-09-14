from datetime import timedelta

from werkzeug.exceptions import Forbidden

from odoo import http, fields
from odoo.http import request


def _has_kitchen_access(env):
    user = env.user
    if user.has_group('point_of_sale.group_pos_user') or user.has_group('point_of_sale.group_pos_manager'):
        return True
    return bool(getattr(user, 'kitchen_screen_access', False))


class KitchenDisplayController(http.Controller):

    # ------------------------------------------------------------------
    # Kitchen (internal, staff-facing) screen
    # ------------------------------------------------------------------
    @http.route('/hudson_kitchen_display/web', type='http', auth='user')
    def kitchen_display_page(self, display_id=None, **kwargs):
        if not _has_kitchen_access(request.env):
            raise Forbidden()
        display = request.env['pos.prep.display'].browse(int(display_id)) if display_id else None
        if not display:
            display = request.env['pos.prep.display'].search([], limit=1)
        return request.render('hudson_kitchen_display.kitchen_display_page', {
            'display_id': display.id if display else '',
            'display_name': display.name if display else 'Kitchen Display',
            'access_token': display.access_token if display else '',
        })

    @http.route('/hudson_kitchen_display/get_orders', type='json', auth='user')
    def get_orders(self, display_id):
        if not _has_kitchen_access(request.env):
            return {'error': 'access_denied'}
        display = request.env['pos.prep.display'].browse(int(display_id))
        orders = request.env['pos.prep.order'].search([('display_id', '=', display.id)])

        from ..utils import get_pos_categories

        # Determine restricted categories from display or POS config settings
        categories = display.category_ids
        if not categories:
            configs = display.pos_config_ids or request.env['pos.config'].search([])
            for cfg in configs:
                if getattr(cfg, 'iface_available_categ_ids', False):
                    categories |= cfg.iface_available_categ_ids
        if not categories:
            categories = request.env['pos.category'].search([])

        def _get_order_category_ids(o):
            cat_ids = set()
            for l in o.line_ids:
                if l.product_id:
                    for c in get_pos_categories(l.product_id):
                        cat_ids.add(c.id)
            return list(cat_ids)

        return {
            'display_name': display.name,
            'stages': [
                {'id': s.id, 'name': s.name, 'sequence': s.sequence,
                 'color': s.color, 'alert_timer': s.alert_timer}
                for s in display.stage_ids.sorted('sequence')
            ],
            'categories': [
                {'id': c.id, 'name': c.name}
                for c in categories.sorted('name')
            ],
            'orders': [{
                'id': o.id,
                'pos_order_id': o.pos_order_id.id,
                'pos_reference': o.pos_order_id.pos_reference,
                'table_number': o.table_number or (o.pos_order_id.pos_reference.split()[-1] if o.pos_order_id and o.pos_order_id.pos_reference else ''),
                'customer_count': o.customer_count or getattr(o.pos_order_id, 'customer_count', 1) or 1,
                'fulfillment_type': o.fulfillment_type or 'dine_in',
                'stage_id': o.stage_id.id,
                'category_ids': _get_order_category_ids(o),
                'create_date': fields.Datetime.to_string(o.create_date),
                'minutes_ago': int(round((fields.Datetime.now() - o.create_date).total_seconds() / 60)) if o.create_date else 0,
                'lines': [{'id': l.id, 'name': l.name, 'qty': int(l.qty) if float(l.qty).is_integer() else l.qty, 'note': l.note, 'is_done': bool(l.is_done)} for l in o.line_ids],
            } for o in orders],
        }

    @http.route('/hudson_kitchen_display/toggle_line', type='json', auth='user')
    def toggle_line(self, line_id):
        if not _has_kitchen_access(request.env):
            return False
        line = request.env['pos.prep.order.line'].browse(int(line_id))
        if not line.exists():
            return False
        line.action_toggle_done()
        return True

    @http.route('/hudson_kitchen_display/advance_line', type='json', auth='user')
    def advance_line(self, line_id):
        if not _has_kitchen_access(request.env):
            return False
        line = request.env['pos.prep.order.line'].browse(int(line_id))
        if not line.exists():
            return False
        line.action_advance_line()
        return True

    @http.route('/hudson_kitchen_display/change_stage', type='json', auth='user')
    def change_stage(self, order_id, stage_id):
        if not _has_kitchen_access(request.env):
            return False
        order = request.env['pos.prep.order'].browse(int(order_id))
        order.write({'stage_id': int(stage_id)})
        order._notify_display()
        return True

    @http.route('/hudson_kitchen_display/previous_stage', type='json', auth='user')
    def previous_stage(self, order_id):
        if not _has_kitchen_access(request.env):
            return False
        order = request.env['pos.prep.order'].browse(int(order_id))
        order.action_previous_stage()
        return True

    @http.route('/hudson_kitchen_display/mark_done', type='json', auth='user')
    def mark_done(self, order_id):
        if not _has_kitchen_access(request.env):
            return False
        order = request.env['pos.prep.order'].browse(int(order_id))
        if order.exists():
            order.action_mark_done()
        return True

    @http.route('/hudson_kitchen_display/clear_completed', type='json', auth='user')
    def clear_completed(self, display_id):
        if not _has_kitchen_access(request.env):
            return False
        display = request.env['pos.prep.display'].browse(int(display_id))
        stages = display.stage_ids.sorted('sequence')
        if stages:
            last_stage = stages[-1]
            orders = request.env['pos.prep.order'].search([
                ('display_id', '=', display.id),
                ('stage_id', '=', last_stage.id),
            ])
            orders.action_mark_done()
        return True

    @http.route('/hudson_kitchen_display/recall', type='json', auth='user')
    def recall(self, order_id=None, display_id=None):
        if not _has_kitchen_access(request.env):
            return {'success': False, 'error': 'access_denied'}
        Order = request.env['pos.prep.order'].with_context(active_test=False)
        order = None
        if order_id:
            order = Order.browse(int(order_id))
        elif display_id:
            order = Order.search([
                ('display_id', '=', int(display_id)),
            ], order='write_date desc, id desc', limit=1)

        if not order or not order.exists():
            return {'success': False, 'error': 'not_found'}

        order.action_recall()
        return {
            'success': True,
            'order_id': order.id,
            'stage_id': order.stage_id.id,
            'stage_name': order.stage_id.name,
            'table_number': order.table_number,
        }

    @http.route('/hudson_kitchen_display/reset_all', type='json', auth='user')
    def reset_all(self, display_id):
        if not _has_kitchen_access(request.env):
            return False
        display = request.env['pos.prep.display'].browse(int(display_id))
        display.action_reset_all_orders()
        return True

    # ------------------------------------------------------------------
    # Manual "Send to Kitchen" (see pos_send_button.js - experimental)
    # ------------------------------------------------------------------
    @http.route('/hudson_kitchen_display/manual_send_last_order', type='json', auth='user')
    def manual_send_last_order(self):
        order = request.env['pos.order'].sudo().search([
            ('create_uid', '=', request.env.uid),
            ('create_date', '>=', fields.Datetime.now() - timedelta(minutes=30)),
        ], order='create_date desc', limit=1)
        if not order:
            return {'ok': False}
        order.action_manual_send_to_kitchen()
        return {'ok': True, 'order_id': order.id}

    @http.route('/hudson_kitchen_display/manual_send/<int:order_id>', type='json', auth='user')
    def manual_send(self, order_id):
        order = request.env['pos.order'].sudo().browse(order_id)
        if not order.exists():
            return {'ok': False}
        order.action_manual_send_to_kitchen()
        return {'ok': True}

    # ------------------------------------------------------------------
    # Customer-facing order status screen (public, token protected)
    # ------------------------------------------------------------------
    @http.route('/pos-order-status/<string:access_token>', type='http', auth='public')
    def order_status_page(self, access_token, **kwargs):
        order = request.env['pos.order'].sudo().search(
            [('kitchen_access_token', '=', access_token)], limit=1)
        if not order:
            return request.not_found()
        return request.render('hudson_kitchen_display.order_status_page', {
            'order_id': order.id,
        })

    @http.route('/hudson_kitchen_display/get_order_status', type='json', auth='public')
    def get_order_status(self, order_id):
        order = request.env['pos.order'].sudo().browse(int(order_id))
        prep = order.prep_order_ids[:1]
        if not prep:
            return {'stage_name': 'Order received', 'sequence': 0, 'total_stages': 1}
        stages = prep.display_id.stage_ids.sorted('sequence')
        return {
            'stage_name': prep.stage_id.name,
            'sequence': prep.stage_id.sequence,
            'total_stages': len(stages),
        }

    # ------------------------------------------------------------------
    # Customer-facing order tracking screen (matching Odoo Online)
    # ------------------------------------------------------------------
    @http.route([
        '/pos-order-tracking',
        '/pos-order-tracking/',
        '/pos-order-tracking/<string:access_token>',
        '/hudson_kitchen_display/order_status',
    ], type='http', auth='public')
    def display_order_status_page(self, access_token=None, display_id=None, **kwargs):
        PrepDisplay = request.env['pos.prep.display'].sudo()
        token = access_token or kwargs.get('access_token')
        display = False
        if token:
            display = PrepDisplay.search([('access_token', '=', token)], limit=1)
        if not display and display_id:
            try:
                display = PrepDisplay.browse(int(display_id))
            except Exception:
                display = False
        if not display:
            display = PrepDisplay.search([], limit=1)

        return request.render('hudson_kitchen_display.display_order_status_page', {
            'display_id': display.id if display else '',
            'display_name': display.name if display else 'Order Status',
            'access_token': display.access_token if display else '',
        })

    @http.route([
        '/hudson_kitchen_display/get_display_orders_status',
        '/pos-order-tracking/get_orders_status',
    ], type='json', auth='public')
    def get_display_orders_status(self, display_id=None, access_token=None):
        PrepDisplay = request.env['pos.prep.display'].sudo()
        display = False
        if access_token:
            display = PrepDisplay.search([('access_token', '=', access_token)], limit=1)
        if not display and display_id:
            try:
                display = PrepDisplay.browse(int(display_id))
            except Exception:
                display = False
        if not display:
            display = PrepDisplay.search([], limit=1)

        if not display or not display.exists():
            return {'ready': [], 'preparing': []}

        stages = display.stage_ids.sorted('sequence')
        if not stages:
            return {'ready': [], 'preparing': []}

        # Identify stages
        ready_stage_ids = set()
        for s in stages:
            s_name = (s.name or '').lower()
            if 'ready' in s_name or 'complete' in s_name:
                ready_stage_ids.add(s.id)
        if not ready_stage_ids:
            ready_stage_ids = {stages[-1].id} if len(stages) == 1 else {s.id for s in stages[1:]}

        # 1. Active orders in kitchen
        active_orders = request.env['pos.prep.order'].sudo().search([
            ('display_id', '=', display.id),
            ('active', '=', True),
        ], order='id asc')

        # 2. Recently marked Done orders (within last 20 minutes)
        # So when the kitchen clicks "Done", the order appears / stays in "Ready" for customer pickup!
        recent_cutoff = fields.Datetime.now() - timedelta(minutes=20)
        done_orders = request.env['pos.prep.order'].sudo().search([
            ('display_id', '=', display.id),
            ('active', '=', False),
            ('|'),
            ('done_date', '>=', recent_cutoff),
            ('write_date', '>=', recent_cutoff),
        ], order='done_date desc, write_date desc', limit=25)

        def _get_display_number(prep_order):
            po = prep_order.pos_order_id
            if po:
                if getattr(po, 'tracking_number', False):
                    return str(po.tracking_number).strip()
                if getattr(po, 'table_id', False):
                    from ..utils import get_table_number
                    t_num = get_table_number(po.table_id)
                    if t_num:
                        return str(t_num)
                if po.pos_reference:
                    ref = po.pos_reference
                    parts = ref.replace('-', ' ').split()
                    last = parts[-1].lstrip('0')
                    return last or parts[-1]
            if prep_order.table_name:
                return str(prep_order.table_name).lstrip('T').strip()
            return str(prep_order.id)

        ready_orders = []
        prep_orders = []
        seen_refs = set()

        # Add active kitchen orders
        for o in active_orders:
            num = _get_display_number(o)
            if not num:
                continue
            if o.stage_id.id in ready_stage_ids:
                if num not in seen_refs:
                    ready_orders.append({'id': o.id, 'reference': num})
                    seen_refs.add(num)
            else:
                if num not in seen_refs:
                    prep_orders.append({'id': o.id, 'reference': num})
                    seen_refs.add(num)

        # Add recently completed / done orders into "Ready"
        for o in done_orders:
            num = _get_display_number(o)
            if not num:
                continue
            if num not in seen_refs:
                ready_orders.append({'id': o.id, 'reference': num})
                seen_refs.add(num)

        return {
            'ready': ready_orders,
            'preparing': prep_orders,
        }

    # ------------------------------------------------------------------
    # Virtual / Preview Order Printer handler for PoS testing
    # ------------------------------------------------------------------
    @http.route([
        '/hw_proxy/default_printer_action',
        '/hw_proxy/print_xml_receipt',
        '/hw_proxy/status',
        '/hw_proxy/status_json',
        '/hw_proxy/hello',
    ], type='jsonrpc', auth='none', cors='*')
    def hw_proxy_action(self, **kwargs):
        return {'result': True, 'status': 'connected'}
