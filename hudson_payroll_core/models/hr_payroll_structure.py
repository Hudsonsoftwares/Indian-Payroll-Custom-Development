# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    type_id = fields.Many2one(
        'hr.payroll.structure.type',
        string='Structure Type',
        help='Salary Structure Type category for this structure'
    )
    input_type_ids = fields.Many2many(
        'hr.payslip.input.type',
        'hr_payslip_input_type_structure_rel',
        'struct_id',
        'input_type_id',
        string='Salary Input Types',
        help='Salary input types available in this salary structure'
    )
