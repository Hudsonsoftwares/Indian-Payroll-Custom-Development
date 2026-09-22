# -*- coding: utf-8 -*-
import logging
from odoo import fields
from ..base import BaseStatutoryService

_logger = logging.getLogger(__name__)


class PayrollPeriodService(BaseStatutoryService):
    """
    Phase 10 Service: Payroll Period Service.
    Dynamically determines the remaining payroll periods in the Financial Year (including current evaluation month).
    Supports:
    - Standard Financial Year (12 monthly periods April through March)
    - Dynamic countdown of remaining periods under Section 192 (12 - eval_fy_idx + 1)
    - Mid-year joiners (taking employee joining date / contract date_start into account)
    - Early resignations / departures before FY end (taking departure_date / contract date_end into account)
    """

    def _resolve_employee_joining_date(self, employee):
        """
        Resolves employee's joining date or first employment start date.
        """
        if not employee:
            return None
        for fname in ('joining_date', 'date_of_joining', 'hds_in_doj', 'first_contract_date', 'contract_date_start'):
            val = getattr(employee, fname, None)
            if val:
                return fields.Date.from_string(val) if isinstance(val, str) else val
        # Check employee contract
        contract = False
        if hasattr(employee, 'contract_id') and employee.contract_id:
            contract = employee.contract_id
        elif hasattr(employee, 'contract_ids') and employee.contract_ids:
            open_contracts = employee.contract_ids.filtered(lambda c: getattr(c, 'state', False) == 'open')
            contract = open_contracts[0] if open_contracts else employee.contract_ids[0]
        if contract and getattr(contract, 'date_start', None):
            val = contract.date_start
            return fields.Date.from_string(val) if isinstance(val, str) else val
        return None

    def _resolve_employee_departure_date(self, employee):
        """
        Resolves employee's departure date, resignation date, or contract end date.
        """
        if not employee:
            return None
        for fname in ('departure_date', 'end_date', 'resignation_date'):
            val = getattr(employee, fname, None)
            if val:
                return fields.Date.from_string(val) if isinstance(val, str) else val
        contract = False
        if hasattr(employee, 'contract_id') and employee.contract_id:
            contract = employee.contract_id
        elif hasattr(employee, 'contract_ids') and employee.contract_ids:
            open_contracts = employee.contract_ids.filtered(lambda c: getattr(c, 'state', False) == 'open')
            contract = open_contracts[0] if open_contracts else employee.contract_ids[0]
        if contract and getattr(contract, 'date_end', None):
            val = contract.date_end
            return fields.Date.from_string(val) if isinstance(val, str) else val
        return None

    def calculate_remaining_periods(self, employee, financial_year, eval_date=None):
        """
        Calculates remaining payroll periods in Financial Year (inclusive of current month).

        :param employee: hr.employee record
        :param financial_year: tds.financial.year record
        :param eval_date: Date (optional payslip eval_date / date_to)
        :return: int (Remaining payroll periods, min 1)
        """
        eval_date = eval_date or fields.Date.today()
        if isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)

        fy_start = financial_year.start_date if financial_year else None
        fy_end = financial_year.end_date if financial_year else None

        if not fy_start or not fy_end:
            return 12

        if eval_date > fy_end:
            return 1

        fy_start_year = fy_start.year
        fy_start_month = fy_start.month

        # Calculate 1-based FY month index for eval_date (1 for April, ..., 12 for March)
        if eval_date < fy_start:
            eval_fy_idx = 1
        else:
            eval_year = eval_date.year
            eval_month = eval_date.month
            elapsed_months = (eval_year - fy_start_year) * 12 + (eval_month - fy_start_month) + 1
            eval_fy_idx = min(12, max(1, elapsed_months))

        # Check joining date
        joining_date = self._resolve_employee_joining_date(employee)
        if joining_date and joining_date > fy_start:
            join_year = joining_date.year
            join_month = joining_date.month
            join_elapsed = (join_year - fy_start_year) * 12 + (join_month - fy_start_month) + 1
            join_fy_idx = min(12, max(1, join_elapsed))
        else:
            join_fy_idx = 1

        # Effective start index for remaining periods:
        # If eval_date is earlier than joining date, countdown starts from joining month.
        # Otherwise, starts from current evaluation month (inclusive).
        start_fy_idx = max(eval_fy_idx, join_fy_idx)

        # Check departure / contract end date
        departure_date = self._resolve_employee_departure_date(employee)
        if departure_date and departure_date < fy_end:
            dep_year = departure_date.year
            dep_month = departure_date.month
            dep_elapsed = (dep_year - fy_start_year) * 12 + (dep_month - fy_start_month) + 1
            dep_fy_idx = min(12, max(1, dep_elapsed))
            end_fy_idx = min(12, max(start_fy_idx, dep_fy_idx))
        else:
            end_fy_idx = 12

        remaining_periods = max(1, end_fy_idx - start_fy_idx + 1)

        _logger.info(
            "[PAYROLL PERIOD SERVICE] Employee '%s' | FY '%s' | Eval FY Index: %s | "
            "Join FY Index: %s | End FY Index: %s | Remaining Periods: %s",
            employee.name if employee else 'N/A',
            financial_year.name if financial_year else 'N/A',
            eval_fy_idx, join_fy_idx, end_fy_idx, remaining_periods
        )
        return remaining_periods

    def calculate_total_periods_in_fy(self, employee, financial_year):
        """
        Calculates total employment months for the employee in this Financial Year.
        - Existing employee (joined on/before FY start): 12 months (or up to departure date).
        - Mid-year joiner (joined after FY start): count of months from joining month to FY end (or departure date).
        """
        if not financial_year or not financial_year.start_date or not financial_year.end_date:
            return 12

        fy_start = financial_year.start_date
        fy_end = financial_year.end_date
        fy_start_year = fy_start.year
        fy_start_month = fy_start.month

        joining_date = self._resolve_employee_joining_date(employee)
        if joining_date and joining_date > fy_start:
            join_year = joining_date.year
            join_month = joining_date.month
            join_elapsed = (join_year - fy_start_year) * 12 + (join_month - fy_start_month) + 1
            join_fy_idx = min(12, max(1, join_elapsed))
        else:
            join_fy_idx = 1

        departure_date = self._resolve_employee_departure_date(employee)
        if departure_date and departure_date < fy_end:
            dep_year = departure_date.year
            dep_month = departure_date.month
            dep_elapsed = (dep_year - fy_start_year) * 12 + (dep_month - fy_start_month) + 1
            dep_fy_idx = min(12, max(1, dep_elapsed))
            end_fy_idx = min(12, max(join_fy_idx, dep_fy_idx))
        else:
            end_fy_idx = 12

        total_periods = max(1, end_fy_idx - join_fy_idx + 1)
        return total_periods

