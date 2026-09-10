# -*- coding: utf-8 -*-
import logging
from odoo import fields
from odoo.exceptions import ValidationError
from ..base import BaseStatutoryService

from .tds_parameter_service import TdsParameterService
from .salary_projection_service import SalaryProjectionService
from .previous_employer_income_service import PreviousEmployerIncomeService
from .other_income_aggregation_service import OtherIncomeAggregationService
from .regime_routing_service import RegimeRoutingService

_logger = logging.getLogger(__name__)


class AnnualIncomeProjectionResult:
    """
    Data Transfer Object (DTO) holding the complete result of Phase 4 Annual Income Projection
    and Tax Regime Resolution orchestration.
    """
    def __init__(self, employee_id, financial_year_id, regime_code, regime_name,
                 salary_projection, previous_employer_income, other_income_aggregation,
                 projected_annual_salary, gross_total_income, regime_context):
        self.employee_id = employee_id
        self.financial_year_id = financial_year_id
        self.regime_code = regime_code
        self.regime_name = regime_name
        self.salary_projection = salary_projection
        self.previous_employer_income = previous_employer_income
        self.other_income_aggregation = other_income_aggregation
        self.projected_annual_salary = projected_annual_salary
        self.gross_total_income = gross_total_income
        self.regime_context = regime_context

    @property
    def current_employer_salary(self):
        """Current employer projected annual salary."""
        return self.salary_projection.total_projected_current_salary if self.salary_projection else 0.0


class AnnualIncomeProjectionService(BaseStatutoryService):
    """
    Phase 4 Master Orchestration Service: Annual Income Projection & Tax Regime Resolution Engine.
    Orchestrates:
    1. Financial Year Resolution (via TdsParameterService)
    2. Employee Tax Regime Selection Resolution ('old' vs 'new')
    3. Annual Current Salary Projection (via SalaryProjectionService)
    4. Previous Employer Income Aggregation (via PreviousEmployerIncomeService)
    5. Non-Payroll Other Income Aggregation (via OtherIncomeAggregationService)
    6. Gross Total Income (GTI) Aggregation
    7. Regime Context Routing Pipeline (via RegimeRoutingService)
    """

    def resolve_employee_regime(self, employee, financial_year):
        """
        Resolves the employee's selected Tax Regime for the specified Financial Year.
        Selected regime is retrieved from the authoritative tds.employee.tax.regime record,
        with fallback to tds.employee.declaration header if master record is absent.
        """
        decl_rec = self.env['tds.employee.declaration'].sudo().search([
            ('employee_id', '=', employee.id),
            ('financial_year_id', '=', financial_year.id)
        ], limit=1)
        ui_regime = decl_rec.tax_regime_id.code if (decl_rec and decl_rec.tax_regime_id) else 'None'

        regime_rec = self.env['tds.employee.tax.regime'].sudo().search([
            ('employee_id', '=', employee.id),
            ('financial_year_id', '=', financial_year.id)
        ], limit=1)

        found_master = bool(regime_rec and regime_rec.regime_id)
        regime_rec_id = regime_rec.id if found_master else 'None'
        
        reason_default = "N/A"
        if found_master:
            resolved_code = regime_rec.regime_id.code.lower()
            resolved_name = regime_rec.regime_id.name
        elif decl_rec and decl_rec.tax_regime_id:
            # Fallback to UI declaration header regime choice if master record absent
            resolved_code = decl_rec.tax_regime_id.code.lower()
            resolved_name = decl_rec.tax_regime_id.name
            reason_default = "Fallback to Declaration Header regime choice because tds.employee.tax.regime master record was un-synchronized."
        else:
            default_regime = self.env['tds.tax.regime'].search([('code', '=', 'new')], limit=1)
            resolved_code = 'new'
            resolved_name = default_regime.name if default_regime else 'New Tax Regime (Section 115BAC)'
            reason_default = "No tds.employee.tax.regime master record OR tds.employee.declaration header choice found for (employee_id, financial_year_id); applying Income Tax Act Section 115BAC statutory default."

        _logger.info(
            "\n==================================================\n"
            "REGIME RESOLUTION TRACE\n"
            "==================================================\n"
            "Employee ID                           : %s (%s)\n"
            "Financial Year                        : %s (ID: %s)\n"
            "Declaration ID                        : %s\n"
            "UI Selected Regime                    : %s\n"
            "tds.employee.tax.regime record found? : %s\n"
            "Regime Record ID                      : %s\n"
            "Resolved Regime Code                  : %s\n"
            "Reason for defaulting to NEW          : %s\n"
            "==================================================",
            employee.id if employee else 'N/A', employee.name if employee else 'N/A',
            financial_year.name if financial_year else 'N/A', financial_year.id if financial_year else 'N/A',
            decl_rec.id if decl_rec else 'None',
            ui_regime,
            found_master,
            regime_rec_id,
            resolved_code.upper(),
            reason_default
        )

        return resolved_code, resolved_name

    def project_annual_income(self, employee, eval_date=None):
        """
        Master orchestration method for Phase 4 Annual Income Projection.

        :param employee: hr.employee record
        :param eval_date: Date (optional evaluation date)
        :return: AnnualIncomeProjectionResult
        """
        if not employee:
            raise ValidationError("Annual Income Projection Error: Employee record is required.")

        eval_date = eval_date or fields.Date.today()
        tds_param_svc = TdsParameterService(self.env)

        # 1. Resolve Financial Year (raises ValidationError if unconfigured)
        financial_year = tds_param_svc.get_financial_year(eval_date=eval_date)
        if not financial_year:
            raise ValidationError(f"Annual Income Projection Error: No active Financial Year found for date {eval_date}.")

        # 2. Resolve Employee Selected Tax Regime
        regime_code, regime_name = self.resolve_employee_regime(employee, financial_year)

        # 3. Project Current Employer Salary via PayrollIncomeProjectionService / SalaryProjectionService
        salary_svc = SalaryProjectionService(self.env)
        salary_proj = salary_svc.project_salary(employee, financial_year, eval_date=eval_date)

        # 4. Aggregate Previous Employer Income
        prev_emp_svc = PreviousEmployerIncomeService(self.env)
        prev_emp_inc = prev_emp_svc.aggregate_previous_employer_income(employee, financial_year)

        # 5. Aggregate Other Non-Payroll Income (Regime-aware HP loss set-off)
        other_inc_svc = OtherIncomeAggregationService(self.env)
        other_inc_agg = other_inc_svc.aggregate_other_income(employee, financial_year, regime_code=regime_code, eval_date=eval_date)

        # 6. Aggregate Projected Annual Salary & Gross Total Income (GTI)
        current_employer_income = salary_proj.total_projected_current_salary
        prev_emp_income = prev_emp_inc.taxable_salary
        other_income_val = other_inc_agg.total_other_income

        projected_annual_salary = current_employer_income + prev_emp_income
        gross_total_income = projected_annual_salary + other_income_val

        summary_log = f"""
========================================================
ANNUAL INCOME PROJECTION SERVICE
========================================================
Regime Code               : {regime_code.upper()} ({regime_name})
Current Employer Salary   : ₹{current_employer_income:,.2f}
Previous Employer Income  : ₹{prev_emp_income:,.2f}
Projected Annual Salary   : ₹{projected_annual_salary:,.2f}
Other Sources Income      : ₹{other_inc_agg.total_other_sources:,.2f}
Raw HP Net Income/Loss    : ₹{other_inc_agg.net_house_property_income_loss:,.2f}
Applicable HP Loss Limit  : ₹{other_inc_agg.hp_loss_limit:,.2f}
Allowed HP Loss Set-Off   : ₹{other_inc_agg.allowed_hp_loss_set_off:,.2f}
Effective HP Impact on GTI: ₹{other_inc_agg.effective_hp_gti_impact:,.2f}
Total Other Income        : ₹{other_income_val:,.2f}
Gross Total Income (GTI)  : ₹{gross_total_income:,.2f}

Formula:
Projected Annual Salary = Current Employer Salary + Previous Employer Income
Other Income = Other Sources + Effective HP Impact
GTI = Projected Annual Salary + Other Income
========================================================
"""
        _logger.warning(summary_log)

        # 7. Prepare Regime Routing Calculation Context Pipeline
        routing_svc = RegimeRoutingService(self.env)
        regime_context = routing_svc.prepare_regime_context(
            employee=employee,
            financial_year=financial_year,
            regime_code=regime_code,
            gross_total_income=gross_total_income,
            eval_date=eval_date
        )

        return AnnualIncomeProjectionResult(
            employee_id=employee.id,
            financial_year_id=financial_year.id,
            regime_code=regime_code,
            regime_name=regime_name,
            salary_projection=salary_proj,
            previous_employer_income=prev_emp_inc,
            other_income_aggregation=other_inc_agg,
            projected_annual_salary=projected_annual_salary,
            gross_total_income=gross_total_income,
            regime_context=regime_context
        )
