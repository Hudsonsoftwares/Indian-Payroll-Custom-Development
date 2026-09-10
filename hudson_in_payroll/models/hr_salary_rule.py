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
    hds_in_is_bonus = fields.Boolean(
        string="Is Bonus",
        default=False,
        help="If checked, this salary rule is treated as a bonus component with configurable eligibility and tax rules."
    )
    hds_in_exclude_notice_period = fields.Boolean(
        string="Exclude Notice Period",
        default=True,
        help="If checked, employees currently serving notice period or with approved resignation will not receive this bonus."
    )
    hds_in_apply_tds = fields.Boolean(
        string="Apply TDS",
        default=True,
        help="If checked, this bonus will be included in taxable income and subject to TDS calculation."
    )


