# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from odoo.exceptions import UserError
from odoo import fields


@tagged('post_install', '-at_install')
class TestBonusManagement(common.TransactionCase):

    def setUp(self):
        super(TestBonusManagement, self).setUp()
        self.company = self.env.company

        # Create test employee
        self.employee = self.env['hr.employee'].create({
            'name': 'Bonus Test Employee',
            'company_id': self.company.id,
        })

        # Create test contract
        self.contract = self.env['hr.version'].create({
            'name': 'Bonus Test Contract',
            'employee_id': self.employee.id,
            'wage': 50000.0,
            'basic_salary': 25000.0,
            'state': 'open',
            'company_id': self.company.id,
            'date_start': fields.Date.today().replace(day=1),
        })

    def test_01_bonus_creation_and_fixed_generation(self):
        """Test creating bonus document and generating fixed bonus lines."""
        bonus = self.env['hds.in.bonus'].create({
            'name': 'Diwali Bonus 2026',
            'bonus_type': 'festival',
            'payment_method': 'monthly_payroll',
            'employee_selection_type': 'employee',
            'employee_id': self.employee.id,
            'calculation_method': 'fixed',
            'fixed_amount': 10000.0,
        })
        self.assertEqual(bonus.state, 'draft')

        # Generate lines
        bonus.action_generate_lines()
        self.assertEqual(len(bonus.line_ids), 1)

        line = bonus.line_ids[0]
        self.assertEqual(line.employee_id, self.employee)
        self.assertEqual(line.amount, 10000.0)

        # Modify amount manually
        line.write({'amount': 12000.0})
        self.assertEqual(line.amount, 12000.0)

    def test_02_bonus_percentage_calculation_methods(self):
        """Test Percentage of Basic and Percentage of Gross bonus calculations."""
        # Percentage of Basic (10% of 25,000 = 2,500)
        bonus_basic = self.env['hds.in.bonus'].create({
            'name': 'Performance Bonus Basic',
            'bonus_type': 'performance',
            'employee_selection_type': 'employee',
            'employee_id': self.employee.id,
            'calculation_method': 'percentage_basic',
            'percentage': 10.0,
        })
        bonus_basic.action_generate_lines()
        self.assertEqual(bonus_basic.line_ids[0].amount, 2500.0)

        # Percentage of Gross (10% of 50,000 = 5,000)
        bonus_gross = self.env['hds.in.bonus'].create({
            'name': 'Performance Bonus Gross',
            'bonus_type': 'performance',
            'employee_selection_type': 'employee',
            'employee_id': self.employee.id,
            'calculation_method': 'percentage_gross',
            'percentage': 10.0,
        })
        bonus_gross.action_generate_lines()
        self.assertEqual(bonus_gross.line_ids[0].amount, 5000.0)

    def test_03_bonus_workflow_transitions(self):
        """Test status state transitions: Draft -> Submitted -> Approved -> Processed."""
        bonus = self.env['hds.in.bonus'].create({
            'name': 'Annual Bonus 2026',
            'bonus_type': 'annual',
            'employee_selection_type': 'employee',
            'employee_id': self.employee.id,
            'calculation_method': 'fixed',
            'fixed_amount': 15000.0,
        })
        bonus.action_submit()
        self.assertEqual(bonus.state, 'submitted')

        bonus.action_approve()
        self.assertEqual(bonus.state, 'approved')

        # Cannot process without approval
        bonus.write({'state': 'submitted'})
        with self.assertRaises(UserError):
            bonus.action_process_bonus()

    def test_04_monthly_payroll_processing(self):
        """Test Option 1: Include in Monthly Payroll generates input and hooks get_inputs."""
        bonus = self.env['hds.in.bonus'].create({
            'name': 'Festival Bonus Monthly',
            'bonus_type': 'festival',
            'payment_method': 'monthly_payroll',
            'employee_selection_type': 'employee',
            'employee_id': self.employee.id,
            'calculation_method': 'fixed',
            'fixed_amount': 8000.0,
            'payment_date': fields.Date.today(),
            'date_from': fields.Date.today().replace(day=1),
            'date_to': fields.Date.today(),
        })
        bonus.action_submit()
        bonus.action_approve()
        bonus.action_process_bonus()

        self.assertEqual(bonus.state, 'processed')

        # Verify get_inputs on HrPayslip
        inputs = self.env['hr.payslip'].get_inputs(self.contract, bonus.date_from, bonus.date_to)
        bonus_input = [i for i in inputs if i.get('code') == 'BONUS']
        self.assertTrue(len(bonus_input) > 0)
        self.assertEqual(bonus_input[0]['amount'], 8000.0)

    def test_05_separate_payroll_processing(self):
        """Test Option 2: Separate Bonus Payroll creates Payslip Batch and linked Payslips."""
        bonus = self.env['hds.in.bonus'].create({
            'name': 'Separate Bonus 2026',
            'bonus_type': 'annual',
            'payment_method': 'separate_payroll',
            'employee_selection_type': 'employee',
            'employee_id': self.employee.id,
            'calculation_method': 'fixed',
            'fixed_amount': 20000.0,
            'date_from': fields.Date.today().replace(day=1),
            'date_to': fields.Date.today(),
        })
        bonus.action_submit()
        bonus.action_approve()
        bonus.action_process_bonus()

        self.assertEqual(bonus.state, 'processed')
        self.assertTrue(bonus.payslip_run_id)
        self.assertEqual(len(bonus.payslip_run_id.slip_ids), 1)

        payslip = bonus.payslip_run_id.slip_ids[0]
        self.assertEqual(payslip.employee_id, self.employee)
        self.assertEqual(bonus.line_ids[0].payslip_id, payslip)
        self.assertEqual(bonus.payslip_count, 1)

    def test_06_bonus_deduction_configuration(self):
        """Test company level bonus deduction flags."""
        self.company.write({
            'hds_in_bonus_apply_tds': True,
            'hds_in_bonus_apply_pf': False,
            'hds_in_bonus_apply_esi': False,
            'hds_in_bonus_apply_pt': False,
        })
        self.assertTrue(self.company.hds_in_bonus_apply_tds)
        self.assertFalse(self.company.hds_in_bonus_apply_pf)

        config = self.env['res.config.settings'].create({
            'hds_in_bonus_apply_pf': True,
        })
        config.execute()
        self.assertTrue(self.company.hds_in_bonus_apply_pf)
