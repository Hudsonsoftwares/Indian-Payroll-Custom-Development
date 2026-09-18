# -*- coding: utf-8 -*-
import logging
from abc import ABC, abstractmethod
from datetime import date
from odoo import fields
from ..payroll.payroll_wage_aggregation_service import PayrollWageAggregationService

_logger = logging.getLogger(__name__)


class AbstractPTPeriodicityStrategy(ABC):
    """
    Abstract Base Class for Professional Tax Periodicity Strategies.
    Encapsulates window resolution, prior deduction tracking, and dynamic payroll distribution math.
    """

    @abstractmethod
    def get_periodicity_code(self) -> str:
        """Returns the periodicity code matching pt.state.slab (e.g., 'monthly', 'half_yearly')."""
        pass

    @abstractmethod
    def resolve_aggregation_window(self, eval_date: date) -> tuple:
        """Resolves period (start_date, end_date) for a given evaluation date."""
        pass

    def get_period_already_deducted(self, env, employee, start_date, eval_date, current_slip=None) -> float:
        """
        Queries prior non-cancelled payslips for employee within [start_date, eval_date)
        and sums up all previously deducted Professional Tax amounts.
        """
        if not employee or not start_date:
            return 0.0

        if isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)
        if not eval_date:
            eval_date = fields.Date.today()

        m_first_date = date(eval_date.year, eval_date.month, 1)

        domain = [
            ('employee_id', '=', employee.id),
            ('state', 'not in', ('cancel', 'refused')),
            ('date_from', '>=', start_date),
            ('date_from', '<=', eval_date),
        ]
        curr_id = getattr(current_slip, 'id', False)
        if current_slip and isinstance(curr_id, int):
            domain.append(('id', '!=', curr_id))

        slips = env['hr.payslip'].search(domain)
        if not slips:
            return 0.0

        total_pt = 0.0
        for slip in slips:
            for line in slip.line_ids:
                if line.code in ('PT', 'HDS_IN_PT') or getattr(line.category_id, 'code', '') == 'PT':
                    total_pt += abs(line.total or 0.0)

        return float(total_pt)

    def calculate_payroll_deduction(
        self,
        env,
        employee,
        period_liability: float,
        eval_date: date,
        current_slip=None,
        period_schedule=None
    ) -> float:
        """
        Generic, configuration-driven algorithm calculating exact PT deduction for current payroll.
        Formula:
        1. remaining_liability = period_liability - already_deducted
        2. if End of Period -> deduct full remaining_liability in deduction month (or final payroll)
        3. if Every Payroll -> deduct remaining_liability / remaining_eligible_payrolls (with exact residual rounding reconciliation)
        """
        from .pt_period_config_service import PTPeriodScheduleService
        from odoo.tools import float_round

        sched_service = PTPeriodScheduleService(env)

        # Resolve period window
        start_d, end_d = sched_service.resolve_period_window(
            schedule=period_schedule, eval_date=eval_date, periodicity=self.get_periodicity_code()
        )

        # Calculate already deducted PT in this period
        already_deducted = self.get_period_already_deducted(
            env, employee=employee, start_date=start_d, eval_date=eval_date, current_slip=current_slip
        )

        remaining_liability = max(float(period_liability or 0.0) - already_deducted, 0.0)
        if remaining_liability <= 0.0:
            return 0.0

        # Resolve strategy and distribution method
        strategy = (period_schedule.deduction_strategy if period_schedule else 'every_payroll') or 'every_payroll'
        dist_method = (period_schedule.distribution_method if period_schedule else False) or ('full_amount' if strategy in ('end_of_period', 'specific_month', 'beginning_of_period') else 'equal_distribution')

        # Strategy 1: End of Period / Specific Month / Beginning of Period / Full Amount
        if strategy in ('end_of_period', 'specific_month', 'beginning_of_period') or dist_method == 'full_amount':
            if sched_service.should_deduct(period_schedule, eval_date=eval_date, employee=employee):
                return float_round(remaining_liability, precision_digits=2)
            return 0.0

        # Strategy 2: Every Payroll / Equal Distribution
        rem_payrolls = sched_service.calculate_remaining_payrolls(
            employee=employee, period_start_date=start_d, period_end_date=end_d, eval_date=eval_date
        )

        if rem_payrolls <= 1:
            # Final eligible payroll of period absorbs exact residual amount for perfect reconciliation
            return float_round(remaining_liability, precision_digits=2)

        raw_deduction = remaining_liability / rem_payrolls
        return float_round(raw_deduction, precision_digits=2)


class MonthlyPTStrategy(AbstractPTPeriodicityStrategy):
    """Monthly Professional Tax Strategy."""

    def get_periodicity_code(self) -> str:
        return 'monthly'

    def resolve_aggregation_window(self, eval_date: date) -> tuple:
        if isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)
        if not eval_date:
            eval_date = fields.Date.today()
        year = eval_date.year
        month = eval_date.month
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        return (date(year, month, 1), date(year, month, last_day))

    def calculate_wage_basis(
        self,
        env,
        employee,
        eval_date: date,
        current_slip=None,
        current_slip_gross=0.0,
        company=None,
        period_schedule=None
    ) -> float:
        return float(current_slip_gross or 0.0)


class HalfYearlyPTStrategy(AbstractPTPeriodicityStrategy):
    """Half-Yearly Professional Tax Strategy."""

    def get_periodicity_code(self) -> str:
        return 'half_yearly'

    def resolve_aggregation_window(self, eval_date: date) -> tuple:
        if isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)
        if not eval_date:
            eval_date = fields.Date.today()

        month = eval_date.month
        year = eval_date.year

        if 4 <= month <= 9:
            start_d = date(year, 4, 1)
            end_d = date(year, 9, 30)
        elif month >= 10:
            start_d = date(year, 10, 1)
            end_d = date(year + 1, 3, 31)
        else:
            start_d = date(year - 1, 10, 1)
            end_d = date(year, 3, 31)

        return (start_d, end_d)

    def calculate_wage_basis(
        self,
        env,
        employee,
        eval_date: date,
        current_slip=None,
        current_slip_gross=0.0,
        company=None,
        period_schedule=None
    ) -> float:
        if period_schedule:
            from .pt_period_config_service import PTPeriodScheduleService
            sched_service = PTPeriodScheduleService(env)
            start_d, end_d = sched_service.resolve_period_window(period_schedule, eval_date=eval_date)
        else:
            start_d, end_d = self.resolve_aggregation_window(eval_date)

        agg_service = PayrollWageAggregationService(env)
        return agg_service.get_aggregated_wage(
            employee=employee,
            start_date=start_d,
            end_date=end_d,
            category_code="GROSS",
            company=company,
            current_slip=current_slip,
            current_slip_gross=current_slip_gross
        )


class QuarterlyPTStrategy(AbstractPTPeriodicityStrategy):
    """Quarterly Professional Tax Strategy."""

    def get_periodicity_code(self) -> str:
        return 'quarterly'

    def resolve_aggregation_window(self, eval_date: date) -> tuple:
        if isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)
        if not eval_date:
            eval_date = fields.Date.today()

        month = eval_date.month
        year = eval_date.year

        if 4 <= month <= 6:
            return (date(year, 4, 1), date(year, 6, 30))
        elif 7 <= month <= 9:
            return (date(year, 7, 1), date(year, 9, 30))
        elif 10 <= month <= 12:
            return (date(year, 10, 1), date(year, 12, 31))
        else:
            return (date(year, 1, 1), date(year, 3, 31))

    def calculate_wage_basis(
        self,
        env,
        employee,
        eval_date: date,
        current_slip=None,
        current_slip_gross=0.0,
        company=None,
        period_schedule=None
    ) -> float:
        if period_schedule:
            from .pt_period_config_service import PTPeriodScheduleService
            sched_service = PTPeriodScheduleService(env)
            start_d, end_d = sched_service.resolve_period_window(period_schedule, eval_date=eval_date)
        else:
            start_d, end_d = self.resolve_aggregation_window(eval_date)

        agg_service = PayrollWageAggregationService(env)
        return agg_service.get_aggregated_wage(
            employee=employee,
            start_date=start_d,
            end_date=end_d,
            category_code="GROSS",
            company=company,
            current_slip=current_slip,
            current_slip_gross=current_slip_gross
        )


class AnnualPTStrategy(AbstractPTPeriodicityStrategy):
    """Annual Professional Tax Strategy."""

    def get_periodicity_code(self) -> str:
        return 'annual'

    def resolve_aggregation_window(self, eval_date: date) -> tuple:
        if isinstance(eval_date, str):
            eval_date = fields.Date.from_string(eval_date)
        if not eval_date:
            eval_date = fields.Date.today()

        year = eval_date.year
        if eval_date.month >= 4:
            return (date(year, 4, 1), date(year + 1, 3, 31))
        else:
            return (date(year - 1, 4, 1), date(year, 3, 31))

    def calculate_wage_basis(
        self,
        env,
        employee,
        eval_date: date,
        current_slip=None,
        current_slip_gross=0.0,
        company=None,
        period_schedule=None
    ) -> float:
        if period_schedule:
            from .pt_period_config_service import PTPeriodScheduleService
            sched_service = PTPeriodScheduleService(env)
            start_d, end_d = sched_service.resolve_period_window(period_schedule, eval_date=eval_date)
        else:
            start_d, end_d = self.resolve_aggregation_window(eval_date)

        agg_service = PayrollWageAggregationService(env)
        return agg_service.get_aggregated_wage(
            employee=employee,
            start_date=start_d,
            end_date=end_d,
            category_code="GROSS",
            company=company,
            current_slip=current_slip,
            current_slip_gross=current_slip_gross
        )


class PTPeriodicityStrategyRegistry:
    """
    Factory & Registry for Professional Tax Periodicity Strategies.
    Decouples ProfessionalTaxService from periodicity-specific code branches.
    """

    _strategies = {
        'monthly': MonthlyPTStrategy(),
        'half_yearly': HalfYearlyPTStrategy(),
        'quarterly': QuarterlyPTStrategy(),
        'annual': AnnualPTStrategy(),
    }

    @classmethod
    def get_strategy(cls, periodicity_code) -> AbstractPTPeriodicityStrategy:
        code = str(periodicity_code).strip().lower() if periodicity_code else 'monthly'
        return cls._strategies.get(code, cls._strategies['monthly'])
