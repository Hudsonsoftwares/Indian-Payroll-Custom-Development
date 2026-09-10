# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from ..services.esic.esic_service import ESICService


class TestESICService(TransactionCase):

    def setUp(self):
        super().setUp()
        self.employee = self.env['hr.employee'].create({
            'name': 'Test ESIC Employee',
            'hds_in_esic_applicable': True,
            'hds_in_is_pwd': False,
        })
        self.company = self.env.company
        self.company.hds_in_esic_applicable = True
        self.payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': '2026-04-01',
            'date_to': '2026-04-30',
        })

    def test_01_esic_calculation(self):
        """
        Gross Wage = ₹20,000 (<= ₹21,000 standard ceiling).
        ESIC EE Rate = 0.75% -> 20000 * 0.0075 = 150.0.
        ESIC ER Rate = 3.25% -> 20000 * 0.0325 = 650.0.
        """
        localdict = {'BASIC': 15000.0, 'HRA': 5000.0}
        service = ESICService(self.env, localdict=localdict)

        wage = service.compute_esic_wage(self.payslip)
        self.assertEqual(wage, 20000.0)

        ee_deduction = service.compute_esic_employee(self.payslip)
        self.assertEqual(ee_deduction, 150.0)

        er_contribution = service.compute_esic_employer(self.payslip)
        self.assertEqual(er_contribution, 650.0)

    def test_02_standard_ceiling_exceeded(self):
        """
        Gross Wage = ₹23,000 (> ₹21,000 standard ceiling).
        Non-PWD employee is not eligible. Returns 0.0.
        """
        localdict = {'BASIC': 18000.0, 'HRA': 5000.0}
        service = ESICService(self.env, localdict=localdict)

        wage = service.compute_esic_wage(self.payslip)
        self.assertEqual(wage, 0.0)

        ee_deduction = service.compute_esic_employee(self.payslip)
        self.assertEqual(ee_deduction, 0.0)

    def test_03_pwd_ceiling_eligible(self):
        """
        Gross Wage = ₹23,000 (> ₹21,000 standard ceiling, but <= ₹25,000 PWD ceiling).
        PWD employee (hds_in_is_pwd = True) is eligible under PWD ceiling parameter.
        EE = 23000 * 0.0075 = 172.5 -> ceil = 173.0.
        ER = 23000 * 0.0325 = 747.5 -> ceil = 748.0.
        """
        self.employee.hds_in_is_pwd = True
        localdict = {'BASIC': 18000.0, 'HRA': 5000.0}
        service = ESICService(self.env, localdict=localdict)

        wage = service.compute_esic_wage(self.payslip)
        self.assertEqual(wage, 23000.0)

        ee_deduction = service.compute_esic_employee(self.payslip)
        self.assertEqual(ee_deduction, 173.0)

        er_contribution = service.compute_esic_employer(self.payslip)
        self.assertEqual(er_contribution, 748.0)

    def test_04_esic_not_applicable(self):
        """When ESIC is disabled on employee or company, calculations return 0.0."""
        self.employee.hds_in_esic_applicable = False
        localdict = {'BASIC': 20000.0}
        service = ESICService(self.env, localdict=localdict)

        self.assertEqual(service.compute_esic_wage(self.payslip), 0.0)
        self.assertEqual(service.compute_esic_employee(self.payslip), 0.0)
        self.assertEqual(service.compute_esic_employer(self.payslip), 0.0)

    def test_scenario_1_constant_wage_below_ceiling(self):
        """
        Scenario 1: Employee wage = ₹20,000 from April through July.
        ESIC should continue every month.
        """
        contract = self.env['hr.version'].create({
            'name': 'April Contract',
            'employee_id': self.employee.id,
            'wage': 20000.0,
            'date_start': '2026-04-01',
            'date_version': '2026-04-01',
        })

        for month in ['2026-04-30', '2026-05-31', '2026-06-30', '2026-07-31']:
            payslip = self.env['hr.payslip'].create({
                'employee_id': self.employee.id,
                'date_from': month[:8] + '01',
                'date_to': month,
            })
            service = ESICService(self.env, localdict={'BASIC': 15000.0, 'HRA': 5000.0})
            wage = service.compute_esic_wage(payslip)
            self.assertEqual(wage, 20000.0)
            self.assertGreater(service.compute_esic_employee(payslip), 0.0)

    def test_scenario_2_mid_period_revision_continuity(self):
        """
        Scenario 2:
        April 1 Wage = ₹20,000 -> ESIC Applicable.
        July 1 Revision -> Wage = ₹26,250 (> ₹21,000 ceiling).
        Expected:
        - April to September payslips: ESIC MUST CONTINUE (Regulation 31 continuity).
        - October payslip (New Contribution Period start Oct 1): ESIC stops because wage > ceiling on Oct 1.
        """
        apr_contract = self.env['hr.version'].create({
            'name': 'April Initial Contract',
            'employee_id': self.employee.id,
            'wage': 20000.0,
            'date_start': '2026-04-01',
            'date_version': '2026-04-01',
        })

        # Re-evaluate applicability on April 1
        self.employee.write({'hds_in_esic_applicable': True})

        # July Salary Revision -> Wage = 26,250
        jul_contract = self.env['hr.version'].create({
            'name': 'July Revised Contract',
            'employee_id': self.employee.id,
            'wage': 26250.0,
            'date_start': '2026-07-01',
            'date_version': '2026-07-01',
        })

        self.env['hds.in.salary.revision'].create({
            'employee_id': self.employee.id,
            'contract_id': jul_contract.id,
            'effective_date': '2026-07-01',
            'old_wage': 20000.0,
            'new_wage': 26250.0,
            'revision_type': 'annual_increment',
            'revision_basis': 'full_wage',
            'computation_type': 'fixed_amount',
            'state': 'approved',
        })

        # July Payslip (Mid-period active revision)
        jul_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': '2026-07-01',
            'date_to': '2026-07-31',
        })
        jul_service = ESICService(self.env, localdict={'BASIC': 20000.0, 'HRA': 6250.0})
        jul_esic_wage = jul_service.compute_esic_wage(jul_payslip)
        self.assertEqual(jul_esic_wage, 26250.0, "July ESIC wage must be contributable wage ₹26,250 due to period continuity")
        self.assertGreater(jul_service.compute_esic_employee(jul_payslip), 0.0)

        # September Payslip (End of active contribution period)
        sep_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': '2026-09-01',
            'date_to': '2026-09-30',
        })
        sep_service = ESICService(self.env, localdict={'BASIC': 20000.0, 'HRA': 6250.0})
        sep_esic_wage = sep_service.compute_esic_wage(sep_payslip)
        self.assertEqual(sep_esic_wage, 26250.0, "September ESIC wage must remain active until Sept 30")
        self.assertGreater(sep_service.compute_esic_employee(sep_payslip), 0.0)

        # October Payslip (Start of NEW contribution period: Oct 1)
        oct_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': '2026-10-01',
            'date_to': '2026-10-31',
        })
        oct_service = ESICService(self.env, localdict={'BASIC': 20000.0, 'HRA': 6250.0})
        oct_esic_wage = oct_service.compute_esic_wage(oct_payslip)
        self.assertEqual(oct_esic_wage, 0.0, "October ESIC wage must be 0.0 as new contribution period starts above ceiling")
        self.assertEqual(oct_service.compute_esic_employee(oct_payslip), 0.0)

