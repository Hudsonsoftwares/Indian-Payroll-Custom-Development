# -*- coding: utf-8 -*-
from datetime import date
from odoo.tests import common, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestPfReports(common.TransactionCase):

    def setUp(self):
        super(TestPfReports, self).setUp()
        self.Employee = self.env['hr.employee']
        self.Contract = self.env['hr.version']
        self.Payslip = self.env['hr.payslip']
        self.EcrWizard = self.env['hds.pf.ecr.wizard']
        self.RegisterWizard = self.env['hds.pf.register.wizard']

        # Setup employee with UAN
        self.emp_valid = self.Employee.create({
            'name': 'Valid UAN Employee',
            'identification_id': 'EMP2001',
            'hds_in_uan': '100000000002',
            'hds_in_pf_member_id': 'MH/BAN/0012345/000/0000202',
            'hds_in_epf_applicable': True,
            'hds_in_eps_applicable': True,
            'hds_in_pf_contribution_basis': 'statutory_ceiling',
        })

        self.contract_valid = self.Contract.create({
            'name': 'Valid Contract',
            'employee_id': self.emp_valid.id,
            'wage': 50000.0,
            'basic_salary': 30000.0,
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })

        # Setup employee WITHOUT UAN
        self.emp_no_uan = self.Employee.create({
            'name': 'Missing UAN Employee',
            'identification_id': 'EMP2002',
            'hds_in_uan': False,
            'hds_in_epf_applicable': True,
            'hds_in_eps_applicable': True,
        })

        self.contract_no_uan = self.Contract.create({
            'name': 'No UAN Contract',
            'employee_id': self.emp_no_uan.id,
            'wage': 20000.0,
            'basic_salary': 15000.0,
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })

    def _create_and_confirm_payslip(self, employee, contract, date_from, date_to):
        payslip = self.Payslip.create({
            'name': f'Payslip for {employee.name}',
            'employee_id': employee.id,
            'contract_id': contract.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        payslip.action_compute_sheet()
        payslip.action_payslip_done()
        return payslip

    def test_01_ecr_validation_missing_uan(self):
        """Test ECR export fails when an EPF-applicable employee lacks UAN."""
        self._create_and_confirm_payslip(self.emp_no_uan, self.contract_no_uan, date(2026, 7, 1), date(2026, 7, 31))

        wizard = self.EcrWizard.create({
            'year': 2026,
            'month': '7',
            'company_id': self.env.company.id,
        })

        with self.assertRaises(UserError) as ctx:
            wizard.action_generate_ecr()

        self.assertIn("missing a UAN", str(ctx.exception))
        self.assertIn("Missing UAN Employee", str(ctx.exception))

    def test_02_ecr_export_success(self):
        """Test successful ECR text and excel generation for valid employee."""
        self._create_and_confirm_payslip(self.emp_valid, self.contract_valid, date(2026, 7, 1), date(2026, 7, 31))

        wizard = self.EcrWizard.create({
            'year': 2026,
            'month': '7',
            'company_id': self.env.company.id,
        })

        action = wizard.action_generate_ecr()

        self.assertEqual(wizard.state, 'generated')
        self.assertTrue(wizard.txt_file)
        self.assertTrue(wizard.xlsx_file)

        # Verify text file format contains pipe delimiter #~#
        import base64
        txt_content = base64.b64decode(wizard.txt_file).decode('utf-8')
        self.assertIn('100000000002#~#Valid UAN Employee', txt_content)

    def test_03_pf_register_export_company_summary(self):
        """Test Case 1: Company PF Register generation when Employee is NOT selected."""
        self._create_and_confirm_payslip(self.emp_valid, self.contract_valid, date(2026, 7, 1), date(2026, 7, 31))

        wizard = self.RegisterWizard.create({
            'year': 2026,
            'month': '7',
            'company_id': self.env.company.id,
            'employee_id': False,
        })

        wizard.action_export_xlsx()

        self.assertEqual(wizard.state, 'generated')
        self.assertTrue(wizard.xlsx_file)
        self.assertIn("PF Register /", wizard.name)
        self.assertGreater(wizard.total_pf_wages, 0.0)
        self.assertGreater(wizard.total_employee_epf, 0.0)

    def test_04_pf_register_export_employee_statement(self):
        """Test Case 2: Employee PF Statement generation when Employee IS selected."""
        self._create_and_confirm_payslip(self.emp_valid, self.contract_valid, date(2026, 7, 1), date(2026, 7, 31))

        wizard = self.RegisterWizard.create({
            'year': 2026,
            'month': '7',
            'company_id': self.env.company.id,
            'employee_id': self.emp_valid.id,
        })

        wizard.action_export_xlsx()

        self.assertEqual(wizard.state, 'generated')
        self.assertTrue(wizard.xlsx_file)
        self.assertIn("Employee PF Statement /", wizard.name)
        self.assertEqual(wizard.emp_summary_name, 'Valid UAN Employee')
        self.assertEqual(wizard.emp_summary_code, 'EMP2001')
        self.assertEqual(wizard.emp_summary_uan, '100000000002')
        self.assertGreater(wizard.emp_summary_pf_wage, 0.0)
        self.assertGreater(wizard.emp_summary_ee_epf, 0.0)
