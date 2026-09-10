# -*- coding: utf-8 -*-
import logging
from odoo import fields

_logger = logging.getLogger(__name__)


class PayrollWageAggregationService:
    """
    Domain Service for generic payroll wage aggregation across historical payslips.
    Decoupled from specific statutory engines (reusable by Professional Tax, Bonus, Gratuity, ESIC).

    Responsibilities:
    - Aggregate historical payslip line amounts for an employee between start_date and end_date.
    - Filter by salary rule categories (e.g. 'GROSS', 'BASIC') or explicit rule code lists.
    - Respect payslip states (includes 'done' / 'verify', ignores 'cancel' / draft).
    - Handle multi-company boundary scoping.
    - Support merging active transient/executing payslip evaluation gross.
    """

    def __init__(self, env):
        self.env = env

    def get_aggregated_wage(
        self,
        employee,
        start_date,
        end_date,
        category_code="GROSS",
        rule_codes=None,
        company=None,
        current_slip=None,
        current_slip_gross=0.0
    ):
        """
        Calculates total aggregated earnings for an employee between start_date and end_date.

        :param employee: hr.employee recordset (single record)
        :param start_date: datetime.date or date str (period start, inclusive)
        :param end_date: datetime.date or date str (period end, inclusive)
        :param category_code: str (salary rule category code, e.g. 'GROSS', 'BASIC')
        :param rule_codes: list of str (optional specific rule codes to filter)
        :param company: res.company recordset (optional company scope)
        :param current_slip: hr.payslip recordset (active payslip being evaluated)
        :param current_slip_gross: float (gross value from current payslip evaluation context)
        :return: float total aggregated earnings
        """
        if not employee:
            return 0.0

        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)

        target_company = company or employee.company_id or self.env.company

        # Build domain to fetch historical payslips for the employee in the date range
        slip_domain = [
            ('employee_id', '=', employee.id),
            ('state', 'in', ['done', 'verify']),
            ('date_from', '>=', start_date),
            ('date_to', '<=', end_date),
        ]
        if target_company:
            slip_domain.append(('company_id', '=', target_company.id))

        if current_slip and current_slip.id:
            # Exclude current payslip from historical DB query to avoid duplicate counting
            slip_domain.append(('id', '!=', current_slip.id))

        historical_slips = self.env['hr.payslip'].search(slip_domain)

        total_wage = 0.0

        # Query payslip lines for category or rule codes
        if historical_slips:
            line_domain = [('slip_id', 'in', historical_slips.ids)]
            if rule_codes:
                line_domain.append(('code', 'in', rule_codes))
            elif category_code:
                line_domain.append(('category_id.code', '=', category_code))

            lines = self.env['hr.payslip.line'].search(line_domain)
            for line in lines:
                total_wage += line.total

        # Add current slip's gross if provided
        if current_slip_gross:
            try:
                total_wage += float(current_slip_gross or 0.0)
            except (TypeError, ValueError):
                pass

        _logger.info(
            "PayrollWageAggregationService: Aggregated %s wage for employee %s [%s to %s]: ₹%s (Historical slips: %s)",
            category_code, getattr(employee, 'name', 'Unknown'), start_date, end_date, total_wage, len(historical_slips)
        )
        return total_wage
