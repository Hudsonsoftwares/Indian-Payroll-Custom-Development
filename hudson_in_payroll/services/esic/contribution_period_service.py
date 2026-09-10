# -*- coding: utf-8 -*-
import datetime
import logging
from ..base import BaseStatutoryService

_logger = logging.getLogger(__name__)


class ESICContributionPeriodService(BaseStatutoryService):
    """
    Pure Python service for ESIC statutory Contribution Period determination.
    Enforces Regulation 31 continuity: If an employee's wage on the first day
    of an active Contribution Period is <= ceiling, ESIC deductions continue
    through the end of that 6-month period regardless of mid-period increments.
    """

    def get_contribution_period_bounds(self, ref_date):
        """
        Returns statutory (period_start_date, period_end_date) for a given reference date.
        - April 1 to September 30
        - October 1 to March 31
        """
        if not ref_date:
            ref_date = datetime.date.today()
        elif isinstance(ref_date, str):
            ref_date = datetime.datetime.strptime(ref_date, '%Y-%m-%d').date()

        year = ref_date.year
        month = ref_date.month

        if 4 <= month <= 9:
            start_date = datetime.date(year, 4, 1)
            end_date = datetime.date(year, 9, 30)
        elif month >= 10:
            start_date = datetime.date(year, 10, 1)
            end_date = datetime.date(year + 1, 3, 31)
        else:
            start_date = datetime.date(year - 1, 10, 1)
            end_date = datetime.date(year, 3, 31)

        return start_date, end_date

    def get_effective_wage_on_date(self, employee, eval_date):
        """
        Determines effective gross wage on a given historical or future date by inspecting
        active contract wage and adjusting for salary revisions confirmed after eval_date.
        """
        if not employee or not isinstance(employee.id, int):
            return 0.0

        if isinstance(eval_date, str):
            eval_date = datetime.datetime.strptime(eval_date, '%Y-%m-%d').date()

        contracts = self.env['hr.version'].search([
            ('employee_id', '=', employee.id),
        ])
        if not contracts:
            return 0.0

        # Sort contracts by date_start desc to get current active contract
        valid_contracts = [c for c in contracts if (c.date_start and c.date_start <= eval_date and (c.wage or 0.0) > 0)]
        if not valid_contracts:
            valid_contracts = [c for c in contracts if (c.wage or 0.0) > 0]
        if not valid_contracts:
            valid_contracts = contracts
        sorted_contracts = sorted(valid_contracts, key=lambda c: (c.date_start or datetime.date.min, c.id), reverse=True)
        current_wage = sorted_contracts[0].wage or 0.0

        # Check salary revisions approved AFTER eval_date to find wage on eval_date
        revisions = self.env['hds.in.salary.revision'].search([
            ('employee_id', '=', employee.id),
            ('effective_date', '>', eval_date),
            ('state', '=', 'approved')
        ], order='effective_date asc')

        if revisions:
            return revisions[0].old_wage if revisions[0].old_wage > 0.0 else current_wage

        return current_wage

    def is_covered_for_contribution_period(self, employee, eval_date=None, current_wage=None):
        """
        Single Source of Truth for ESIC Contribution Period coverage:
        Checks if gross wage on the FIRST DAY of the active Contribution Period was <= statutory ceiling.
        """
        if not employee:
            return False

        if eval_date is None:
            eval_date = datetime.date.today()
        elif isinstance(eval_date, str):
            eval_date = datetime.datetime.strptime(eval_date, '%Y-%m-%d').date()

        period_start, period_end = self.get_contribution_period_bounds(eval_date)
        period_start_wage = self.get_effective_wage_on_date(employee, period_start)

        if period_start_wage <= 0.0:
            period_start_wage = self.get_effective_wage_on_date(employee, eval_date)

        if period_start_wage <= 0.0 and current_wage is not None:
            period_start_wage = float(current_wage or 0.0)

        if getattr(employee, 'hds_in_is_pwd', False):
            ceiling = self.get_parameter('hds_in_esic_pwd_wage_ceiling', date=eval_date, as_decimal=False)
        else:
            ceiling = self.get_parameter('hds_in_esic_wage_ceiling', date=eval_date, as_decimal=False)

        if period_start_wage > 0.0:
            result = period_start_wage <= ceiling
        else:
            result = False

        _logger.info(
            "[ESIC] period_start=%s period_start_wage=%s ceiling=%s result=%s",
            period_start,
            period_start_wage,
            ceiling,
            result
        )
        return result
