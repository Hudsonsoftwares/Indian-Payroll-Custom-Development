# -*- coding: utf-8 -*-
from odoo import fields
import logging
try:
    from ..base import BaseStatutoryService
    from ..audit.audit_service import StatutoryAuditSession
    from .leave_encashment_validator import LeaveEncashmentValidator
    from .leave_encashment_data_service import LeaveEncashmentDataService
    from .leave_encashment_calculator import LeaveEncashmentCalculator
except (ImportError, ValueError):
    from base_service import BaseStatutoryService
    from leave_encashment_validator import LeaveEncashmentValidator
    from leave_encashment_data_service import LeaveEncashmentDataService
    from leave_encashment_calculator import LeaveEncashmentCalculator
    StatutoryAuditSession = None

_logger = logging.getLogger(__name__)


class LeaveEncashmentService(BaseStatutoryService):
    """
    Orchestration Facade Service for Leave Encashment statutory calculation.
    Coordinates SOA components:
    1. LeaveEncashmentValidator
    2. LeaveEncashmentDataService
    3. LeaveEncashmentCalculator
    4. StatutoryAuditSession
    """

    def __init__(self, env, localdict=None):
        super().__init__(env)
        self.localdict = localdict or {}
        self.validator = LeaveEncashmentValidator(env)
        self.data_service = LeaveEncashmentDataService(env)
        self.calculator = LeaveEncashmentCalculator()

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

    def compute_leave_encashment(
        self,
        employee=None,
        last_working_day=None,
        contract=None,
        payslip=None,
        calc_date=None
    ):
        """
        Computes Leave Encashment amount via SOA component orchestration.

        :param employee: optional hr.employee recordset (resolved from payslip or localdict if None)
        :param last_working_day: optional str or date (employee last working day)
        :param contract: optional hr.version recordset
        :param payslip: optional hr.payslip recordset
        :param calc_date: optional reference date
        :return: float (payable leave encashment amount)
        """
        slip, resolved_emp, eval_date, company = self._extract_payslip_and_employee(payslip)
        emp = employee or resolved_emp
        ctr = contract or (getattr(slip, 'contract_id', None) if slip else None) or self.localdict.get('contract')
        ref_date = calc_date or eval_date

        with StatutoryAuditSession(
            self.env,
            slip,
            statutory_module="leave_encashment",
            rule_code="LEAVE_ENCASH",
            calculation_type="final_settlement"
        ) as audit:
            audit.attach_input("employee_id", emp.id if emp else False)
            audit.attach_input("employee_name", emp.name if emp else False)
            audit.attach_input("eval_date", str(ref_date))

            # 1. Statutory & Policy Eligibility Validation
            val_result = self.validator.validate(
                employee=emp,
                last_working_day=last_working_day
            )
            audit.attach_parameter("is_eligible", val_result.is_eligible)
            audit.attach_parameter("validation_reason", val_result.reason)
            audit.attach_parameter("last_working_day", str(val_result.last_working_day) if val_result.last_working_day else None)

            if not val_result.is_eligible:
                audit.log_message(val_result.reason)
                audit.attach_output("final_amount", 0.0)
                return 0.0

            # 2. Gather & Prepare Calculation Data DTO
            calc_data = self.data_service.prepare_calculation_data(
                employee=emp,
                contract=ctr,
                last_working_day=last_working_day or val_result.last_working_day,
                calc_date=ref_date
            )
            audit.attach_parameter("wage_base", calc_data.wage_base)
            audit.attach_parameter("basic_wage", calc_data.basic_wage)
            audit.attach_parameter("da_amount", calc_data.da_amount)
            audit.attach_parameter("month_divisor", calc_data.month_divisor)
            audit.attach_parameter("max_encashable_days", calc_data.max_encashable_days)
            audit.attach_parameter("total_eligible_days", calc_data.total_eligible_days)
            audit.attach_parameter("leave_breakdown", calc_data.leave_breakdown)

            # 3. Perform Pure Calculation
            calc_result = self.calculator.calculate(calc_data)
            audit.attach_output("leave_days_used", calc_result.leave_days_used)
            audit.attach_output("daily_rate_used", calc_result.daily_rate_used)
            audit.attach_output("raw_amount", calc_result.raw_amount)
            audit.attach_output("capped_amount", calc_result.capped_amount)
            audit.attach_output("final_amount", calc_result.final_amount)
            audit.attach_output("is_cap_applied", calc_result.is_cap_applied)
            audit.attach_output("max_encashable_days_used", calc_result.max_encashable_days_used)

            return calc_result.final_amount
