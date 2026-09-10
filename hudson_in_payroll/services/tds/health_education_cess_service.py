# -*- coding: utf-8 -*-
import logging
from ..base import BaseStatutoryService
from .tds_parameter_service import TdsParameterService

_logger = logging.getLogger(__name__)


class HealthEducationCessResult:
    """
    Data Transfer Object (DTO) holding Health & Education Cess and Total Annual Tax Liability details.
    """
    def __init__(self, tax_plus_surcharge, cess_rate_pct, cess_amount, total_annual_tax_liability):
        self.tax_plus_surcharge = tax_plus_surcharge
        self.cess_rate_pct = cess_rate_pct
        self.cess_amount = cess_amount
        self.total_annual_tax_liability = total_annual_tax_liability


class HealthEducationCessService(BaseStatutoryService):
    """
    Phase 4 Pipeline Service: Health & Education Cess Engine Service.
    Resolves the statutory Health & Education Cess percentage (4.0%) via TdsParameterService (HEALTH_CESS).
    Applies Cess to (Tax + Surcharge - Rebate) and computes final Total Annual Income Tax Liability.
    """

    def calculate_cess(self, tax_plus_surcharge, eval_date=None):
        """
        Calculates Health & Education Cess and total annual tax liability.

        :param tax_plus_surcharge: float (Income tax after rebate + surcharge)
        :param eval_date: Date (optional)
        :return: HealthEducationCessResult
        """
        if tax_plus_surcharge <= 0:
            return HealthEducationCessResult(
                tax_plus_surcharge=0.0,
                cess_rate_pct=4.0,
                cess_amount=0.0,
                total_annual_tax_liability=0.0
            )

        tds_param_svc = TdsParameterService(self.env)
        # Resolve Health & Education Cess rate (4%) via TdsParameterService
        cess_rate = tds_param_svc.get_parameter('HEALTH_CESS', eval_date=eval_date) or 4.0

        cess_amount = round(tax_plus_surcharge * (cess_rate / 100.0), 2)
        total_annual_tax_liability = round(tax_plus_surcharge + cess_amount, 2)

        summary_log = f"""
========================================================
HEALTH & EDUCATION CESS SERVICE
========================================================
Tax After Rebate / Surcharge : ₹{tax_plus_surcharge:,.2f}
Cess Rate                    : {cess_rate}%
Cess Amount                  : ₹{cess_amount:,.2f}
Final Annual Tax             : ₹{total_annual_tax_liability:,.2f}
========================================================
"""
        _logger.warning(summary_log)

        return HealthEducationCessResult(
            tax_plus_surcharge=tax_plus_surcharge,
            cess_rate_pct=cess_rate,
            cess_amount=cess_amount,
            total_annual_tax_liability=total_annual_tax_liability
        )
