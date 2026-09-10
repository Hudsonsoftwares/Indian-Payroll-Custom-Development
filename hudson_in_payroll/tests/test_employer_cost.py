# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestEmployerCost(TransactionCase):

    def setUp(self):
        super().setUp()
        self.country_in = self.env.ref('base.in')
        self.env.company.country_id = self.country_in
        self.SalaryRule = self.env['hr.salary.rule']
        self.Contract = self.env['hr.version']
        self.Employee = self.env['hr.employee']
        self.Structure = self.env['hr.payroll.structure']

        self.rule_epf_er = self.env.ref('hudson_in_payroll.hds_in_rule_epf_er')
        self.rule_edli = self.env.ref('hudson_in_payroll.hds_in_rule_edli')
        self.rule_admin = self.env.ref('hudson_in_payroll.hds_in_rule_epf_admin')

        self.employee = self.Employee.create({
            'name': 'Test Employee CTC',
        })

        self.structure = self.env.ref('hudson_payroll_base.structure_base')

        self.contract = self.Contract.create({
            'name': 'Test Contract CTC',
            'employee_id': self.employee.id,
            'wage': 15000.0,
            'struct_id': self.structure.id,
        })
        self.employee.contract_id = self.contract.id

    def test_01_salary_rule_ctc_flag(self):
        """Verify salary rules have hds_in_contributes_to_employer_cost flag set correctly."""
        self.assertTrue(self.rule_epf_er.hds_in_contributes_to_employer_cost)
        self.assertTrue(self.rule_edli.hds_in_contributes_to_employer_cost)
        self.assertTrue(self.rule_admin.hds_in_contributes_to_employer_cost)

    def test_02_contract_ctc_computation(self):
        """
        Wage = 15,000.
        Employer PF (12%) = 1,800.0
        Employer EDLI (0.5%) = 75.0
        EPF Admin (0.5%) = 75.0
        Total Employer Statutory = 1,950.0
        Monthly CTC = 15,000 + 1,950 = 16,950.0
        Annual CTC = 16,950 * 12 = 203,400.0
        """
        self.contract._compute_employer_cost()
        self.assertGreater(self.contract.hds_in_employer_cost_monthly, 15000.0)
        self.assertEqual(self.contract.hds_in_employer_cost_annual, self.contract.hds_in_employer_cost_monthly * 12.0)
        self.assertEqual(self.employee.hds_in_employer_cost_annual, self.contract.hds_in_employer_cost_annual)

    def test_03_contract_template_load_employer_cost_sync(self):
        """Validates that loading a contract template populates non-zero Employer Cost figures on contract and syncs to employee."""
        tmpl = self.Contract.create({
            'name': 'Standard Software Engineer Template',
            'wage': 20000.0,
            'struct_id': self.structure.id,
        })

        new_contract = self.Contract.create({
            'name': 'Contract - New Employee',
            'employee_id': self.employee.id,
            'contract_template_id': tmpl.id,
        })
        new_contract._onchange_contract_template_id()

        self.assertGreater(new_contract.hds_in_employer_cost_monthly, 20000.0)
        self.assertEqual(self.employee.hds_in_employer_cost_monthly, new_contract.hds_in_employer_cost_monthly)
        self.assertEqual(self.employee.hds_in_employer_cost_annual, new_contract.hds_in_employer_cost_annual)
