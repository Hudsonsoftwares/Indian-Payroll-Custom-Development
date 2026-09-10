# -*- coding: utf-8 -*-
import logging
from odoo import fields
from odoo.exceptions import ValidationError
from ..base import BaseStatutoryService

_logger = logging.getLogger(__name__)


class PayrollIncomeProjectionResult:
    """
    Data Transfer Object (DTO) holding projected current employer payroll earnings breakdown.
    """
    def __init__(self, ytd_paid_earnings=0.0, projected_remaining_earnings=0.0,
                 total_projected_payroll=0.0, months_elapsed=0, months_remaining=0,
                 earnings_breakdown=None):
        self.ytd_paid_earnings = ytd_paid_earnings
        self.projected_remaining_earnings = projected_remaining_earnings
        self.total_projected_payroll = total_projected_payroll
        self.months_elapsed = months_elapsed
        self.months_remaining = months_remaining
        self.earnings_breakdown = earnings_breakdown or {}


class PayrollIncomeProjectionService(BaseStatutoryService):
    """
    Phase 4 Service: Payroll Income Projection Service.
    Projects an employee's annual taxable earnings from current employer payroll
    by aggregating Year-To-Date (YTD) paid payslip rule outputs and projecting remaining months in the Financial Year.
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
            return employee.contract_ids[0]
        
        ContractModel = self.env.get('hr.version') or self.env.get('hr.contract')
        if ContractModel is not None:
            open_contracts = ContractModel.search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open')
            ], limit=1)
            if open_contracts:
                return open_contracts
            return ContractModel.search([('employee_id', '=', employee.id)], limit=1)
        return False


    def project_payroll_income(self, employee, financial_year, eval_date=None):

        """
        Projects annual payroll earnings for the employee across the Financial Year.


        :param employee: hr.employee record
        :param financial_year: tds.financial.year record
        :param eval_date: Date (optional)
        :return: PayrollIncomeProjectionResult
        """
        if not employee:
            raise ValidationError("Payroll Income Projection Error: Employee record is required.")
        if not financial_year:
            raise ValidationError("Payroll Income Projection Error: Financial Year record is required.")

        eval_date = eval_date or fields.Date.today()
        if isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)

        fy_start = financial_year.start_date
        fy_end = financial_year.end_date

        # Determine elapsed and remaining months in the Financial Year (April = 1, March = 12)
        if eval_date < fy_start:
            months_remaining = 12
            months_elapsed = 0
        elif eval_date > fy_end:
            months_remaining = 0
            months_elapsed = 12
        else:
            fy_start_year = fy_start.year
            fy_start_month = fy_start.month
            eval_year = eval_date.year
            eval_month = eval_date.month

            elapsed = (eval_year - fy_start_year) * 12 + (eval_month - fy_start_month) + 1
            months_elapsed = min(12, max(1, elapsed))
            months_remaining = max(0, 12 - months_elapsed)

        # Query confirmed/paid payslips for current FY
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '>=', fy_start),
            ('date_to', '<=', fy_end),
            ('state', 'in', ['done', 'paid'])
        ])

        ytd_paid_earnings = 0.0
        earnings_breakdown = {
            'basic': 0.0,
            'da': 0.0,
            'hra': 0.0,
            'special_allowance': 0.0,
            'bonus_incentives': 0.0,
            'other_allowances': 0.0,
        }

        for slip in payslips:
            for line in slip.line_ids:
                code = (line.code or '').upper()
                amt = line.total or 0.0
                cat_code = (line.category_id.code or '').upper() if line.category_id else ''

                # Aggregate taxable earnings rules (BASIC, ALW, GROSS categories)
                if cat_code in ('BASIC', 'ALW', 'GROSS'):
                    if code in ('BASIC', 'BASIC_PAY'):
                        earnings_breakdown['basic'] += amt
                    elif code in ('DA', 'DEARNESS_ALLOWANCE'):
                        earnings_breakdown['da'] += amt
                    elif code in ('HRA', 'HOUSE_RENT_ALLOWANCE'):
                        earnings_breakdown['hra'] += amt
                    elif code in ('SPL_ALW', 'SPECIAL_ALLOWANCE'):
                        earnings_breakdown['special_allowance'] += amt
                    elif code in ('BONUS', 'INCENTIVE', 'COMMISSION', 'OVERTIME', 'ARREARS'):
                        earnings_breakdown['bonus_incentives'] += amt
                    elif code not in ('GROSS', 'NET'):
                        earnings_breakdown['other_allowances'] += amt

                    ytd_paid_earnings += amt

        # Contract / Monthly wage structure for remaining months projection
        contract = self._get_employee_contract(employee)


        monthly_base_wage = contract.wage if contract else 0.0
        if monthly_base_wage <= 0 and months_elapsed > 0:
            monthly_base_wage = ytd_paid_earnings / months_elapsed

        monthly_hra = (contract.hra_amount if hasattr(contract, 'hra_amount') else 0.0) or (earnings_breakdown['hra'] / months_elapsed if months_elapsed > 0 else 0.0)
        monthly_da = (contract.da_amount if hasattr(contract, 'da_amount') else 0.0) or (earnings_breakdown['da'] / months_elapsed if months_elapsed > 0 else 0.0)
        monthly_other = (earnings_breakdown['other_allowances'] / months_elapsed) if months_elapsed > 0 else 0.0

        projected_remaining_earnings = (monthly_base_wage + monthly_hra + monthly_da + monthly_other) * months_remaining
        total_projected_payroll = ytd_paid_earnings + projected_remaining_earnings

        return PayrollIncomeProjectionResult(
            ytd_paid_earnings=ytd_paid_earnings,
            projected_remaining_earnings=projected_remaining_earnings,
            total_projected_payroll=total_projected_payroll,
            months_elapsed=months_elapsed,
            months_remaining=months_remaining,
            earnings_breakdown=earnings_breakdown
        )
