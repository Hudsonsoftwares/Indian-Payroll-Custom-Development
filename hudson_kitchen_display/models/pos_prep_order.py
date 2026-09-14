from odoo import models, fields, api


class PosPrepOrder(models.Model):
    _name = 'pos.prep.order'
    _description = 'Kitchen Preparation Order'
    _order = 'create_date asc'

    pos_order_id = fields.Many2one('pos.order', required=True, ondelete='cascade')
    display_id = fields.Many2one('pos.prep.display', required=True, ondelete='cascade')
    stage_id = fields.Many2one('pos.prep.display.stage', required=True)
    stage_sequence = fields.Integer(related='stage_id.sequence', store=True)
    line_ids = fields.One2many('pos.prep.order.line', 'prep_order_id', string='Lines')
    stage_log_ids = fields.One2many('pos.prep.order.stage.log', 'prep_order_id', string='Stage history')

    table_name = fields.Char(string='Table Name')
    customer_count = fields.Integer(string='Guests', default=2)
    table_number = fields.Char(compute='_compute_table_number')
    active = fields.Boolean(default=True)
    fulfillment_type = fields.Selection([
        ('dine_in', 'Dine In'),
        ('takeout', 'Takeout'),
        ('delivery', 'Delivery'),
    ], default='dine_in', required=True)

    done_date = fields.Datetime(string='Completed on')
    prep_duration = fields.Float(
        string='Prep duration (min)', compute='_compute_prep_duration', store=True,
        help='Minutes between the order reaching the kitchen and reaching its last stage.')

    def _compute_table_number(self):
        from ..utils import get_table_number
        for rec in self:
            if rec.table_name:
                rec.table_number = rec.table_name
                continue
            table = rec.pos_order_id.table_id if 'table_id' in rec.pos_order_id._fields else False
            num = get_table_number(table)
            if num:
                rec.table_number = f"T{num}" if str(num).isdigit() else str(num)
            else:
                ref = rec.pos_order_id.pos_reference if rec.pos_order_id else ''
                rec.table_number = ref.split()[-1] if ref else ''

    @api.depends('create_date', 'done_date')
    def _compute_prep_duration(self):
        for rec in self:
            if rec.create_date and rec.done_date:
                rec.prep_duration = round((rec.done_date - rec.create_date).total_seconds() / 60.0, 1)
            else:
                rec.prep_duration = 0.0

    def write(self, vals):
        # Log every stage change for the manager reporting view / audit trail
        if 'stage_id' in vals:
            for order in self:
                if order.stage_id.id != vals['stage_id']:
                    self.env['pos.prep.order.stage.log'].sudo().create({
                        'prep_order_id': order.id,
                        'stage_id': vals['stage_id'],
                    })
        res = super().write(vals)
        if 'stage_id' in vals:
            for order in self:
                stages = order.display_id.stage_ids.sorted('sequence')
                if stages and order.stage_id.id == stages[-1].id and not order.done_date:
                    order.done_date = fields.Datetime.now()
                elif stages and order.stage_id.id != stages[-1].id and order.done_date:
                    order.done_date = False
        return res

    def action_next_stage(self):
        for order in self:
            stages = list(order.display_id.stage_ids.sorted('sequence'))
            if order.stage_id in stages:
                idx = stages.index(order.stage_id)
                if idx + 1 < len(stages):
                    order.write({'stage_id': stages[idx + 1].id})
                    order._notify_display()

    def action_previous_stage(self):
        """Undo: move an order back one stage. Addresses the #1 complaint
        about third-party KDS modules - no way to fix a mis-tap."""
        for order in self:
            stages = list(order.display_id.stage_ids.sorted('sequence'))
            if order.stage_id in stages:
                idx = stages.index(order.stage_id)
                if idx - 1 >= 0:
                    order.write({'stage_id': stages[idx - 1].id})
                    order._notify_display()

    def action_mark_done(self):
        for order in self:
            stages = order.display_id.stage_ids.sorted('sequence')
            last_stage = stages[-1:] if stages else False
            vals = {'active': False}
            if not order.done_date:
                vals['done_date'] = fields.Datetime.now()
            if last_stage and order.stage_id != last_stage:
                vals['stage_id'] = last_stage.id
            order.write(vals)
            order._notify_display()

    def action_recall(self):
        for order in self:
            stages = list(order.display_id.stage_ids.sorted('sequence'))
            vals = {'active': True}
            if order.done_date:
                vals['done_date'] = False
            if stages:
                if order.stage_id in stages:
                    idx = stages.index(order.stage_id)
                    if not order.active:
                        # If order was marked done / cleared, restore it to the last stage (Completed)
                        vals['stage_id'] = stages[-1].id
                    elif idx > 0:
                        # If order was active, undo by moving back one stage
                        vals['stage_id'] = stages[idx - 1].id
                    else:
                        vals['stage_id'] = stages[0].id
                else:
                    vals['stage_id'] = stages[-1].id
            order.write(vals)
            order._notify_display()

    def _notify_display(self):
        """Push a lightweight ping on the display's bus channel so every open
        kitchen screen for that display refreshes near-instantly instead of
        waiting for the next poll. Also pings the customer status page for
        this specific order."""
        for order in self:
            try:
                self.env['bus.bus']._sendone(
                    f'pos_prep_display-{order.display_id.id}', 'pos_prep_order_update', {'order_id': order.id})
                total = len(order.display_id.stage_ids)
                self.env['bus.bus']._sendone(
                    f'pos_prep_order_status-{order.pos_order_id.id}', 'pos_prep_order_status', {
                        'stage_name': order.stage_id.name,
                        'sequence': order.stage_id.sequence,
                        'total_stages': total,
                    })
            except Exception:
                pass  # bus is best-effort; polling is the safety net

    # kept for backwards compatibility with earlier controller code
    def _notify_customer_screen(self):
        self._notify_display()


class PosPrepOrderLine(models.Model):
    _name = 'pos.prep.order.line'
    _description = 'Kitchen Preparation Order Line'

    prep_order_id = fields.Many2one('pos.prep.order', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    name = fields.Char()
    qty = fields.Float(default=1.0)
    note = fields.Char()
    is_done = fields.Boolean(string='Done', default=False)

    def action_toggle_done(self):
        for line in self:
            line.is_done = not line.is_done
            order = line.prep_order_id
            if order and all(l.is_done for l in order.line_ids):
                order.action_next_stage()
                order.line_ids.write({'is_done': False})
            elif order:
                order._notify_display()

    def action_advance_line(self):
        for line in self:
            order = line.prep_order_id
            stages = list(order.display_id.stage_ids.sorted('sequence'))
            if not stages or order.stage_id not in stages:
                continue
            idx = stages.index(order.stage_id)
            if idx + 1 >= len(stages):
                line.is_done = True
                continue
            next_stage = stages[idx + 1]

            if len(order.line_ids) <= 1:
                order.write({'stage_id': next_stage.id})
                line.write({'is_done': False})
                order._notify_display()
                continue

            existing_next = self.env['pos.prep.order'].search([
                ('pos_order_id', '=', order.pos_order_id.id),
                ('display_id', '=', order.display_id.id),
                ('stage_id', '=', next_stage.id),
            ], limit=1)

            if not existing_next:
                existing_next = self.env['pos.prep.order'].create({
                    'pos_order_id': order.pos_order_id.id,
                    'display_id': order.display_id.id,
                    'stage_id': next_stage.id,
                    'table_name': order.table_name,
                    'customer_count': order.customer_count,
                    'fulfillment_type': order.fulfillment_type,
                })

            line.write({
                'prep_order_id': existing_next.id,
                'is_done': False,
            })
            order._notify_display()
            existing_next._notify_display()


class PosPrepOrderStageLog(models.Model):
    _name = 'pos.prep.order.stage.log'
    _description = 'Kitchen Order Stage History (audit trail)'
    _order = 'create_date asc'

    prep_order_id = fields.Many2one('pos.prep.order', required=True, ondelete='cascade')
    stage_id = fields.Many2one('pos.prep.display.stage', required=True)
    display_id = fields.Many2one(related='prep_order_id.display_id', store=True)
