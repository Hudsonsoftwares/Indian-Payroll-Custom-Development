# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipWorkedDays(models.Model):
    """Worked Days records for tracking attendance, leaves, and payable time during a payslip period."""
    _name = 'hr.payslip.worked.days'
    _description = 'Payslip Worked Days'
    _order = 'payslip_id, sequence'

    name = fields.Char(string='Description', required=True)
    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Pay Slip',
        required=True,
        ondelete='cascade',
        index=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        related='payslip_id.employee_id',
        store=True,
        readonly=True,
        index=True
    )
    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Pay Run',
        related='payslip_id.payslip_run_id',
        store=True,
        readonly=True,
        index=True
    )
    sequence = fields.Integer(string='Sequence', default=10, required=True, index=True)
    code = fields.Char(
        string='Code',
        required=True,
        help="The code that can be referenced in salary rules (e.g. WORK100, LEAVE100, LOP)"
    )
    number_of_days = fields.Float(string='Number of Days', default=0.0)
    number_of_hours = fields.Float(string='Number of Hours', default=0.0)
    currency_id = fields.Many2one(
        related='payslip_id.currency_id',
        string='Currency',
        readonly=True
    )
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        default=0.0,
        help="Monetary amount associated with this worked days category."
    )
    contract_id = fields.Many2one(
        'hr.version',
        string='Contract',
        help="The contract for which the worked days are computed"
    )
