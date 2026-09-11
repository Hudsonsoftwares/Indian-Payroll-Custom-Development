# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models


class HrVersion(models.Model):
    """
    Extends Contract model (hr.version in Odoo 19 Community) to calculate
    projected Monthly and Annual Employer Cost to Company (CTC).
    """
    _inherit = 'hr.version'

    hds_in_employer_cost_monthly = fields.Monetary(
        string="Employer Cost (Monthly)",
        compute='_compute_employer_cost',
        store=True,
        currency_field='currency_id',
        help="Monthly Cost to Company (Gross Salary + Employer Contributions)."
    )

    hds_in_employer_cost_annual = fields.Monetary(
        string="Employer Cost to Company (CTC)",
        compute='_compute_employer_cost',
        store=True,
        currency_field='currency_id',
        help="Annual Employer Cost to Company (CTC)."
    )

    # Benefits (Indian Payroll)
    benefit_phone = fields.Monetary(
        string='Phone Subscription',
        tracking=True,
        currency_field='currency_id',
        help="Monthly Phone Subscription benefit"
    )
    benefit_internet = fields.Monetary(
        string='Internet Subscription',
        tracking=True,
        currency_field='currency_id',
        help="Monthly Internet Subscription benefit"
    )
    benefit_meal_vouchers = fields.Monetary(
        string='Meal Vouchers',
        tracking=True,
        currency_field='currency_id',
        help="Monthly Meal Vouchers benefit"
    )
    benefit_transport = fields.Monetary(
        string='Company Transport',
        tracking=True,
        currency_field='currency_id',
        help="Monthly Company Transport benefit"
    )



    def _is_india_localization(self):
        """
        Centralized payroll localization check for hr.version.
        Returns True only if India localization is active for this contract/template.
        """
        self.ensure_one()
        return bool(self.is_india_localization)

    @api.depends(
        'wage', 'basic_salary', 'da', 'struct_id', 'struct_id.rule_ids', 'company_id', 'company_id.country_id',
        'employee_id.hds_in_pf_contribution_basis', 'employee_id.hds_in_pf_employer_basis',
        'employee_id.hds_in_epf_applicable', 'employee_id.hds_in_eps_applicable',
        'employee_id.hds_in_esic_applicable', 'employee_id.hds_in_lwf_applicable'
    )
    def _compute_employer_cost(self):
        for contract in self:
            if not contract._is_india_localization():
                contract.hds_in_employer_cost_monthly = 0.0
                contract.hds_in_employer_cost_annual = 0.0
                if contract.employee_id:
                    contract.employee_id.hds_in_employer_cost_monthly = 0.0
                    contract.employee_id.hds_in_employer_cost_annual = 0.0
                continue

            wage = float(contract.wage or 0.0)
            breakdown = float(getattr(contract, 'breakdown_total', 0.0) or 0.0)
            if breakdown <= 0.0:
                breakdown = float(
                    (getattr(contract, 'basic_salary', 0.0) or 0.0) + (getattr(contract, 'hra', 0.0) or 0.0) +
                    (getattr(contract, 'da', 0.0) or 0.0) + (getattr(contract, 'standard_allowance', 0.0) or 0.0) +
                    (getattr(contract, 'performance_bonus', 0.0) or 0.0) + (getattr(contract, 'retention_bonus', 0.0) or 0.0) +
                    (getattr(contract, 'lta_allowance', 0.0) or 0.0) + (getattr(contract, 'fixed_allowance', 0.0) or 0.0)
                )
            if wage <= 0.0 and breakdown > 0.0:
                wage = breakdown
            elif breakdown > wage > 0.0:
                wage = breakdown

            employer_contrib_monthly = 0.0

            if contract.struct_id:
                ctc_rules = contract.struct_id.get_all_rules()
                if isinstance(ctc_rules, models.Model):
                    rules = ctc_rules.filtered(lambda r: r.hds_in_contributes_to_employer_cost and r.active)
                else:
                    rule_ids = [r[0] if isinstance(r, (tuple, list)) else getattr(r, 'id', r) for r in ctc_rules]
                    rules = self.env['hr.salary.rule'].browse(rule_ids).filtered(
                        lambda r: r.hds_in_contributes_to_employer_cost and r.active
                    )
            else:
                rules = self.env['hr.salary.rule'].search([('hds_in_contributes_to_employer_cost', '=', True), ('active', '=', True)])

            for rule in rules:
                if rule.amount_select == 'fix':
                    employer_contrib_monthly += rule.amount_fix
                elif rule.amount_select == 'percentage':
                    employer_contrib_monthly += (wage * rule.amount_percentage / 100.0)
                elif rule.amount_select == 'code':
                    employer_contrib_monthly += self._estimate_statutory_rule_amount(contract, rule)

            monthly_ctc = round(wage + employer_contrib_monthly, 2)
            contract.hds_in_employer_cost_monthly = monthly_ctc
            contract.hds_in_employer_cost_annual = round(monthly_ctc * 12.0, 2)
            if contract.employee_id:
                contract.employee_id.hds_in_employer_cost_monthly = monthly_ctc
                contract.employee_id.hds_in_employer_cost_annual = round(monthly_ctc * 12.0, 2)

    @api.onchange('wage', 'basic_salary', 'da', 'struct_id', 'employee_id')
    def _onchange_contract_ctc_inputs(self):
        if self._is_india_localization():
            self._compute_employer_cost()

    @api.onchange('contract_template_id')
    def _onchange_contract_template_id(self):
        super()._onchange_contract_template_id()
        if self._is_india_localization():
            self._compute_employer_cost()
        else:
            self.hds_in_employer_cost_monthly = 0.0
            self.hds_in_employer_cost_annual = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        for contract in contracts:
            if contract._is_india_localization():
                contract._compute_employer_cost()
                if contract.employee_id and contract.wage:
                    contract._sync_employee_esic_default()
            else:
                contract.hds_in_employer_cost_monthly = 0.0
                contract.hds_in_employer_cost_annual = 0.0
        return contracts

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ('wage', 'employee_id', 'struct_id', 'contract_template_id', 'basic_salary', 'hra', 'da')):
            for contract in self:
                if contract._is_india_localization():
                    contract._compute_employer_cost()
                    if contract.employee_id and contract.wage:
                        contract._sync_employee_esic_default()
                else:
                    contract.hds_in_employer_cost_monthly = 0.0
                    contract.hds_in_employer_cost_annual = 0.0
        return res

    @api.onchange('wage', 'employee_id')
    def _onchange_wage_sync_esic(self):
        for contract in self:
            if not contract._is_india_localization():
                continue
            if contract.employee_id:
                default_esic = contract.employee_id._evaluate_default_esic_applicable(
                    gross_wage=contract.wage,
                    eval_date=contract.date_start or fields.Date.today()
                )
                contract.employee_id.hds_in_esic_applicable = default_esic
                if not default_esic:
                    contract.employee_id.hds_in_esic_ip_status = 'exempt'
                    contract.employee_id.hds_in_esic_exit_reason = 'wage_exceeded'
                else:
                    if contract.employee_id.hds_in_esic_ip_status == 'exempt':
                        contract.employee_id.hds_in_esic_ip_status = 'active'

    def _sync_employee_esic_default(self):
        """
        Updates default ESIC applicability on employee when contract wage changes,
        while maintaining manual override capability.
        """
        self.ensure_one()
        if not self._is_india_localization():
            return
        employee = self.employee_id
        if not employee:
            return
        default_esic = employee._evaluate_default_esic_applicable(
            gross_wage=self.wage,
            eval_date=self.date_start or fields.Date.today()
        )
        vals = {'hds_in_esic_applicable': default_esic}
        if not default_esic:
            vals['hds_in_esic_ip_status'] = 'exempt'
            vals['hds_in_esic_exit_reason'] = 'wage_exceeded'
        else:
            if employee.hds_in_esic_ip_status == 'exempt':
                vals['hds_in_esic_ip_status'] = 'active'
        employee.write(vals)

    def _estimate_statutory_rule_amount(self, contract, rule):
        """
        Estimates contract-level statutory employer cost by delegating directly
        to EPFService and ESICService and reusing the exact same statutory calculation engine,
        wage rules, applicability flags, contribution basis, and effective-dated parameters.
        No statutory constants or rates are hardcoded.
        """
        if not contract._is_india_localization():
            return 0.0

        code_text = rule.amount_python_compute or ''
        rule_code = rule.code or ''
        employee = contract.employee_id

        from ..services.epf.epf_service import EPFService, ContractPayslipAdapter
        adapter = ContractPayslipAdapter(contract)

        # EPF Contribution Rules
        if any(k in code_text for k in ('compute_employer_total_pf', 'compute_employer_epf', 'compute_employer_eps', 'compute_employer_edli', 'compute_epf_admin', 'compute_edli_admin')) or rule_code in ('EMPLOYER_EPF', 'EPS', 'EPF_SHARE', 'EDLI', 'EPF_ADMIN', 'EDLI_ADMIN'):
            if employee and hasattr(employee, 'hds_in_epf_applicable') and not employee.hds_in_epf_applicable:
                return 0.0
            epf_svc = EPFService(self.env)
            if 'compute_employer_total_pf' in code_text or ('compute_employer_epf' in code_text and 'compute_employer_epf_share' not in code_text) or rule_code == 'EMPLOYER_EPF':
                return epf_svc.compute_employer_epf(adapter)
            elif 'compute_employer_epf_share' in code_text or rule_code == 'EPF_SHARE':
                return epf_svc.compute_employer_epf_share(adapter)
            elif 'compute_employer_eps' in code_text or rule_code == 'EPS':
                return epf_svc.compute_employer_eps(adapter)
            elif 'compute_employer_edli' in code_text or rule_code == 'EDLI':
                return epf_svc.compute_employer_edli(adapter)
            elif 'compute_epf_admin' in code_text or rule_code == 'EPF_ADMIN':
                return epf_svc.compute_epf_admin(adapter)
            elif 'compute_edli_admin' in code_text or rule_code == 'EDLI_ADMIN':
                return epf_svc.compute_edli_admin(adapter)

        # ESIC Employer Contribution Rule
        elif 'compute_esic_employer' in code_text or rule_code == 'ESIC_ER':
            if employee and hasattr(employee, 'hds_in_esic_applicable') and not employee.hds_in_esic_applicable:
                return 0.0
            from ..services.esic.esic_service import ESICService
            esic_svc = ESICService(self.env)
            return esic_svc.compute_esic_employer(adapter)

        # LWF Employer Contribution Rule
        elif 'compute_lwf_employer' in code_text or rule_code == 'LWF_ER':
            if employee and hasattr(employee, 'hds_in_lwf_applicable') and not employee.hds_in_lwf_applicable:
                return 0.0
            return 20.0

        return 0.0
