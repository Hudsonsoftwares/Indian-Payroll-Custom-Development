# -*- coding: utf-8 -*-
import logging
from odoo import fields
from ..base import BaseStatutoryService
from ..audit.audit_service import StatutoryAuditSession
from ..payroll.work_location_service import PayrollWorkLocationService
from .lwf_rate_service import LWFRateService
from .company_configuration_validator import CompanyConfigurationValidator
from .lwf_eligibility_validator import LWFEligibilityValidator
from .lwf_calculator import LWFCalculator

_logger = logging.getLogger(__name__)


class LWFService(BaseStatutoryService):
    """
    Thin Orchestration Facade for Labour Welfare Fund (LWF) statutory calculations.
    Coordinates sub-components in strict SOA order:
    1. CompanyConfigurationValidator
    2. PayrollWorkLocationService
    3. LWFRateService
    4. LWFEligibilityValidator
    5. LWFCalculator
    6. StatutoryAuditSession
    """

    def __init__(self, env, localdict=None):
        super().__init__(env)
        self.localdict = localdict or {}
        self.company_validator = CompanyConfigurationValidator(env)
        self.location_service = PayrollWorkLocationService(env)
        self.rate_service = LWFRateService(env)
        self.eligibility_validator = LWFEligibilityValidator(env)
        self.calculator = LWFCalculator(env)

    def _extract_payslip_and_employee(self, payslip=None):
        slip = payslip or self.localdict.get('payslip_record') or self.localdict.get('payslip')
        employee = False
        eval_date = fields.Date.today()
        company = self.env.company

        if slip:
            employee = getattr(slip, 'employee_id', False)
            eval_date = getattr(slip, 'date_to', fields.Date.today()) or fields.Date.today()
            company = getattr(slip, 'company_id', False) or self.env.company
        elif self.localdict.get('employee'):
            employee = self.localdict.get('employee')
            company = getattr(employee, 'company_id', False) or self.env.company

        return slip, employee, eval_date, company

    def _get_establishment_employee_count(self, employee, company):
        """Helper to get active employee headcount in the establishment/company."""
        if not company:
            return 0
        domain = [('company_id', '=', company.id), ('active', '=', True)]
        return self.env['hr.employee'].search_count(domain)

    def compute_lwf_employee(self, payslip=None):
        """
        Computes Employee LWF statutory deduction amount via SOA components.

        :param payslip: optional hr.payslip recordset
        :return: float (employee contribution amount in INR)
        """
        slip, employee, eval_date, company = self._extract_payslip_and_employee(payslip)
        with StatutoryAuditSession(self.env, slip, statutory_module="lwf", rule_code="LWF_EE", calculation_type="employee_contribution") as audit:
            audit.attach_input("employee_id", employee.id if employee else False)
            audit.attach_input("employee_name", employee.name if employee else False)
            audit.attach_input("eval_date", str(eval_date))

            # 1. Company Configuration Validation
            comp_result = self.company_validator.validate(company)
            audit.attach_parameter("company_enabled", comp_result.is_enabled)
            audit.attach_parameter("company_registration_no", comp_result.registration_no)
            if not comp_result.is_valid:
                audit.log_message(comp_result.reason)
                return 0.0

            # 2. Location Service Resolution
            state = self.location_service.get_work_state(employee)
            audit.attach_parameter("resolved_state", state.name if state else False)

            # 3. Rate Service Query
            rate_config = self.rate_service.get_rate_config(state, eval_date=eval_date, company=company)
            audit.attach_parameter("rate_config_id", rate_config.id if rate_config else False)

            # 4. Eligibility Validation
            headcount = self._get_establishment_employee_count(employee, company)
            elig_result = self.eligibility_validator.validate(
                employee=employee,
                state=state,
                rate_config=rate_config,
                eval_date=eval_date,
                establishment_headcount=headcount
            )
            audit.attach_parameter("min_employee_count_threshold", elig_result.min_threshold)
            audit.attach_parameter("establishment_employee_headcount", elig_result.headcount)
            audit.attach_parameter("is_deduction_month", elig_result.is_scheduled_month)

            if not elig_result.is_eligible:
                audit.log_message(elig_result.reason)
                return 0.0

            # 5. Calculation
            amount = self.calculator.calculate_employee_contribution(rate_config)
            audit.attach_output("emp_contribution", amount)
            return amount

    def compute_lwf_employer(self, payslip=None):
        """
        Computes Employer LWF statutory contribution amount via SOA components.

        :param payslip: optional hr.payslip recordset
        :return: float (employer contribution amount in INR)
        """
        slip, employee, eval_date, company = self._extract_payslip_and_employee(payslip)
        with StatutoryAuditSession(self.env, slip, statutory_module="lwf", rule_code="LWF_ER", calculation_type="employer_contribution") as audit:
            audit.attach_input("employee_id", employee.id if employee else False)
            audit.attach_input("employee_name", employee.name if employee else False)
            audit.attach_input("eval_date", str(eval_date))

            # 1. Company Configuration Validation
            comp_result = self.company_validator.validate(company)
            audit.attach_parameter("company_enabled", comp_result.is_enabled)
            audit.attach_parameter("company_registration_no", comp_result.registration_no)
            if not comp_result.is_valid:
                audit.log_message(comp_result.reason)
                return 0.0

            # 2. Location Service Resolution
            state = self.location_service.get_work_state(employee)
            audit.attach_parameter("resolved_state", state.name if state else False)

            # 3. Rate Service Query
            rate_config = self.rate_service.get_rate_config(state, eval_date=eval_date, company=company)
            audit.attach_parameter("rate_config_id", rate_config.id if rate_config else False)

            # 4. Eligibility Validation
            headcount = self._get_establishment_employee_count(employee, company)
            elig_result = self.eligibility_validator.validate(
                employee=employee,
                state=state,
                rate_config=rate_config,
                eval_date=eval_date,
                establishment_headcount=headcount
            )
            audit.attach_parameter("min_employee_count_threshold", elig_result.min_threshold)
            audit.attach_parameter("establishment_employee_headcount", elig_result.headcount)
            audit.attach_parameter("is_deduction_month", elig_result.is_scheduled_month)

            if not elig_result.is_eligible:
                audit.log_message(elig_result.reason)
                return 0.0

            # 5. Calculation
            amount = self.calculator.calculate_employer_contribution(rate_config)
            audit.attach_output("empl_contribution", amount)
            return amount
