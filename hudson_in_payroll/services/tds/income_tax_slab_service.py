# -*- coding: utf-8 -*-
import logging
from ..base import BaseStatutoryService

_logger = logging.getLogger(__name__)


class IncomeTaxSlabResult:
    """
    Data Transfer Object (DTO) holding income tax slab computation details.
    """
    def __init__(self, net_taxable_income, base_tax_liability, slab_breakdown):
        self.net_taxable_income = net_taxable_income
        self.base_tax_liability = base_tax_liability
        self.slab_breakdown = slab_breakdown


class IncomeTaxSlabService(BaseStatutoryService):
    """
    Phase 4 Pipeline Service: Income Tax Slab Engine Service.
    Resolves progressive income tax slabs from tds.tax.slab for the resolved Financial Year
    and Tax Regime, computing the base annual tax liability before rebates.
    """

    def calculate_base_tax(self, net_taxable_income, financial_year, regime_code):
        """
        Calculates progressive annual income tax before rebates.

        :param net_taxable_income: float (Net Taxable Income)
        :param financial_year: tds.financial.year record
        :param regime_code: str ('old' or 'new')
        :return: IncomeTaxSlabResult
        """
        regime_code = (regime_code or 'new').lower()

        # Query effective-dated income tax slabs from master
        slabs = self.env['tds.tax.slab'].search([
            ('financial_year_id', '=', financial_year.id),
            ('regime_code', '=', regime_code)
        ], order='income_from asc')

        # Fallback default slabs if unconfigured in seed data
        if not slabs:
            slabs = self._get_fallback_slabs(financial_year, regime_code)

        base_tax = 0.0
        slab_breakdown = []

        for slab in slabs:
            inc_from = slab.income_from
            inc_to = slab.income_to if slab.income_to > 0 else float('inf')
            rate = slab.rate / 100.0

            if net_taxable_income > inc_from:
                taxable_in_slab = min(net_taxable_income, inc_to) - inc_from
                if taxable_in_slab > 0:
                    tax_in_slab = taxable_in_slab * rate
                    base_tax += tax_in_slab
                    slab_breakdown.append({
                        'slab_name': slab.name or f"₹{inc_from:,.0f} - ₹{inc_to:,.0f}",
                        'income_from': inc_from,
                        'income_to': inc_to,
                        'taxable_amount': taxable_in_slab,
                        'rate_pct': slab.rate,
                        'tax_amount': tax_in_slab,
                    })

        _logger.warning("""[80E_AUDIT] TAX_SLAB_CALCULATION
taxable_income=%s""", net_taxable_income)
        for item in slab_breakdown:
            _logger.warning("[80E_AUDIT] SLAB: lower=%s upper=%s taxable=%s rate=%s tax=%s",
                item.get('income_from', 0.0), item.get('income_to', 0.0), item['taxable_amount'], item['rate_pct'], item['tax_amount'])
        _logger.warning("[80E_AUDIT] tax_before_rebate=%s", base_tax)

        breakdown_lines = []
        for item in slab_breakdown:
            breakdown_lines.append(f"- {item['slab_name']} @ {item['rate_pct']}%: ₹{item['tax_amount']:,.2f}")
        breakdown_text = "\n".join(breakdown_lines) if breakdown_lines else "- No taxable slabs applicable"

        summary_log = f"""
========================================================
INCOME TAX SLAB SERVICE
========================================================
Tax Regime              : {regime_code.upper()}
Net Taxable Income      : ₹{net_taxable_income:,.2f}

Slab Breakdown:
{breakdown_text}

Base Tax Liability      : ₹{base_tax:,.2f}
========================================================
"""
        _logger.warning("""[FORENSIC_TDS_TRACE]
step=ANNUAL_TAX_SLABS
input=net_taxable_income:INR %s, regime:%s, fy:%s
output=base_annual_tax_liability:INR %s, slab_count:%s
source_method=IncomeTaxSlabService.calculate_base_tax
branch_used=%s""",
            f"{net_taxable_income:,.2f}",
            regime_code.upper(),
            financial_year.code if financial_year else 'N/A',
            f"{base_tax:,.2f}",
            len(slab_breakdown),
            f"{'OLD_REGIME_SLAB_PROGRESSIVE_CALCULATION' if regime_code == 'old' else 'NEW_REGIME_115BAC_SLAB_PROGRESSIVE_CALCULATION'}"
        )

        return IncomeTaxSlabResult(
            net_taxable_income=net_taxable_income,
            base_tax_liability=base_tax,
            slab_breakdown=slab_breakdown
        )

    def _get_fallback_slabs(self, financial_year, regime_code):
        """Standard statutory fallbacks if tax slabs are unseeded."""
        class DummySlab:
            def __init__(self, name, inc_from, inc_to, rate):
                self.name = name
                self.income_from = inc_from
                self.income_to = inc_to
                self.rate = rate

        if regime_code == 'new':
            # New Regime Slabs (Finance Act 2025 / FY 2025-26)
            return [
                DummySlab("Up to ₹4.0L", 0.0, 400000.0, 0.0),
                DummySlab("₹4.0L - ₹8.0L", 400000.0, 800000.0, 5.0),
                DummySlab("₹8.0L - ₹12.0L", 800000.0, 1200000.0, 10.0),
                DummySlab("₹12.0L - ₹16.0L", 1200000.0, 1600000.0, 15.0),
                DummySlab("₹16.0L - ₹20.0L", 1600000.0, 2000000.0, 20.0),
                DummySlab("₹20.0L - ₹24.0L", 2000000.0, 2400000.0, 25.0),
                DummySlab("Above ₹24.0L", 2400000.0, 0.0, 30.0),
            ]
        else:
            # Old Regime Slabs
            return [
                DummySlab("Up to ₹2.5L", 0.0, 250000.0, 0.0),
                DummySlab("₹2.5L - ₹5.0L", 250000.0, 500000.0, 5.0),
                DummySlab("₹5.0L - ₹10.0L", 500000.0, 1000000.0, 20.0),
                DummySlab("Above ₹10.0L", 1000000.0, 0.0, 30.0),
            ]
