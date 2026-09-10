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

    # Allowances & Benefits (Indian Payroll)
    lta_allowance = fields.Monetary(
        string='Leave Travel Allowance',
        tracking=True,
        currency_field='currency_id',
        help="Monthly Leave Travel Allowance (LTA)"
    )
    lta_percent = fields.Float(
        string='LTA %',
        compute='_compute_lta_percent',
        store=True,
        digits=(16, 2),
        help="LTA percentage relative to wage"
    )
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

    @api.depends('lta_allowance', 'wage')
    def _compute_lta_percent(self):
        for rec in self:
            if rec.wage and rec.lta_allowance:
                rec.lta_percent = round((rec.lta_allowance / rec.wage) * 100.0, 2)
            else:
                rec.lta_percent = 0.0



    def _is_india_localization(self):
        """
        Centralized payroll localization check for hr.version.
        Returns True only if India localization is active for this contract/template.
        """
        self.ensure_one()
        return bool(self.is_india_localization)

    @api.depends('wage', 'struct_id', 'struct_id.rule_ids', 'company_id', 'company_id.country_id')
    def _compute_employer_cost(self):
        for contract in self:
            if not contract._is_india_localization():
                contract.hds_in_employer_cost_monthly = 0.0
                contract.hds_in_employer_cost_annual = 0.0
                if contract.employee_id:
                    contract.employee_id._compute_hds_in_employer_cost()
                continue

            wage = contract.wage or 0.0
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

            monthly_ctc = wage + employer_contrib_monthly
            contract.hds_in_employer_cost_monthly = monthly_ctc
            contract.hds_in_employer_cost_annual = monthly_ctc * 12.0
            if contract.employee_id:
                contract.employee_id._compute_hds_in_employer_cost()

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
        employee.write({'hds_in_esic_applicable': default_esic})

    def _estimate_statutory_rule_amount(self, contract, rule):
        """
        Estimates contract-level statutory employer cost by delegating directly
        to EPFService and reusing the exact same statutory calculation engine,
        wage rules, applicability flags, contribution basis, and effective-dated parameters.
        No statutory constants or rates are hardcoded.
        """
        if not contract._is_india_localization():
            return 0.0

        code_text = rule.amount_python_compute or ''
        employee = contract.employee_id
        if employee and hasattr(employee, 'hds_in_epf_applicable') and not employee.hds_in_epf_applicable:
            return 0.0

        from ..services.epf.epf_service import EPFService, ContractPayslipAdapter
        adapter = ContractPayslipAdapter(contract)
        epf_svc = EPFService(self.env)

        if 'compute_employer_total_pf' in code_text or ('compute_employer_epf' in code_text and 'compute_employer_epf_share' not in code_text):
            return epf_svc.compute_employer_epf(adapter)
        elif 'compute_employer_epf_share' in code_text:
            return epf_svc.compute_employer_epf_share(adapter)
        elif 'compute_employer_eps' in code_text:
            return epf_svc.compute_employer_eps(adapter)
        elif 'compute_employer_edli' in code_text:
            return epf_svc.compute_employer_edli(adapter)
        elif 'compute_epf_admin' in code_text:
            return epf_svc.compute_epf_admin(adapter)
        elif 'compute_edli_admin' in code_text:
            return epf_svc.compute_edli_admin(adapter)
        return 0.0
