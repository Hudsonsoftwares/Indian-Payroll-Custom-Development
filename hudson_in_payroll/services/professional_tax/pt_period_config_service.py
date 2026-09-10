# -*- coding: utf-8 -*-
import logging
from datetime import date
import calendar
from odoo import fields

_logger = logging.getLogger(__name__)


class PTPeriodScheduleService:
    """
    Domain Service for Professional Tax Period Schedule Resolution & Payroll Counting.
    Decoupled from salary slab amount matching (pt.state.slab).

    Responsibilities:
    - Locate active pt.period.schedule record for state, company, and evaluation date.
    - Calculate exact statutory date range (start_date, end_date) for the matching period window.
    - Dynamically calculate total and remaining eligible payroll counts for employee lifecycle (joining/leaving).
    """

    def __init__(self, env):
        self.env = env

    def resolve_schedule(self, state, company=None, eval_date=None):
        """
        Resolves the active pt.period.schedule record matching state, company, and eval_date.

        :param state: res.country.state recordset
        :param company: res.company recordset
        :param eval_date: datetime.date or str
        :return: pt.period.schedule recordset (single record) or False
        """
        if not state:
            return False

        if not eval_date:
            eval_date = fields.Date.today()
        elif isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)

        target_company = company or self.env.company
        month = eval_date.month

        # Build search domain for active schedules
        base_domain = [
            ('state_id', '=', state.id),
            ('active', '=', True),
            '|', ('date_from', '=', False), ('date_from', '<=', eval_date),
            '|', ('date_to', '=', False), ('date_to', '>=', eval_date),
            '|', ('company_id', '=', False), ('company_id', '=', target_company.id),
        ]

        schedules = self.env['pt.period.schedule'].search(base_domain)
        if not schedules:
            return False

        # Filter schedules whose window includes month
        matching_schedules = []
        for sched in schedules:
            if sched.periodicity == 'monthly':
                matching_schedules.append(sched)
                continue

            start_m = int(sched.window_start_month or '1')
            end_m = int(sched.window_end_month or '12')

            if start_m <= end_m:
                if start_m <= month <= end_m:
                    matching_schedules.append(sched)
            else:  # Crosses calendar year boundary (e.g. October 10 -> March 3)
                if month >= start_m or month <= end_m:
                    matching_schedules.append(sched)

        if not matching_schedules:
            return schedules[0]

        # Rank company-specific over global
        def rank_key(s):
            is_company = 1 if (company and s.company_id and s.company_id.id == company.id) else 0
            d_from = s.date_from or fields.Date.from_string('1900-01-01')
            return (is_company, d_from, s.id)

        sorted_schedules = sorted(matching_schedules, key=rank_key, reverse=True)
        return sorted_schedules[0]

    def resolve_period_window(self, schedule=None, eval_date=None, periodicity=None):
        """
        Calculates exact (start_date, end_date) date tuple for period schedule window.

        :param schedule: pt.period.schedule recordset or None
        :param eval_date: datetime.date or str
        :param periodicity: str ('monthly', 'quarterly', 'half_yearly', 'annual')
        :return: tuple of (start_date, end_date)
        """
        if not eval_date:
            eval_date = fields.Date.today()
        elif isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)

        year = eval_date.year
        month = eval_date.month

        code = (schedule.periodicity if schedule else periodicity) or 'monthly'

        if schedule and schedule.window_start_month and schedule.window_end_month:
            start_m = int(schedule.window_start_month)
            end_m = int(schedule.window_end_month)

            if start_m <= end_m:
                start_d = date(year, start_m, 1)
                last_day = calendar.monthrange(year, end_m)[1]
                end_d = date(year, end_m, last_day)
            else:
                if month >= start_m:
                    start_d = date(year, start_m, 1)
                    last_day = calendar.monthrange(year + 1, end_m)[1]
                    end_d = date(year + 1, end_m, last_day)
                else:
                    start_d = date(year - 1, start_m, 1)
                    last_day = calendar.monthrange(year, end_m)[1]
                    end_d = date(year, end_m, last_day)
            return (start_d, end_d)

        # Generic default window logic when schedule window is not explicitly set
        if code == 'quarterly':
            if 4 <= month <= 6:
                return (date(year, 4, 1), date(year, 6, 30))
            elif 7 <= month <= 9:
                return (date(year, 7, 1), date(year, 9, 30))
            elif 10 <= month <= 12:
                return (date(year, 10, 1), date(year, 12, 31))
            else:
                return (date(year, 1, 1), date(year, 3, 31))
        elif code == 'half_yearly':
            if 4 <= month <= 9:
                return (date(year, 4, 1), date(year, 9, 30))
            elif month >= 10:
                return (date(year, 10, 1), date(year + 1, 3, 31))
            else:
                return (date(year - 1, 10, 1), date(year, 3, 31))
        elif code == 'annual':
            if month >= 4:
                return (date(year, 4, 1), date(year + 1, 3, 31))
            else:
                return (date(year - 1, 4, 1), date(year, 3, 31))

        # Default Monthly
        last_day = calendar.monthrange(year, month)[1]
        return (date(year, month, 1), date(year, month, last_day))

    def _get_emp_date(self, employee, field_name):
        if not employee or field_name not in employee._fields:
            return False
        val = getattr(employee, field_name, False)
        if isinstance(val, str):
            return fields.Date.from_string(val)
        return val

    def calculate_eligible_payrolls(self, employee, period_start_date, period_end_date):
        """
        Calculates total eligible payroll count for employee within [period_start_date, period_end_date].
        Dynamically accounts for employee join/hire date and contract start/end dates.
        """
        if not employee:
            return 1

        emp_start = (
            self._get_emp_date(employee, 'joining_date') or
            self._get_emp_date(employee, 'first_contract_date')
        )
        if not emp_start and 'contract_id' in employee._fields and employee.contract_id:
            emp_start = self._get_emp_date(employee.contract_id, 'date_start')

        emp_end = (
            self._get_emp_date(employee, 'departure_date') or
            self._get_emp_date(employee, 'resignation_date')
        )
        if not emp_end and 'contract_id' in employee._fields and employee.contract_id:
            emp_end = self._get_emp_date(employee.contract_id, 'date_end')

        count = 0
        cur_year = period_start_date.year
        cur_month = period_start_date.month

        end_year = period_end_date.year
        end_month = period_end_date.month

        while (cur_year < end_year) or (cur_year == end_year and cur_month <= end_month):
            m_last_day = calendar.monthrange(cur_year, cur_month)[1]
            m_start = date(cur_year, cur_month, 1)
            m_end = date(cur_year, cur_month, m_last_day)

            is_after_start = True
            if emp_start:
                is_after_start = m_end >= emp_start

            is_before_end = True
            if emp_end:
                is_before_end = m_start <= emp_end

            if is_after_start and is_before_end:
                count += 1

            if cur_month == 12:
                cur_month = 1
                cur_year += 1
            else:
                cur_month += 1

        return max(count, 1)

    def calculate_remaining_payrolls(self, employee, period_start_date, period_end_date, eval_date):
        """
        Calculates remaining eligible payroll count for employee from eval_date's month
        through period_end_date (inclusive of eval_date's month).
        """
        if isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)
        if not eval_date:
            eval_date = fields.Date.today()

        eval_m_start = date(eval_date.year, eval_date.month, 1)
        start_eval = max(period_start_date, eval_m_start)
        return self.calculate_eligible_payrolls(employee, start_eval, period_end_date)

    def should_deduct(self, schedule, eval_date=None, employee=None):
        """
        Determines whether PT should be deducted for eval_date according to schedule configuration.
        """
        if not schedule:
            return True

        if not eval_date:
            eval_date = fields.Date.today()
        elif isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)

        m = eval_date.month
        strategy_type = schedule.deduction_strategy or 'every_payroll'

        if strategy_type == 'every_payroll':
            return True

        if strategy_type == 'end_of_period':
            target_m = int(schedule.window_end_month or schedule.deduction_month or '12')
            if schedule.deduction_month:
                try:
                    target_m = int(str(schedule.deduction_month).strip())
                except (ValueError, TypeError):
                    pass

            if m == target_m:
                return True

            if employee:
                start_d, end_d = self.resolve_period_window(schedule, eval_date=eval_date)
                rem = self.calculate_remaining_payrolls(employee, start_d, end_d, eval_date)
                if rem <= 1:
                    return True

            return False

        if strategy_type == 'specific_month':
            if schedule.deduction_month:
                try:
                    return m == int(str(schedule.deduction_month).strip())
                except (ValueError, TypeError):
                    pass
            return False

        return True
