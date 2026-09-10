# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from ..services.revision.salary_revision_service import SalaryRevisionService


class TestSalaryRevisionEngine(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.hds_in_esic_applicable = True
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Revision Employee',
            'hds_in_epf_applicable': True,
            'hds_in_esic_applicable': True,
            'company_id': self.company.id,
        })
        self.contract = self.env['hr.version'].create({
            'name': 'Contract - Test Revision Employee',
            'employee_id': self.employee.id,
            'wage': 20000.0,
            'date_start': '2026-01-01',
        })

    def test_01_salary_preview_simulation(self):
        """Validates simulated before and after breakdown for a +10% gross salary revision."""
        wizard = self.env['hds.in.salary.revision.wizard'].with_context(
            active_id=self.employee.id,
            active_model='hr.employee'
        ).create({
            'effective_date': '2026-04-01',
            'revision_type': 'annual_increment',
            'computation_type': 'percentage',
            'increase_percentage': 10.0,
            'revision_basis': 'full_wage',
        })

        self.assertEqual(wizard.current_wage, 20000.0)
        self.assertEqual(wizard.revised_wage, 22000.0)
        self.assertEqual(wizard.wage_difference, 2000.0)
        self.assertTrue(wizard.preview_old_esic_app)
        # Gross = ₹22,000 (> ₹21,000 ceiling for non-PWD) -> ESIC estimated coverage False
        self.assertFalse(wizard.preview_new_esic_app)

    def test_02_salary_revision_execution(self):
        """Validates end-to-end execution of salary revision via SalaryRevisionService."""
        wizard = self.env['hds.in.salary.revision.wizard'].with_context(
            active_id=self.employee.id,
            active_model='hr.employee'
        ).create({
            'effective_date': '2026-04-01',
            'revision_type': 'annual_increment',
            'computation_type': 'percentage',
            'increase_percentage': 10.0,
            'revision_basis': 'full_wage',
            'reason': 'Annual Increment 2026',
        })

        revision_record = wizard.action_confirm_revision()
        revision = self.env['hds.in.salary.revision'].browse(revision_record['res_id'])

        # 1. Immutable record created
        self.assertEqual(revision.employee_id.id, self.employee.id)
        self.assertEqual(revision.old_wage, 20000.0)
        self.assertEqual(revision.new_wage, 22000.0)
        self.assertEqual(revision.state, 'approved')

        # 2. Active contract updated
        self.assertEqual(self.contract.wage, 22000.0)

        # 3. Employee statutory defaults refreshed (ESIC becomes False as ₹22,000 > ₹21,000 ceiling)
        self.assertFalse(self.employee.hds_in_esic_applicable)

    def test_03_invalid_effective_date(self):
        """Validates that effective date preceding contract start date raises ValidationError."""
        wizard = self.env['hds.in.salary.revision.wizard'].with_context(
            active_id=self.employee.id,
            active_model='hr.employee'
        ).create({
            'effective_date': '2025-12-01', # Precedes contract start '2026-01-01'
            'revision_type': 'correction',
            'computation_type': 'fixed_amount',
            'increase_amount': 1000.0,
            'revision_basis': 'full_wage',
        })

        with self.assertRaises(ValidationError):
            wizard.action_confirm_revision()

    def test_04_epf_actual_basic_parity(self):
        """Validates parity when employee is configured with actual_basic PF contribution basis."""
        self.employee.hds_in_pf_contribution_basis = 'actual_basic'
        wizard = self.env['hds.in.salary.revision.wizard'].with_context(
            active_id=self.employee.id,
            active_model='hr.employee'
        ).create({
            'effective_date': '2026-04-01',
            'revision_type': 'annual_increment',
            'computation_type': 'percentage',
            'increase_percentage': 10.0,
            'revision_basis': 'full_wage',
        })

        # When contribution basis is 'actual_basic', EPF wage is uncapped (₹20,000 / ₹22,000)
        self.assertEqual(wizard.preview_old_epf_wage, 20000.0)
        self.assertEqual(wizard.preview_new_epf_wage, 22000.0)
        self.assertEqual(wizard.preview_old_ee_epf, 2400.0)
        self.assertEqual(wizard.preview_new_ee_epf, 2640.0)

    def test_05_contract_breakdown_regeneration_and_isolation(self):
        """Validates that salary revision regenerates contract breakdown components and preserves multi-employee isolation."""
        # Setup Employee B (Other employee)
        emp_b = self.env['hr.employee'].create({
            'name': 'Other Employee',
            'company_id': self.company.id,
        })
        contract_b = self.env['hr.version'].create({
            'name': 'Contract - Other Employee',
            'employee_id': emp_b.id,
            'wage': 15000.0,
            'basic_salary': 7500.0,
            'hra': 3000.0,
            'fixed_allowance': 4500.0,
            'date_start': '2026-01-01',
        })

        # Set initial breakdown on Employee A
        self.contract.write({
            'wage': 20000.0,
            'basic_salary': 10000.0,
            'hra': 4000.0,
            'fixed_allowance': 6000.0,
        })

        # Revise Employee A from ₹20,000 to ₹25,000
        wizard = self.env['hds.in.salary.revision.wizard'].with_context(
            active_id=self.employee.id,
            active_model='hr.employee'
        ).create({
            'effective_date': '2026-04-01',
            'revision_type': 'annual_increment',
            'computation_type': 'fixed_amount',
            'increase_amount': 5000.0,
            'revision_basis': 'full_wage',
        })

        wizard.action_confirm_revision()

        # 1. Employee A's contract breakdown is regenerated and balanced
        self.assertEqual(self.contract.wage, 25000.0)
        self.assertEqual(self.contract.basic_salary, 12500.0)
        self.assertEqual(self.contract.hra, 5000.0)
        self.assertEqual(self.contract.fixed_allowance, 7500.0)
        self.assertTrue(self.contract.breakdown_is_equal)

        # 2. Employee B's contract remains completely unchanged (Strict Isolation)
        self.assertEqual(contract_b.wage, 15000.0)
        self.assertEqual(contract_b.basic_salary, 7500.0)
        self.assertEqual(contract_b.hra, 3000.0)
        self.assertEqual(contract_b.fixed_allowance, 4500.0)

    def test_06_keep_existing_breakdown_mode(self):
        """Validates that 'keep_existing' mode updates gross wage but leaves component breakdown untouched."""
        self.contract.write({
            'wage': 20000.0,
            'basic_salary': 15000.0,
            'hra': 3000.0,
            'fixed_allowance': 2000.0,
        })

        wizard = self.env['hds.in.salary.revision.wizard'].with_context(
            active_id=self.employee.id,
            active_model='hr.employee'
        ).create({
            'effective_date': '2026-04-01',
            'revision_type': 'annual_increment',
            'computation_type': 'fixed_amount',
            'increase_amount': 5000.0,
            'revision_basis': 'full_wage',
            'breakdown_distribution_mode': 'keep_existing',
        })

        wizard.action_confirm_revision()

        # Contract wage is updated to ₹25,000, but stored components remain untouched
        self.assertEqual(self.contract.wage, 25000.0)
        self.assertEqual(self.contract.basic_salary, 15000.0)
        self.assertEqual(self.contract.hra, 3000.0)
        self.assertEqual(self.contract.fixed_allowance, 2000.0)

    def test_07_manual_adjust_breakdown_mode(self):
        """Validates manual breakdown allocation mode and strict sum validation."""
        self.contract.write({'wage': 20000.0})

        # 1. Invalid manual sum raises ValidationError
        wizard_invalid = self.env['hds.in.salary.revision.wizard'].with_context(
            active_id=self.employee.id,
            active_model='hr.employee'
        ).create({
            'effective_date': '2026-04-01',
            'revision_type': 'annual_increment',
            'computation_type': 'fixed_amount',
            'increase_amount': 5000.0, # Revised wage = 25,000
            'revision_basis': 'full_wage',
            'breakdown_distribution_mode': 'manual_adjust',
            'manual_basic_salary': 15000.0,
            'manual_hra': 5000.0,
            'manual_fixed_allowance': 4000.0, # Total = 24,000 != 25,000
        })

        with self.assertRaises(ValidationError):
            wizard_invalid.action_confirm_revision()

        # 2. Valid manual sum executes and updates contract components
        wizard_valid = self.env['hds.in.salary.revision.wizard'].with_context(
            active_id=self.employee.id,
            active_model='hr.employee'
        ).create({
            'effective_date': '2026-04-01',
            'revision_type': 'annual_increment',
            'computation_type': 'fixed_amount',
            'increase_amount': 5000.0, # Revised wage = 25,000
            'revision_basis': 'full_wage',
            'breakdown_distribution_mode': 'manual_adjust',
            'manual_basic_salary': 15000.0,
            'manual_hra': 5000.0,
            'manual_fixed_allowance': 5000.0, # Total = 25,000 == 25,000
        })

        wizard_valid.action_confirm_revision()

        self.assertEqual(self.contract.wage, 25000.0)
        self.assertEqual(self.contract.basic_salary, 15000.0)
        self.assertEqual(self.contract.hra, 5000.0)
        self.assertEqual(self.contract.fixed_allowance, 5000.0)
        self.assertTrue(self.contract.breakdown_is_equal)

    def test_08_copy_current_and_auto_balance(self):
        """Validates 'copy_current' mode pre-filling and action_auto_balance_remaining functionality."""
        self.contract.write({
            'wage': 20000.0,
            'basic_salary': 10000.0,
            'hra': 4000.0,
            'fixed_allowance': 6000.0,
        })

        wizard = self.env['hds.in.salary.revision.wizard'].with_context(
            active_id=self.employee.id,
            active_model='hr.employee'
        ).create({
            'effective_date': '2026-04-01',
            'revision_type': 'annual_increment',
            'computation_type': 'fixed_amount',
            'increase_amount': 5000.0, # Revised wage = 25,000
            'revision_basis': 'full_wage',
            'breakdown_distribution_mode': 'copy_current',
        })

        # Trigger onchange to pre-fill current components
        wizard._onchange_breakdown_distribution_mode()

        self.assertEqual(wizard.manual_basic_salary, 10000.0)
        self.assertEqual(wizard.manual_hra, 4000.0)
        self.assertEqual(wizard.manual_fixed_allowance, 6000.0)
        self.assertEqual(wizard.manual_breakdown_remaining, 5000.0)
        self.assertFalse(wizard.manual_breakdown_is_equal)

        # Click Auto Balance Remaining button
        wizard.action_auto_balance_remaining()

        # Fixed Allowance becomes 6,000 + 5,000 = 11,000 to balance revised wage of 25,000
        self.assertEqual(wizard.manual_fixed_allowance, 11000.0)
        self.assertEqual(wizard.manual_breakdown_remaining, 0.0)
        self.assertTrue(wizard.manual_breakdown_is_equal)

        wizard.action_confirm_revision()

        self.assertEqual(self.contract.wage, 25000.0)
        self.assertEqual(self.contract.basic_salary, 10000.0)
        self.assertEqual(self.contract.hra, 4000.0)
        self.assertEqual(self.contract.fixed_allowance, 11000.0)
