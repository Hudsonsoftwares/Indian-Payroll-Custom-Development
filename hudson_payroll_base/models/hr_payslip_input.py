# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipInputType(models.Model):
    """Configurable external input types (e.g. Overtime, Bonus, Advance Recovery, Deduction)."""
    _name = 'hr.payslip.input.type'
    _description = 'Payslip Input Type'
    _order = 'sequence, id'

    name = fields.Char(string='Description', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    country_id = fields.Many2one('res.country', string='Country')
    input_line_type_ids = fields.Many2many(
        'hr.payroll.structure',
        'hr_payslip_input_type_structure_rel',
        'input_type_id',
        'struct_id',
        string='Applicable Structures'
    )


class HrPayslipInput(models.Model):
    """External input lines fed into a specific payslip for rule calculation."""
    _name = 'hr.payslip.input'
    _description = 'Payslip Input'
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
    sequence = fields.Integer(string='Sequence', default=10, required=True, index=True)
    input_type_id = fields.Many2one(
        'hr.payslip.input.type',
        string='Input Type'
    )
    code = fields.Char(
        string='Code',
        required=True,
        help="Input code that can be referenced in salary rules (e.g. inputs.OVERTIME.amount)"
    )
    amount = fields.Float(
        string='Amount',
        default=0.0,
        help="Amount or monetary value of this input line"
    )
    contract_id = fields.Many2one(
        'hr.version',
        string='Contract',
        help="The contract related to this input"
    )
