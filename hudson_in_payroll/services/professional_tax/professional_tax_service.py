# -*- coding: utf-8 -*-
import logging
from odoo import fields
from ..base import BaseStatutoryService
from ..audit.audit_service import StatutoryAuditSession
from ..payroll.work_location_service import PayrollWorkLocationService
from .professional_tax_slab_service import ProfessionalTaxSlabService
from .pt_validator import PTValidator
from .pt_calculator import PTCalculator

from .pt_periodicity_strategy import PTPeriodicityStrategyRegistry

_logger = logging.getLogger(__name__)


class ProfessionalTaxResult:
    """
    Structured Result Container representing the end-to-end Professional Tax calculation result.
    Encapsulates final deduction amount, state, company, slab, override metadata, and validation status.
    """

    def __init__(
        self,
        amount=0.0,
        state=None,
        company=None,
        slab=None,
        override_applied=False,
        override_month=None,
        override_amount=None,
        is_valid=True,
        validation_status="VALID",
        failure_reason=""
    ):
        self.amount = amount
        self.state = state
        self.company = company
        self.slab = slab
        self.salary_from = getattr(slab, 'salary_from', None) if slab else None
        self.salary_to = getattr(slab, 'salary_to', None) if slab else None
        self.periodicity = getattr(slab, 'periodicity', None) if slab else None
        self.override_applied = override_applied
        self.override_month = override_month
        self.override_amount = override_amount
        self.is_valid = is_valid
        self.validation_status = validation_status
        self.failure_reason = failure_reason

    def to_dict(self):
        """Returns a structured dictionary representation of the orchestrated result."""
        return {
            'amount': self.amount,
            'state_id': self.state.id if self.state else False,
            'state_name': self.state.name if self.state else False,
            'company_id': self.company.id if self.company else False,
            'company_name': self.company.name if self.company else False,
            'salary_from': self.salary_from,
            'salary_to': self.salary_to,
            'periodicity': self.periodicity,
            'override_applied': self.override_applied,
            'override_month': self.override_month,
            'override_amount': self.override_amount,
            'is_valid': self.is_valid,
            'validation_status': self.validation_status,
            'failure_reason': self.failure_reason,
            'slab': self.slab.to_dict() if (self.slab and hasattr(self.slab, 'to_dict')) else False,
        }

    def __repr__(self):
        return (
            f"<ProfessionalTaxResult amount={self.amount} state={self.state.name if self.state else None} "
            f"valid={self.is_valid} status=''{self.validation_status}'' override_applied={self.override_applied}>"
        )


class ProfessionalTaxService(BaseStatutoryService):
    """
    Domain Facade and Thin Orchestration Service for Indian Professional Tax (PT).
    Coordinates sub-services in strict SOA order:
    1. Context Extraction (Payslip / Localdict / Explicit parameters)
    2. Company Configuration Check (res.company PT settings)
    3. Work Location Resolution (PayrollWorkLocationService)
    4. Periodicity & Strategy Resolution (PTPeriodicityStrategyRegistry)
    5. Wage Aggregation (PayrollWageAggregationService / Strategy)
    6. PT Slab Resolution (ProfessionalTaxSlabService)
    7. Eligibility & Deduction Schedule Validation (PTValidator)
    8. PT Amount Calculation (PTCalculator)
    9. Statutory Audit Session Integration (Audit Readiness)
    """

    def __init__(self, env, localdict=None):
        super().__init__(env)
        self.localdict = localdict or {}
        self.location_service = PayrollWorkLocationService(env)
        self.slab_service = ProfessionalTaxSlabService(env)
        from .pt_period_config_service import PTPeriodScheduleService
        self.sched_service = PTPeriodScheduleService(env)
        self.validator = PTValidator(env)
        self.calculator = PTCalculator(env)

    def _extract_context(self, payslip=None, employee=None, salary=0.0, eval_date=None, company=None, gender=None, localdict=None):
        """
        Extracts execution parameters from explicit arguments or payslip/localdict context.
        """
        dict_ctx = localdict if localdict is not None else self.localdict
        slip = payslip or dict_ctx.get('payslip_record') or dict_ctx.get('payslip') or dict_ctx.get('ps')

        target_emp = employee
        if not target_emp and slip:
            target_emp = getattr(slip, 'employee_id', False)
        if not target_emp:
            target_emp = dict_ctx.get('employee')

        target_date = eval_date
        if not target_date and slip:
            target_date = getattr(slip, 'date_to', False) or getattr(slip, 'date_from', False)
        if not target_date:
            target_date = dict_ctx.get('eval_date') or fields.Date.today()
        if isinstance(target_date, str):
            target_date = fields.Date.from_string(target_date)

        target_company = company
        if not target_company and slip:
            target_company = getattr(slip, 'company_id', False)
        if not target_company and target_emp:
            target_company = getattr(target_emp, 'company_id', False)
        if not target_company:
            target_company = dict_ctx.get('company') or self.env.company

        target_salary = salary
        if not target_salary and dict_ctx:
            categories = dict_ctx.get('categories')
            if categories:
                target_salary = (
                    getattr(categories, 'GROSS_PT', 0.0) or
                    getattr(categories, 'PT_BASE', 0.0) or
                    getattr(categories, 'GROSS', 0.0) or 0.0
                )
            if not target_salary:
                target_salary = dict_ctx.get('gross_salary') or dict_ctx.get('salary') or 0.0
        if not target_salary and target_emp and getattr(target_emp, 'contract_id', False):
            target_salary = getattr(target_emp.contract_id, 'wage', 0.0) or 0.0

        try:
            target_salary = float(target_salary or 0.0)
        except (TypeError, ValueError):
            target_salary = 0.0

        if slip and hasattr(slip, '_get_earned_wage_ratio'):
            ratio = slip._get_earned_wage_ratio(localdict=dict_ctx)
            target_salary = round(target_salary * ratio, 2)

        target_gender = gender
        if not target_gender and target_emp:
            target_gender = self.slab_service.resolve_employee_gender(target_emp)

        return slip, target_emp, target_salary, target_date, target_company, target_gender

    def compute_pt(self, payslip=None, employee=None, salary=0.0, eval_date=None, company=None, gender=None, localdict=None):
        """
        Orchestrates end-to-end Professional Tax computation via SOA components and periodicity strategies.

        :param payslip: hr.payslip recordset or None
        :param employee: hr.employee recordset or None
        :param salary: float (monthly gross/taxable salary override)
        :param eval_date: datetime.date or str or None
        :param company: res.company recordset or None
        :param gender: str or None
        :param localdict: dict or None (payslip execution context)
        :return: ProfessionalTaxResult instance
        """
        slip, emp, sal, date_eval, comp, gdr = self._extract_context(
            payslip=payslip, employee=employee, salary=salary,
            eval_date=eval_date, company=company, gender=gender, localdict=localdict
        )

        with StatutoryAuditSession(self.env, slip, statutory_module="pt", rule_code="PT", calculation_type="employee_deduction") as audit:
            audit.attach_input("employee_id", emp.id if emp else False)
            audit.attach_input("employee_name", emp.name if emp else False)
            audit.attach_input("eval_date", str(date_eval))
            audit.attach_input("single_month_salary", sal)
            audit.attach_input("company_id", comp.id if comp else False)

            # 1. Location Service State Resolution
            state = self.location_service.get_work_state(emp)
            audit.attach_parameter("resolved_state", state.name if state else False)

            # 2. Period Schedule & Strategy Resolution (Decoupled from slabs)
            period_sched = self.sched_service.resolve_schedule(state, company=comp, eval_date=date_eval)
            periodicity = period_sched.periodicity if period_sched else self.slab_service.resolve_state_periodicity(state, company=comp)
            strategy = PTPeriodicityStrategyRegistry.get_strategy(periodicity)
            audit.attach_parameter("periodicity", periodicity)
            if period_sched:
                audit.attach_parameter("period_schedule_id", period_sched.id)
                audit.attach_parameter("deduction_strategy", period_sched.deduction_strategy)

            # 3. Wage Aggregation Basis Resolution (Monthly vs Half-Yearly vs Quarterly)
            salary_basis = strategy.calculate_wage_basis(
                self.env, emp, date_eval, current_slip=slip, current_slip_gross=sal, company=comp, period_schedule=period_sched
            )
            audit.attach_input("salary_basis", salary_basis)

            # 4. Validator Eligibility & Deduction Schedule Check
            val_result = self.validator.validate(
                employee=emp, salary=salary_basis, eval_date=date_eval, company=comp, state=state, gender=gdr, periodicity=periodicity, strategy=strategy, period_schedule=period_sched
            )
            audit.attach_parameter("validation_status", val_result.validation_status)
            audit.attach_parameter("is_valid", val_result.is_valid)
            audit.attach_parameter("failure_reason", val_result.failure_reason)

            slab_rec = val_result.matched_slab.slab_record if (val_result and val_result.matched_slab) else None
            if period_sched:
                audit.attach_parameter("deduction_strategy", period_sched.deduction_strategy)
                audit.attach_parameter("deduction_month", period_sched.deduction_month or False)

            if not val_result.is_valid:
                audit.log_message(val_result.failure_reason)
                return ProfessionalTaxResult(
                    amount=0.0,
                    state=state or val_result.resolved_state,
                    company=comp,
                    slab=val_result.matched_slab,
                    is_valid=False,
                    validation_status=val_result.validation_status,
                    failure_reason=val_result.failure_reason
                )

            # 5. Calculator Amount Computation & Strategy Recovery
            calc_result = self.calculator.calculate(slab=val_result.matched_slab, eval_date=date_eval)
            period_liability = calc_result.pt_amount

            final_deduction = strategy.calculate_payroll_deduction(
                self.env,
                employee=emp,
                period_liability=period_liability,
                eval_date=date_eval,
                current_slip=slip,
                period_schedule=period_sched
            )
            _logger.warning("Statutory PT Liability: %s | Current Payroll Deduction: %s", period_liability, final_deduction)

            audit.attach_parameter("period_liability", period_liability)
            audit.attach_parameter("normal_amount", calc_result.normal_amount)
            audit.attach_parameter("override_applied", calc_result.override_applied)
            audit.attach_parameter("override_month", calc_result.override_month)
            audit.attach_parameter("override_amount", calc_result.override_amount)
            audit.attach_output("pt_deduction", final_deduction)

            return ProfessionalTaxResult(
                amount=final_deduction,
                state=val_result.resolved_state or state,
                company=comp,
                slab=val_result.matched_slab,
                override_applied=calc_result.override_applied,
                override_month=calc_result.override_month,
                override_amount=calc_result.override_amount,
                is_valid=True,
                validation_status='VALID',
                failure_reason="Professional Tax deduction calculated successfully."
            )

    def compute_pt_amount(self, payslip=None, employee=None, salary=0.0, eval_date=None, company=None, gender=None, localdict=None):
        """
        Helper method returning float deduction amount for direct salary rule consumption.
        """
        res = self.compute_pt(
            payslip=payslip, employee=employee, salary=salary,
            eval_date=eval_date, company=company, gender=gender, localdict=localdict
        )
        return res.amount
