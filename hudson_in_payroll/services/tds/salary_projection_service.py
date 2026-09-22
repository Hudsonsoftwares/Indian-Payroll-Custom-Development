# -*- coding: utf-8 -*-
import logging
# pyrefly: ignore [missing-import]
from odoo import fields
from ..base import BaseStatutoryService
from .payroll_period_service import PayrollPeriodService
_logger = logging.getLogger(__name__)


class SalaryProjectionResult:
    """
    Data Transfer Object (DTO) holding projected current employer salary details.
    """
    def __init__(self, ytd_basic=0.0, projected_basic=0.0, total_basic=0.0,
                 ytd_da=0.0, projected_da=0.0, total_da=0.0,
                 ytd_hra=0.0, projected_hra=0.0, total_hra=0.0,
                 ytd_bonus=0.0, projected_bonus=0.0, total_bonus=0.0,
                 ytd_allowances=0.0, projected_allowances=0.0, total_allowances=0.0,
                 months_elapsed=0, months_remaining=0, total_projected_current_salary=0.0,
                 ytd_lta=0.0, projected_lta=0.0, total_lta=0.0):
        self.ytd_basic = ytd_basic
        self.projected_basic = projected_basic
        self.total_basic = total_basic
        self.ytd_da = ytd_da
        self.projected_da = projected_da
        self.total_da = total_da
        self.ytd_hra = ytd_hra
        self.projected_hra = projected_hra
        self.total_hra = total_hra
        self.ytd_bonus = ytd_bonus
        self.projected_bonus = projected_bonus
        self.total_bonus = total_bonus
        self.ytd_allowances = ytd_allowances
        self.projected_allowances = projected_allowances
        self.total_allowances = total_allowances
        self.months_elapsed = months_elapsed
        self.months_remaining = months_remaining
        self.total_projected_current_salary = total_projected_current_salary
        self.ytd_lta = ytd_lta
        self.projected_lta = projected_lta
        self.total_lta = total_lta


class SalaryProjectionService(BaseStatutoryService):
    """
    Phase 4 Service: Annual Salary Projection Service.
    Projects an employee's annual taxable earnings from current employer payroll
    by aggregating Year-To-Date (YTD) paid payslips and projecting remaining months in the Financial Year.
    """

    def _get_employee_contract(self, employee):
        if not employee:
            return False
        if hasattr(employee, 'contract_id') and employee.contract_id:
            return employee.contract_id
        if hasattr(employee, 'contract_ids') and employee.contract_ids:
            open_contracts = employee.contract_ids.filtered(lambda c: getattr(c, 'state', False) == 'open')
            if open_contracts:
                return open_contracts[0]
            if len(employee.contract_ids) > 0:
                return employee.contract_ids[0]

        # Dynamically inspect and query contract models ('hr.version' and 'hr.contract')
        for model_name in ('hr.version', 'hr.contract'):
            if model_name in self.env:
                ContractModel = self.env[model_name]
                fields_keys = ContractModel._fields.keys()

                _logger.warning("Target contract model '%s' available fields: %s", model_name, list(fields_keys))

                if 'employee_id' not in fields_keys:
                    continue

                base_domain = [('employee_id', '=', employee.id)]

                # Check state / status filter only if field exists on model
                if 'state' in fields_keys:
                    open_contracts = ContractModel.search(base_domain + [('state', '=', 'open')], limit=1)
                    if open_contracts:
                        return open_contracts
                elif 'status' in fields_keys:
                    open_contracts = ContractModel.search(base_domain + [('status', '=', 'open')], limit=1)
                    if open_contracts:
                        return open_contracts

                # Check active filter only if field exists on model
                if 'active' in fields_keys:
                    active_contracts = ContractModel.search(base_domain + [('active', '=', True)], limit=1)
                    if active_contracts:
                        return active_contracts

                all_contracts = ContractModel.search(base_domain, limit=1)
                if all_contracts:
                    return all_contracts

        return False


    def project_salary(self, employee, financial_year, eval_date=None):
        """
        Calculates Year-To-Date (YTD) salary earnings and projects remaining months' earnings.

        :param employee: hr.employee record
        :param financial_year: tds.financial.year record
        :param eval_date: Date (optional)
        :return: SalaryProjectionResult
        """
        eval_date = eval_date or fields.Date.today()
        if isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)

        fy_start = financial_year.start_date
        fy_end = financial_year.end_date

        # Determine remaining payroll periods dynamically via PayrollPeriodService
        # NOTE:
        # - Projection Months (salary_projection_months) is used ONLY to estimate projected annual income.
        # - Remaining Payroll Periods (remaining_periods) is used ONLY inside MonthlyTDSDistributionService to distribute remaining TDS liability.
        period_svc = PayrollPeriodService(self.env)
        total_fy_months = period_svc.calculate_total_periods_in_fy(employee, financial_year, eval_date=eval_date)
        remaining_periods = period_svc.calculate_remaining_periods(employee, financial_year, eval_date=eval_date)

        # Query paid/confirmed PRIOR payslips for current FY on or before eval_date.
        # Must filter ('date_to', '<=', eval_date) so that future payslips in the FY
        # are NOT included when calculating YTD earnings and remaining projection months.
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '>=', fy_start),
            ('date_to', '<=', eval_date),
            ('state', 'in', ['done', 'paid'])
        ])

        paid_months_count = len(payslips)
        # Dynamic projection months based on total employment months in FY minus already paid months
        salary_projection_months = max(0, total_fy_months - paid_months_count)

        if eval_date < fy_start:
            months_elapsed = 0
            months_remaining = total_fy_months
        elif eval_date > fy_end:
            months_elapsed = total_fy_months
            months_remaining = 0
        else:
            fy_start_year = fy_start.year
            fy_start_month = fy_start.month
            eval_year = eval_date.year
            eval_month = eval_date.month

            joining_date = period_svc._resolve_employee_joining_date(employee)
            if joining_date and joining_date > fy_start:
                join_elapsed = (joining_date.year - fy_start_year) * 12 + (joining_date.month - fy_start_month) + 1
                join_fy_idx = min(12, max(1, join_elapsed))
            else:
                join_fy_idx = 1

            if join_fy_idx == 1 and employee and financial_year:
                from .previous_employer_income_service import PreviousEmployerIncomeService
                prev_svc = PreviousEmployerIncomeService(self.env)
                prev_res = prev_svc.aggregate_previous_employer_income(employee, financial_year)
                if prev_res.has_declaration and (prev_res.taxable_salary > 0 or prev_res.tds_deducted > 0):
                    earliest_slip = self.env['hr.payslip'].search([
                        ('employee_id', '=', employee.id),
                        ('date_from', '>=', fy_start),
                        ('date_to', '<=', fy_end)
                    ], order='date_from asc', limit=1)
                    if earliest_slip and earliest_slip.date_from:
                        s_date = fields.Date.from_string(earliest_slip.date_from)
                        join_elapsed = (s_date.year - fy_start_year) * 12 + (s_date.month - fy_start_month) + 1
                        join_fy_idx = min(12, max(1, join_elapsed))
                    else:
                        elapsed_for_join = (eval_year - fy_start_year) * 12 + (eval_month - fy_start_month) + 1
                        join_fy_idx = min(12, max(1, elapsed_for_join))

            elapsed_months = (eval_year - fy_start_year) * 12 + (eval_month - fy_start_month) + 1
            eval_fy_idx = min(12, max(1, elapsed_months))

            if eval_fy_idx < join_fy_idx:
                months_elapsed = 0
                months_remaining = total_fy_months
            else:
                months_elapsed = eval_fy_idx - join_fy_idx + 1
                months_remaining = max(0, total_fy_months - months_elapsed)

        ytd_basic = 0.0
        ytd_da = 0.0
        ytd_hra = 0.0
        ytd_bonus = 0.0
        ytd_lta = 0.0
        ytd_allowances = 0.0

        # Explicitly defined summary rule codes and categories to exclude from YTD component aggregation
        EXCLUDED_SUMMARY_CODES = {'GROSS', 'NET', 'PF_WAGE', 'TOTAL', 'ESIC_WAGE', 'EPF_ADMIN', 'EDLI_ADMIN', 'ESI_WAGE'}
        EXCLUDED_SUMMARY_CATEGORIES = {'GROSS', 'NET', 'COMP', 'DED'}

        for slip in payslips:
            for line in slip.line_ids:
                code = (line.code or '').upper()
                cat_code = (line.category_id.code or '').upper() if line.category_id else ''
                amt = line.total or 0.0

                # 1. Skip summary rules and non-earning category lines
                if cat_code in EXCLUDED_SUMMARY_CATEGORIES or code in EXCLUDED_SUMMARY_CODES:
                    continue

                # 2. Accumulate specific earning components
                if code in ('BASIC', 'BASIC_PAY'):
                    ytd_basic += amt
                elif code in ('DA', 'DEARNESS_ALLOWANCE'):
                    ytd_da += amt
                elif code in ('HRA', 'HOUSE_RENT_ALLOWANCE'):
                    ytd_hra += amt
                elif code in ('LTA', 'LEAVE_TRAVEL_ALLOWANCE', 'LEAVE_TRAVEL_ASSISTANCE'):
                    ytd_lta += amt
                elif code in ('BONUS', 'INCENTIVE', 'COMMISSION', 'OVERTIME', 'ARREARS', 'PERF_BONUS', 'RETENTION_BONUS'):
                    ytd_bonus += amt
                elif cat_code in ('ALW', 'ALLOWANCE') or cat_code.startswith('ALW'):
                    ytd_allowances += amt
                else:
                    # Generic fallback for any other earning allowance line
                    ytd_allowances += amt

        # Contract / Monthly Wage structure for remaining months projection
        contract = self._get_employee_contract(employee)

        contract_wage = float(contract.wage or 0.0) if contract else 0.0

        contract_basic = float(getattr(contract, 'basic_salary', 0.0) or 0.0) if contract else 0.0
        contract_da = float(getattr(contract, 'da', 0.0) or getattr(contract, 'da_amount', 0.0) or 0.0) if contract else 0.0
        contract_hra = float(getattr(contract, 'hra', 0.0) or getattr(contract, 'hra_amount', 0.0) or 0.0) if contract else 0.0
        contract_lta = float(getattr(contract, 'lta', 0.0) or getattr(contract, 'lta_amount', 0.0) or getattr(contract, 'leave_travel_allowance', 0.0) or 0.0) if contract else 0.0

        contract_other_allowances = 0.0
        if contract:
            contract_other_allowances = sum([
                float(getattr(contract, f, 0.0) or 0.0)
                for f in ('travel_allowance', 'meal_allowance', 'medical_allowance', 'other_allowance', 'fixed_allowance', 'performance_bonus', 'retention_bonus')
            ])

        if contract_basic > 0.0:
            monthly_basic = contract_basic
            monthly_da = contract_da or (ytd_da / months_elapsed if months_elapsed > 0 else 0.0)
            monthly_hra = contract_hra or (ytd_hra / months_elapsed if months_elapsed > 0 else 0.0)
            monthly_lta = contract_lta or (ytd_lta / months_elapsed if months_elapsed > 0 else 0.0)
            monthly_allowances = contract_other_allowances or max(0.0, contract_wage - (monthly_basic + monthly_da + monthly_hra + monthly_lta)) or (ytd_allowances / months_elapsed if months_elapsed > 0 else 0.0)
        else:
            monthly_basic = contract_wage or (ytd_basic / months_elapsed if months_elapsed > 0 else 0.0)
            monthly_da = contract_da or (ytd_da / months_elapsed if months_elapsed > 0 else 0.0)
            monthly_hra = contract_hra or (ytd_hra / months_elapsed if months_elapsed > 0 else 0.0)
            monthly_lta = contract_lta or (ytd_lta / months_elapsed if months_elapsed > 0 else 0.0)
            monthly_allowances = contract_other_allowances or (ytd_allowances / months_elapsed if months_elapsed > 0 else 0.0)

        monthly_gross = monthly_basic + monthly_hra + monthly_da + monthly_lta + monthly_allowances

        projected_basic = monthly_basic * salary_projection_months
        projected_da = monthly_da * salary_projection_months
        projected_hra = monthly_hra * salary_projection_months
        projected_lta = monthly_lta * salary_projection_months
        projected_bonus = 0.0  # Bonuses are non-recurring unless already paid
        projected_allowances = monthly_allowances * salary_projection_months

        total_basic = ytd_basic + projected_basic
        total_da = ytd_da + projected_da
        total_hra = ytd_hra + projected_hra
        total_lta = ytd_lta + projected_lta
        total_bonus = ytd_bonus + projected_bonus
        total_allowances = ytd_allowances + projected_allowances

        total_projected_current_salary = total_basic + total_da + total_hra + total_lta + total_bonus + total_allowances

        previous_salary_val = ytd_basic + ytd_da + ytd_hra + ytd_lta + ytd_bonus + ytd_allowances
        remaining_projected_val = projected_basic + projected_da + projected_hra + projected_lta + projected_bonus + projected_allowances

        _logger.warning("""[FORENSIC_TDS_TRACE]
step=SALARY_PROJECTION
eval_date=%s
eval_month=%s
input=employee_id:%s, fy:%s, paid_payslips_count:%s, contract_monthly_gross:INR %s
output=ytd_salary:INR %s, projected_salary:INR %s, total_annual_projected_salary:INR %s, projection_months_remaining:%s
source_method=SalaryProjectionService.project_salary
branch_used=%s""",
            eval_date,
            eval_date.strftime('%B') if hasattr(eval_date, 'strftime') else 'N/A',
            employee.id if employee else 'N/A',
            financial_year.code if financial_year else 'N/A',
            paid_months_count,
            f"{monthly_gross:,.2f}",
            f"{previous_salary_val:,.2f}",
            f"{remaining_projected_val:,.2f}",
            f"{total_projected_current_salary:,.2f}",
            salary_projection_months,
            f"HISTORICAL_YTD_PLUS_CONTRACT_PROJECTION (YTD Payslips: {paid_months_count}, Remaining Months: {salary_projection_months})"
        )

        eval_date_str = eval_date.strftime('%d-%b-%Y') if hasattr(eval_date, 'strftime') else str(eval_date)
        fy_name = financial_year.code or financial_year.name

        summary_log = f"""
========================================================
SALARY PROJECTION SUMMARY
========================================================
Financial Year             : {fy_name}
Evaluation Date            : {eval_date_str}

Monthly Gross Salary       : ₹{monthly_gross:,.2f}

Calendar Months Elapsed    : {months_elapsed}
Paid Payslip Months        : {paid_months_count}
Projection Months          : {salary_projection_months}
Remaining Payroll Periods  : {remaining_periods}

Projected Annual Salary    : ₹{total_projected_current_salary:,.2f}
Projected Annual LTA       : ₹{total_lta:,.2f}
========================================================
"""
        _logger.warning(summary_log)

        return SalaryProjectionResult(
            ytd_basic=ytd_basic,
            projected_basic=projected_basic,
            total_basic=total_basic,
            ytd_da=ytd_da,
            projected_da=projected_da,
            total_da=total_da,
            ytd_hra=ytd_hra,
            projected_hra=projected_hra,
            total_hra=total_hra,
            ytd_bonus=ytd_bonus,
            projected_bonus=projected_bonus,
            total_bonus=total_bonus,
            ytd_allowances=ytd_allowances,
            projected_allowances=projected_allowances,
            total_allowances=total_allowances,
            months_elapsed=months_elapsed,
            months_remaining=salary_projection_months,
            total_projected_current_salary=total_projected_current_salary,
            ytd_lta=ytd_lta,
            projected_lta=projected_lta,
            total_lta=total_lta
        )
