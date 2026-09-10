# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    hds_in_include_in_pf_wage = fields.Boolean(
        string="Include in PF Wage",
        default=False,
        help="If enabled, the calculated amount of this salary rule is included when determining the employee's PF-eligible wage."
    )
    hds_in_contributes_to_employer_cost = fields.Boolean(
        string="Contributes to Employer Cost",
        default=False,
        help="If checked, this salary rule amount will be included in the calculation of Employer Cost to Company (CTC)."
    )


