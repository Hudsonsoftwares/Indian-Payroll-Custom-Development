# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


class PayrollWorkLocationService:
    """
    Domain Service for determining an employee's statutory work state.
    Provides a centralized, 3-tier resolution chain reusable across all state-wise
    statutory compliance engines (LWF, Professional Tax, Minimum Wages, S&E).

    Lookup Priority:
    1. employee.work_location_id.address_id.state_id  (Physical work location partner state)
    2. employee.address_id.state_id                    (Direct employee work address partner state)
    3. employee.company_id.partner_id.state_id        (Registered company legal partner state)
    """

    def __init__(self, env):
        self.env = env

    def get_work_state(self, employee):
        """
        Resolves the statutory state (res.country.state recordset) for a given employee.

        :param employee: hr.employee recordset (single record)
        :return: res.country.state recordset or False
        """
        if not employee:
            return False

        # 1. Primary: Work Location Partner State
        if employee.work_location_id and employee.work_location_id.address_id and employee.work_location_id.address_id.state_id:
            return employee.work_location_id.address_id.state_id

        # 2. Secondary: Direct Employee Work Address Partner State
        if employee.address_id and employee.address_id.state_id:
            return employee.address_id.state_id

        # 3. Fallback: Registered Company Partner State
        company = employee.company_id or self.env.company
        if company and company.partner_id and company.partner_id.state_id:
            return company.partner_id.state_id

        _logger.warning("Statutory work state could not be resolved for employee %s (ID: %s)", employee.name, employee.id)
        return False
