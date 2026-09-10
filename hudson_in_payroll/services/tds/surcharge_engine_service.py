# -*- coding: utf-8 -*-
import logging
from ..base import BaseStatutoryService

_logger = logging.getLogger(__name__)


class SurchargeEngineResult:
    """
    Data Transfer Object (DTO) holding surcharge computation details.
    """
    def __init__(self, net_taxable_income, tax_after_rebate, surcharge_rate_pct,
                 surcharge_amount, tax_plus_surcharge):
        self.net_taxable_income = net_taxable_income
        self.tax_after_rebate = tax_after_rebate
        self.surcharge_rate_pct = surcharge_rate_pct
        self.surcharge_amount = surcharge_amount
        self.tax_plus_surcharge = tax_plus_surcharge


class SurchargeEngineService(BaseStatutoryService):
    """
    Phase 4 Pipeline Service: Surcharge Engine Service.
    Resolves range-based surcharge percentage bands from tds.surcharge for the Financial Year & Tax Regime.
    Applies surcharge to total income tax after Section 87A rebate.
    """

    def calculate_surcharge(self, net_taxable_income, tax_after_rebate, financial_year, regime_code):
        """
        Calculates income tax surcharge.

        :param net_taxable_income: float (Net Taxable Income)
        :param tax_after_rebate: float (Tax liability after Section 87A rebate)
        :param financial_year: tds.financial.year record
        :param regime_code: str ('old' or 'new')
        :return: SurchargeEngineResult
        """
        if tax_after_rebate <= 0:
            return SurchargeEngineResult(
                net_taxable_income=net_taxable_income,
                tax_after_rebate=0.0,
                surcharge_rate_pct=0.0,
                surcharge_amount=0.0,
                tax_plus_surcharge=0.0
            )

        regime_code = (regime_code or 'new').lower()

        # Query surcharge slabs from master
        surcharges = self.env['tds.surcharge'].search([
            ('financial_year_id', '=', financial_year.id),
            ('regime_code', '=', regime_code)
        ], order='income_from desc')

        surcharge_rate = 0.0
        for s in surcharges:
            inc_from = s.income_from
            inc_to = s.income_to if s.income_to > 0 else float('inf')
            if inc_from <= net_taxable_income <= inc_to or (inc_from <= net_taxable_income and inc_to == float('inf')):
                surcharge_rate = s.surcharge_rate
                break

        surcharge_amount = tax_after_rebate * (surcharge_rate / 100.0)
        tax_plus_surcharge = tax_after_rebate + surcharge_amount

        summary_log = f"""
========================================================
SURCHARGE ENGINE SERVICE
========================================================
Net Taxable Income      : ₹{net_taxable_income:,.2f}
Tax Before Surcharge    : ₹{tax_after_rebate:,.2f}
Applicable Surcharge    : {surcharge_rate}%
Surcharge Amount        : ₹{surcharge_amount:,.2f}
Tax Plus Surcharge      : ₹{tax_plus_surcharge:,.2f}
========================================================
"""
        _logger.warning(summary_log)

        return SurchargeEngineResult(
            net_taxable_income=net_taxable_income,
            tax_after_rebate=tax_after_rebate,
            surcharge_rate_pct=surcharge_rate,
            surcharge_amount=surcharge_amount,
            tax_plus_surcharge=tax_plus_surcharge
        )
