# -*- coding: utf-8 -*-
import logging
from ..base import BaseStatutoryService

_logger = logging.getLogger(__name__)


class PreviousEmployerIncomeResult:
    """
    Data Transfer Object (DTO) holding aggregated Previous Employer income and tax details.
    """
    def __init__(self, taxable_salary=0.0, tds_deducted=0.0, pt_deducted=0.0, pf_contributed=0.0, has_declaration=False):
        self.taxable_salary = taxable_salary
        self.tds_deducted = tds_deducted
        self.pt_deducted = pt_deducted
        self.pf_contributed = pf_contributed
        self.has_declaration = has_declaration


class PreviousEmployerIncomeService(BaseStatutoryService):
    """
    Phase 4 Service: Previous Employer Income Aggregation Service.
    Aggregates taxable salary, TDS deducted, Professional Tax, and EPF from previous employers
    declared via Form 12B / Income Declaration for mid-year joiners.
    """

    def aggregate_previous_employer_income(self, employee, financial_year):
        """
        Aggregates previous employer income for the employee in the specified Financial Year.

        :param employee: hr.employee record
        :param financial_year: tds.financial.year record
        :return: PreviousEmployerIncomeResult
        """
        inc_decl = self.env['tds.employee.income.declaration'].sudo().search([
            ('employee_id', '=', employee.id),
            ('financial_year_id', '=', financial_year.id),
        ], limit=1)

        if not inc_decl:
            return PreviousEmployerIncomeResult(has_declaration=False)

        return PreviousEmployerIncomeResult(
            taxable_salary=inc_decl.prev_employer_taxable_gross or 0.0,
            tds_deducted=inc_decl.prev_employer_tds or 0.0,
            pt_deducted=inc_decl.prev_employer_pt or 0.0,
            pf_contributed=inc_decl.prev_employer_pf or 0.0,
            has_declaration=True
        )
