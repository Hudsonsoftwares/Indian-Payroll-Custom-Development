# -*- coding: utf-8 -*-
import logging
from odoo.exceptions import UserError, ValidationError
from ..base import BaseStatutoryService
from .salary_preview_service import SalaryPreviewService
from .payroll_refresh_service import PayrollRefreshService
from .statutory_refresh_service import StatutoryRefreshService
from ..audit.audit_service import StatutoryAuditSession

_logger = logging.getLogger(__name__)


class SalaryRevisionService(BaseStatutoryService):
    """
    Central Facade for Salary Revisions.
    Validates revision criteria, creates immutable historical revision records, updates active contracts,
    delegates statutory refreshes, and creates audit trail records.
    """

    def __init__(self, env):
        super().__init__(env)
        self.preview_service = SalaryPreviewService(env)
        self.payroll_refresh = PayrollRefreshService(env)
        self.statutory_refresh = StatutoryRefreshService(env)

    def execute_salary_revision(self, wizard):
        """
        Executes confirmed salary revision from wizard data.
        """
        employee = wizard.employee_id
        contract = wizard.contract_id or self._get_active_contract(employee)

        if not contract:
            raise UserError(self.env._("No active contract found for employee '%s'. Revisions require an active contract.") % employee.name)

        effective_date = wizard.effective_date
        if contract.date_start and effective_date < contract.date_start:
            raise ValidationError(self.env._("Revision effective date (%s) cannot precede contract start date (%s).") % (effective_date, contract.date_start))

        current_wage = contract.wage or 0.0
        new_wage = wizard.revised_wage

        if new_wage <= 0.0:
            raise ValidationError(self.env._("Revised gross wage must be greater than zero."))

        # Check for duplicate revision on same effective date
        existing = self.env['hds.in.salary.revision'].search([
            ('employee_id', '=', employee.id),
            ('effective_date', '=', effective_date),
            ('state', '=', 'approved')
        ], limit=1)
        if existing:
            raise ValidationError(self.env._("A confirmed salary revision already exists for employee '%s' on effective date %s.") % (employee.name, effective_date))

        # 1. Preview Impact
        preview = self.preview_service.calculate_preview(employee, current_wage, new_wage, effective_date=effective_date)

        # 2. Create Immutable Salary Revision Record
        revision_vals = {
            'employee_id': employee.id,
            'contract_id': contract.id,
            'effective_date': effective_date,
            'revision_type': wizard.revision_type,
            'revision_basis': wizard.revision_basis,
            'capped_wage_amount': wizard.capped_wage_amount,
            'computation_type': wizard.computation_type,
            'increase_percentage': wizard.increase_percentage,
            'increase_amount': wizard.increase_amount,
            'old_wage': current_wage,
            'new_wage': new_wage,
            'wage_difference': preview['wage_difference'],
            'old_employer_cost_monthly': preview['old_ctc'],
            'new_employer_cost_monthly': preview['new_ctc'],
            'old_epf_wage': preview['old_epf_wage'],
            'new_epf_wage': preview['new_epf_wage'],
            'old_employee_epf': preview['old_ee_epf'],
            'new_employee_epf': preview['new_ee_epf'],
            'old_employer_pf': preview['old_er_pf'],
            'new_employer_pf': preview['new_er_pf'],
            'old_esic_applicable': preview['old_esic_app'],
            'new_esic_applicable': preview['new_esic_app'],
            'old_employee_esic': preview['old_ee_esic'],
            'new_employee_esic': preview['new_ee_esic'],
            'old_employer_esic': preview['old_er_esic'],
            'new_employer_esic': preview['new_er_esic'],
            'old_pt_amount': 0.0,
            'new_pt_amount': preview['pt_amount'],
            'old_lwf_amount': 0.0,
            'new_lwf_amount': preview['lwf_amount'],
            'reason': wizard.reason,
            'notes': wizard.notes,
            'state': 'approved',
            'created_by_id': self.env.uid,
        }
        revision_record = self.env['hds.in.salary.revision'].create(revision_vals)

        # 3. Update Active Employee Contract
        mode = getattr(wizard, 'breakdown_distribution_mode', 'auto_structure')
        manual_dict = wizard._get_manual_breakdown_dict() if hasattr(wizard, '_get_manual_breakdown_dict') and mode == 'manual_adjust' else None
        self.payroll_refresh.refresh_contract_payroll(
            contract, new_wage, effective_date=effective_date, mode=mode, manual_dict=manual_dict
        )

        # 4. Refresh Statutory Components
        self.statutory_refresh.refresh_statutory_components(employee, new_wage, effective_date=effective_date)

        # 5. Audit Logging
        payslip_dummy = self.env['hr.payslip'].search([('employee_id', '=', employee.id)], limit=1)
        if not payslip_dummy:
            class DummyPayslip:
                def __init__(self, emp):
                    self.employee_id = emp
                    self.company_id = emp.company_id or emp.env.company
                    self.id = False
                    self.date_to = effective_date or fields.Date.today()
            payslip_dummy = DummyPayslip(employee)

        with StatutoryAuditSession(self.env, payslip_dummy, statutory_module='revision', rule_code='SALARY_REVISION') as audit:
            audit.attach_input('old_wage', current_wage)
            audit.attach_input('new_wage', new_wage)
            audit.attach_parameter('REVISION_TYPE', wizard.revision_type)
            audit.attach_parameter('REVISION_BASIS', wizard.revision_basis)
            audit.attach_output('revision_record_id', revision_record.id)

        _logger.info(
            "[SalaryRevisionService] Executed salary revision %s for Employee %s: Gross %s -> %s",
            revision_record.name, employee.name, current_wage, new_wage
        )

        return revision_record

    def _get_active_contract(self, employee):
        contracts = self.env['hr.version'].search([('employee_id', '=', employee.id)])
        return contracts.sorted(lambda c: c.date_start or fields.Date.today(), reverse=True)[0] if contracts else False
