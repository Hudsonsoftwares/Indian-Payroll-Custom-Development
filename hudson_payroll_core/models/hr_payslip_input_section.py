# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrPayslipInputSection(models.Model):
    _name = 'hr.payslip.input.section'
    _description = 'Salary Rule Section'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    input_type_ids = fields.One2many(
        'hr.payslip.input.type',
        'input_section_id',
        string='Input Types'
    )
    struct_ids = fields.Many2many(
        'hr.payroll.structure',
        'hr_payslip_input_section_structure_rel',
        'section_id',
        'struct_id',
        string='Available in Salary Structure',
        help='Salary structures where this section is available'
    )
