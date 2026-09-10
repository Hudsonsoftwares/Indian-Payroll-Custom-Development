# -*- coding: utf-8 -*-
import logging
from ..base import BaseStatutoryService

_logger = logging.getLogger(__name__)


class TaxableIncomeResult:
    """
    Data Transfer Object (DTO) holding Net Taxable Income details.
    """
    def __init__(self, gross_total_income, total_approved_deductions, net_taxable_income):
        self.gross_total_income = gross_total_income
        self.total_approved_deductions = total_approved_deductions
        self.net_taxable_income = net_taxable_income


class TaxableIncomeService(BaseStatutoryService):
    """
    Phase 4 Pipeline Service: Taxable Income Service.
    Calculates Net Taxable Income by subtracting total approved deductions from Gross Total Income (GTI).
    Serves as the input provider to the Income Tax Slab Engine.
    """

    def calculate_taxable_income(self, gross_total_income, total_approved_deductions):
        """
        Calculates Net Taxable Income.

        :param gross_total_income: float (Gross Total Income projected in Phase 4)
        :param total_approved_deductions: float (Total approved statutory deductions)
        :return: TaxableIncomeResult
        """
        net_taxable = max(0.0, gross_total_income - total_approved_deductions)

        summary_log = f"""
========================================================
TAXABLE INCOME SERVICE
========================================================
Gross Total Income      : ₹{gross_total_income:,.2f}
- Total Deductions      : ₹{total_approved_deductions:,.2f}
= Net Taxable Income    : ₹{net_taxable:,.2f}
========================================================
"""
        _logger.warning("""[FORENSIC_TDS_TRACE]
step=TAXABLE_INCOME
input=gross_total_income:INR %s, total_allowable_deductions:INR %s
output=net_taxable_income:INR %s
source_method=TaxableIncomeService.calculate_taxable_income
branch_used=%s""",
            f"{gross_total_income:,.2f}",
            f"{total_approved_deductions:,.2f}",
            f"{net_taxable:,.2f}",
            f"MAX_ZERO_FLOOR_TAXABLE_INCOME (Gross INR {gross_total_income:,.2f} - Deductions INR {total_approved_deductions:,.2f})"
        )

        return TaxableIncomeResult(
            gross_total_income=gross_total_income,
            total_approved_deductions=total_approved_deductions,
            net_taxable_income=net_taxable
        )
