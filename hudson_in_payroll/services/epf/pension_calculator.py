# -*- coding: utf-8 -*-
from odoo import fields
from ..base import BaseStatutoryService


class EPFPensionCalculator(BaseStatutoryService):
    """Calculates Employer Pension Scheme (EPS) Contribution."""

    def __init__(self, env, wage_calc):
        super().__init__(env)
        self.wage_calc = wage_calc

    def compute(self, payslip):
        employee = payslip.employee_id
        if not employee.hds_in_epf_applicable or not employee.hds_in_eps_applicable:
            return 0.0

        eval_date = payslip.date_to or fields.Date.today()

        # Age > 58 Check: Pension contribution ceases at age 58
        if employee.birthday:
            age = self.calculate_age(employee.birthday, eval_date)
            if age >= 58:
                return 0.0

        pf_wage = self.wage_calc.get_pf_contribution_wage(payslip)
        eps_rate = self.get_pf_parameter('hds_in_eps_rate', date=eval_date, as_decimal=True)

        if employee.hds_in_higher_pension or employee.hds_in_is_international_worker:
            eps_wage = self.wage_calc.get_actual_pf_wage(payslip)
        else:
            eps_ceiling = self.get_pf_parameter('hds_in_eps_wage_ceiling', date=eval_date)
            eps_wage = min(self.wage_calc.get_actual_pf_wage(payslip), eps_ceiling)

        if eps_wage <= 0.0:
            return 0.0

        return self.round_statutory(eps_wage * eps_rate)
