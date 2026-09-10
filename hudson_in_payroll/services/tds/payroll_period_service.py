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
    - Mid-year joiners
    - Early resignations / departures before FY end
    """

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

        fy_start = financial_year.start_date
        fy_end = financial_year.end_date

        tds_months = int(getattr(financial_year, 'tds_month_division', 0) or 0)
        if tds_months <= 0:
            tds_months_param = self.env['ir.config_parameter'].sudo().get_param('hudson_in_payroll.tds_month_division', default=12)
            try:
                tds_months = int(tds_months_param)
                if tds_months <= 0:
                    tds_months = 12
            except (ValueError, TypeError):
                tds_months = 12

        if eval_date < fy_start:
            return tds_months
        elif eval_date > fy_end:
            return 1

        # Calculate 1-based FY month index (1 for April, ..., 12 for March)
        if fy_start:
            fy_start_year = fy_start.year
            fy_start_month = fy_start.month
            eval_year = eval_date.year
            eval_month = eval_date.month
            elapsed_months = (eval_year - fy_start_year) * 12 + (eval_month - fy_start_month) + 1
            eval_fy_idx = min(12, max(1, elapsed_months))
        else:
            eval_m = eval_date.month
            eval_fy_idx = eval_m - 3 if eval_m >= 4 else eval_m + 9

        # Configuration-driven redistribution months count (e.g., 3 for final 3 months of FY)
        dist_months = max(1, min(12, int(getattr(financial_year, 'tds_recalculation_distribution_months', 3) or 3)))

        # Dynamically derive the start FY month index of the redistribution period (final dist_months of FY)
        recalc_start_fy_idx = 12 - dist_months + 1

        if eval_fy_idx >= recalc_start_fy_idx:
            # Redistribution Phase: dynamically calculate remaining redistribution months
            remaining_dist_periods = max(1, 12 - eval_fy_idx + 1)
            _logger.info(
                "[PAYROLL PERIOD SERVICE] Financial Year '%s' | Redistribution Active (Final %s months of FY, start FY Index %s) | "
                "Current Month FY Index: %s | Remaining Redistribution Periods: %s",
                financial_year.name if financial_year else 'N/A', dist_months, recalc_start_fy_idx,
                eval_fy_idx, remaining_dist_periods
            )
            return remaining_dist_periods

        # Normal Phase (before redistribution period begins): Use standard 12-month division
        tds_months = int(getattr(financial_year, 'tds_month_division', 0) or 0)
        if tds_months <= 0:
            tds_months_param = self.env['ir.config_parameter'].sudo().get_param('hudson_in_payroll.tds_month_division', default=12)
            try:
                tds_months = int(tds_months_param)
                if tds_months <= 0:
                    tds_months = 12
            except (ValueError, TypeError):
                tds_months = 12

        _logger.info(
            "[PAYROLL PERIOD SERVICE] Financial Year '%s' | Normal Phase (FY Index %s < Start %s) | "
            "Using Constant Divisor = %s for Annual Tax Distribution.",
            financial_year.name if financial_year else 'N/A', eval_fy_idx, recalc_start_fy_idx, tds_months
        )
        return tds_months
