# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    journal_id = fields.Many2one(
        'account.journal',
        string='Salary Journal',
        required=True,
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env['account.journal'].search(
            [('type', '=', 'general')], limit=1
        ),
        help="Journal associated with this pay run batch."
    )
    move_count = fields.Integer(
        string='Accounting Entries Count',
        compute='_compute_move_count'
    )

    @api.depends('slip_ids.move_id')
    def _compute_move_count(self):
        for run in self:
            run.move_count = len(run.slip_ids.mapped('move_id'))

    def write(self, vals):
        res = super(HrPayslipRun, self).write(vals)
        # When pay run transitions to paid, ensure moves are created in draft state
        if vals.get('state') == 'paid':
            for run in self:
                for slip in run.slip_ids:
                    if not slip.move_id:
                        slip._create_account_move()
        elif vals.get('state') in ('confirmed', 'close'):
            for run in self:
                for slip in run.slip_ids:
                    if not slip.move_id and slip.state in ('done', 'paid'):
                        slip._create_account_move()
        return res

    def action_open_account_moves(self):
        """Opens all Accounting Entries generated for this pay run batch."""
        self.ensure_one()
        for slip in self.slip_ids:
            if not slip.move_id and slip.state in ('done', 'paid'):
                slip._create_account_move()
        move_ids = self.slip_ids.mapped('move_id').ids
        return {
            'name': _('Accounting Entries - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', move_ids)],
            'context': {'create': False, 'search_default_posted': 0},
        }
