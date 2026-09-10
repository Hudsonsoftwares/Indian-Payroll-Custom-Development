# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    gross_amount = fields.Float(
        string='Gross Pay',
        compute='_compute_payslip_totals',
        store=True,
        digits='Payroll',
        help="Total gross salary amount computed from payslip lines"
    )
    net_amount = fields.Float(
        string='Net Pay',
        compute='_compute_payslip_totals',
        store=True,
        digits='Payroll',
        help="Total net salary amount computed from payslip lines"
    )

    @api.depends('line_ids.total', 'line_ids.code', 'line_ids.category_id.code')
    def _compute_payslip_totals(self):
        for payslip in self:
            gross = 0.0
            net = 0.0
            gross_lines = payslip.line_ids.filtered(
                lambda l: l.code == 'GROSS' or (l.category_id and l.category_id.code == 'GROSS')
            )
            net_lines = payslip.line_ids.filtered(
                lambda l: l.code == 'NET' or (l.category_id and l.category_id.code == 'NET')
            )

            if gross_lines:
                gross = sum(gross_lines.mapped('total'))
            else:
                # Fallback: sum of positive lines if no explicit GROSS category line
                gross = sum(payslip.line_ids.filtered(lambda l: l.total > 0).mapped('total'))

            if net_lines:
                net = sum(net_lines.mapped('total'))
            else:
                # Fallback: gross if no explicit NET rule code found
                net = gross

            payslip.gross_amount = gross
            payslip.net_amount = net
