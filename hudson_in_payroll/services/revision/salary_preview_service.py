# -*- coding: utf-8 -*-
from odoo import fields
from ..base import BaseStatutoryService
from ..epf.epf_service import EPFService
from ..esic.esic_service import ESICService


class SimulationPayslip:
    """
    Lightweight, non-persisted simulation payslip object designed to bridge
    the Salary Revision Engine with pure statutory domain services (EPFService, ESICService).
    """

    def __init__(self, env, employee, eval_date, eval_ctx):
        self.env = env
        self.employee_id = employee
        self.company_id = employee.company_id or env.company
        self.date_to = eval_date or fields.Date.today()
        self.id = False
        self.eval_ctx = eval_ctx

    def hds_in_get_actual_pf_wage(self, localdict=None):
        """
        Delegates actual PF wage calculation to evaluated localdict context.
        Sums up rules configured with hds_in_include_in_pf_wage = True.
        """
        ld = localdict or self.eval_ctx
        pf_wage = 0.0
        if ld:
            pf_rules = self.env['hr.salary.rule'].search([
                ('hds_in_include_in_pf_wage', '=', True)
            ])
            for rule in pf_rules:
                amount = float(ld.get(rule.code, 0.0) or 0.0)
                pf_wage += amount
            if pf_wage > 0.0:
                return pf_wage

        # Fallback to BASIC or GROSS in eval_ctx
        return float(self.eval_ctx.get('BASIC', 0.0) or self.eval_ctx.get('GROSS', 0.0) or 0.0)


class SalaryPreviewService(BaseStatutoryService):
    """
    Pure Python consumer service that calculates simulated before-and-after statutory
    and payroll breakdowns for proposed salary revisions by delegating 100% of calculation
    responsibility to production domain services (EPFService, ESICService).
    """

    def calculate_preview(self, employee, current_wage, revised_wage, effective_date=None, mode='auto_structure', manual_dict=None):
        """
        Calculates live before/after statutory impact preview for a given employee and wage pair.
        Delegates 100% of EPF and ESIC statutory logic to EPFService and ESICService.
        """
        if effective_date is None:
            effective_date = self.env.context.get('date') or fields.Date.today()

        # 1. Build simulation evaluation contexts for current & revised wages
        old_ctx = self._build_simulation_context(employee, current_wage, mode='keep_existing')
        new_ctx = self._build_simulation_context(employee, revised_wage, mode=mode, manual_dict=manual_dict)

        old_sim_payslip = SimulationPayslip(self.env, employee, effective_date, old_ctx)
        new_sim_payslip = SimulationPayslip(self.env, employee, effective_date, new_ctx)

        # 2. Instantiate EPF Domain Service with simulation context
        old_epf_service = EPFService(self.env, localdict=old_ctx)
        new_epf_service = EPFService(self.env, localdict=new_ctx)

        old_epf_wage = old_epf_service.compute_pf_wage(old_sim_payslip) if employee.hds_in_epf_applicable else 0.0
        new_epf_wage = new_epf_service.compute_pf_wage(new_sim_payslip) if employee.hds_in_epf_applicable else 0.0

        old_ee_epf = old_epf_service.compute_employee_epf(old_sim_payslip) if employee.hds_in_epf_applicable else 0.0
        new_ee_epf = new_epf_service.compute_employee_epf(new_sim_payslip) if employee.hds_in_epf_applicable else 0.0

        old_er_pf = old_epf_service.compute_employer_total_pf(old_sim_payslip) if employee.hds_in_epf_applicable else 0.0
        new_er_pf = new_epf_service.compute_employer_total_pf(new_sim_payslip) if employee.hds_in_epf_applicable else 0.0

        old_eps = old_epf_service.compute_employer_eps(old_sim_payslip) if employee.hds_in_eps_applicable else 0.0
        new_eps = new_epf_service.compute_employer_eps(new_sim_payslip) if employee.hds_in_eps_applicable else 0.0

        old_edli = old_epf_service.compute_employer_edli(old_sim_payslip) if employee.hds_in_epf_applicable else 0.0
        new_edli = new_epf_service.compute_employer_edli(new_sim_payslip) if employee.hds_in_epf_applicable else 0.0

        # 3. Instantiate ESIC Domain Service with simulation context
        old_esic_service = ESICService(self.env, localdict=old_ctx)
        new_esic_service = ESICService(self.env, localdict=new_ctx)

        company = employee.company_id or self.env.company
        from ..esic.contribution_period_service import ESICContributionPeriodService
        period_service = ESICContributionPeriodService(self.env)
        is_esic_covered = period_service.is_covered_for_contribution_period(employee, eval_date=effective_date)

        old_esic_app = bool(company.hds_in_esic_applicable and employee.hds_in_esic_applicable and is_esic_covered)
        new_esic_app = bool(company.hds_in_esic_applicable and employee.hds_in_esic_applicable and is_esic_covered)

        old_ee_esic = old_esic_service.compute_esic_employee(old_sim_payslip) if old_esic_app else 0.0
        new_ee_esic = new_esic_service.compute_esic_employee(new_sim_payslip) if new_esic_app else 0.0

        old_er_esic = old_esic_service.compute_esic_employer(old_sim_payslip) if old_esic_app else 0.0
        new_er_esic = new_esic_service.compute_esic_employer(new_sim_payslip) if new_esic_app else 0.0

        # 4. Professional Tax & LWF Simulation
        pt_amount = 200.0 if revised_wage > 15000.0 else 0.0
        lwf_amount = 20.0

        # 5. Employer Cost (CTC) Simulation
        old_ctc = current_wage + old_er_pf + old_edli + (old_epf_wage * 0.005 if employee.hds_in_epf_applicable else 0.0) + old_er_esic
        new_ctc = revised_wage + new_er_pf + new_edli + (new_epf_wage * 0.005 if employee.hds_in_epf_applicable else 0.0) + new_er_esic

        # Statutory Contribution Period Details for UI Preview
        import datetime
        cur_start, cur_end = period_service.get_contribution_period_bounds(effective_date)
        esic_cur_period_label = f"({cur_start.strftime('%b %Y')} – {cur_end.strftime('%b %Y')})"
        esic_cur_period_status = old_esic_app or new_esic_app

        next_ref_date = cur_end + datetime.timedelta(days=1)
        next_start, next_end = period_service.get_contribution_period_bounds(next_ref_date)
        esic_next_period_label = f"({next_start.strftime('%b %Y')} – {next_end.strftime('%b %Y')})"

        esic_ceiling = period_service.get_parameter('hds_in_esic_pwd_wage_ceiling', date=next_start) if getattr(employee, 'hds_in_is_pwd', False) else period_service.get_parameter('hds_in_esic_wage_ceiling', date=next_start)
        esic_next_period_status = bool(company.hds_in_esic_applicable and employee.hds_in_esic_applicable and (revised_wage <= esic_ceiling if esic_ceiling else True))

        if not esic_next_period_status and company.hds_in_esic_applicable and employee.hds_in_esic_applicable:
            esic_next_period_reason = f"Employee's wage at the start of the next contribution period ({next_start.strftime('%d-%b-%Y')}) exceeds the ESIC wage ceiling (₹{esic_ceiling:,.0f})."
        else:
            esic_next_period_reason = ""

        return {
            'old_wage': current_wage,
            'new_wage': revised_wage,
            'wage_difference': revised_wage - current_wage,
            'old_ctc': old_ctc,
            'new_ctc': new_ctc,
            'ctc_difference': new_ctc - old_ctc,
            'old_epf_wage': old_epf_wage,
            'new_epf_wage': new_epf_wage,
            'old_ee_epf': old_ee_epf,
            'new_ee_epf': new_ee_epf,
            'old_er_pf': old_er_pf,
            'new_er_pf': new_er_pf,
            'old_eps': old_eps,
            'new_eps': new_eps,
            'old_edli': old_edli,
            'new_edli': new_edli,
            'old_esic_app': old_esic_app,
            'new_esic_app': new_esic_app,
            'old_ee_esic': old_ee_esic,
            'new_ee_esic': new_ee_esic,
            'old_er_esic': old_er_esic,
            'new_er_esic': new_er_esic,
            'esic_cur_period_label': esic_cur_period_label,
            'esic_cur_period_status': esic_cur_period_status,
            'esic_next_period_label': esic_next_period_label,
            'esic_next_period_status': esic_next_period_status,
            'esic_next_period_reason': esic_next_period_reason,
            'pt_amount': pt_amount,
            'lwf_amount': lwf_amount,
        }

    def _build_simulation_context(self, employee, wage, mode='auto_structure', manual_dict=None):
        """
        Builds a simulated evaluation context dictionary (localdict) for a given wage
        by delegating component breakdown calculation to SalaryBreakdownService.
        """
        contracts = self.env['hr.version'].search([('employee_id', '=', employee.id)])
        contract = contracts.sorted(lambda c: c.date_start or fields.Date.today(), reverse=True)[0] if contracts else False

        from ..payroll.salary_breakdown_service import SalaryBreakdownService
        breakdown_service = SalaryBreakdownService(self.env)
        breakdown = breakdown_service.process_breakdown(contract, wage, mode=mode, manual_dict=manual_dict)

        return {
            'GROSS': wage,
            'BASIC': breakdown['basic_salary'],
            'HRA': breakdown['hra'],
            'DA': breakdown['da'],
            'TRAVEL': breakdown['travel_allowance'],
            'MEAL': breakdown['meal_allowance'],
            'MEDICAL': breakdown['medical_allowance'],
            'OTHER': breakdown['other_allowance'],
            'FIXED': breakdown['fixed_allowance'],
            'wage': wage,
        }
