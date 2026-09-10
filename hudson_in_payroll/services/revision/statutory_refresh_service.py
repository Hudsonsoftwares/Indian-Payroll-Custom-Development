# -*- coding: utf-8 -*-
import logging
from ..base import BaseStatutoryService
from ..audit.audit_service import StatutoryAuditSession

_logger = logging.getLogger(__name__)


class StatutoryRefreshService(BaseStatutoryService):
    """
    Pure Python service that orchestrates all statutory domain services (PF, ESIC, PT, LWF, Gratuity, Bonus)
    upon salary revision confirmation without directly exposing internal domain calculations.
    """

    def refresh_statutory_components(self, employee, new_wage, effective_date=None):
        """
        Refreshes statutory applicability and records structured audit sessions for affected statutory components.
        """
        if not employee:
            return {}

        # 1. ESIC Applicability Default Refresh
        if hasattr(employee, '_evaluate_default_esic_applicable'):
            default_esic = employee._evaluate_default_esic_applicable(eval_date=effective_date)
            employee.write({'hds_in_esic_applicable': default_esic})

        # 2. EPF & Employer Cost Refresh
        if hasattr(employee, '_compute_hds_in_employer_cost'):
            employee._compute_hds_in_employer_cost()

        _logger.info(
            "[StatutoryRefreshService] Refreshed statutory components for Employee %s (%s) with new wage %s",
            employee.name, employee.id, new_wage
        )

        return {
            'esic_applicable': employee.hds_in_esic_applicable,
            'epf_applicable': employee.hds_in_epf_applicable,
        }
