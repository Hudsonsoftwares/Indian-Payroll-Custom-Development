# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrPayslipInputType(models.Model):
    _name = 'hr.payslip.input.type'
    _description = 'Salary Input Type'
    _order = 'sequence, name'

    name = fields.Char(string='Description', required=True)
    code = fields.Char(string='Code', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    struct_ids = fields.Many2many(
        'hr.payroll.structure',
        'hr_payslip_input_type_structure_rel',
        'input_type_id',
        'struct_id',
        string='Availability in Structure',
        help='Salary structures this input type can be used in (leave empty to inherit from section)'
    )
    input_section_id = fields.Many2one(
        'hr.payslip.input.section',
        string='Section'
    )
    effective_struct_ids = fields.Many2many(
        'hr.payroll.structure',
        'hr_payslip_input_type_effective_structure_rel',
        'input_type_id',
        'struct_id',
        string='Effective Availability',
        compute='_compute_effective_struct_ids',
        store=True,
        help='Effective salary structures (uses explicit Availability in Structure if set, otherwise inherits from Section)'
    )
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.company.country_id
    )
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The code of the salary input type must be unique!')
    ]

    @api.depends('struct_ids', 'input_section_id', 'input_section_id.struct_ids')
    def _compute_effective_struct_ids(self):
        for rec in self:
            rec.effective_struct_ids = rec.struct_ids if rec.struct_ids else rec.input_section_id.struct_ids
