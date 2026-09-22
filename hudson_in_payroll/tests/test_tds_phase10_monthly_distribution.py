# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields
from odoo.addons.hudson_in_payroll.services.tds.payroll_period_service import PayrollPeriodService
from odoo.addons.hudson_in_payroll.services.tds.monthly_tds_distribution_service import MonthlyTDSDistributionService
from odoo.addons.hudson_in_payroll.services.tds.salary_projection_service import SalaryProjectionService


class TestTdsPhase10MonthlyDistribution(TransactionCase):

    def setUp(self):
        super(TestTdsPhase10MonthlyDistribution, self).setUp()
        self.fy = self.env['tds.financial.year'].search([('code', '=', '2025-2026')], limit=1)
        if not self.fy:
            self.fy = self.env['tds.financial.year'].create({
                'name': 'Financial Year 2025-2026',
                'code': '2025-2026',
                'assessment_year': '2026-2027',
                'start_date': '2025-04-01',
                'end_date': '2026-03-31',
                'active': True,
            })

        self.employee = self.env['hr.employee'].create({
            'name': 'Phase 10 Monthly TDS Test Employee',
            'birthday': '1990-05-15',
        })

    def test_01_payroll_period_service_dynamic_periods(self):
        """Test PayrollPeriodService resolving remaining periods dynamically across all 12 months under Section 192."""
        period_svc = PayrollPeriodService(self.env)

        # April evaluation date (month 4) = 12 periods
        eval_april = fields.Date.from_string('2025-04-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_april), 12)

        # May evaluation date (month 5) = 11 periods
        eval_may = fields.Date.from_string('2025-05-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_may), 11)

        # August evaluation date (month 8) = 8 periods
        eval_aug = fields.Date.from_string('2025-08-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_aug), 8)

        # October evaluation date (month 10) = 6 periods
        eval_oct = fields.Date.from_string('2025-10-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_oct), 6)

        # December evaluation date (month 12) = 4 periods
        eval_dec = fields.Date.from_string('2025-12-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_dec), 4)

        # January evaluation date (month 1) = 3 distribution periods
        eval_jan = fields.Date.from_string('2026-01-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_jan), 3)

        # February evaluation date (month 2) = 2 distribution periods
        eval_feb = fields.Date.from_string('2026-02-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_feb), 2)

        # March evaluation date (month 3) = 1 distribution period
        eval_march = fields.Date.from_string('2026-03-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_march), 1)

    def test_02_monthly_tds_distribution_service_without_previous_employer(self):
        """Test MonthlyTDSDistributionService without Form 12B or YTD TDS."""
        dist_svc = MonthlyTDSDistributionService(self.env)

        eval_april = fields.Date.from_string('2025-04-15')
        annual_tax = 120000.0  # ₹1,20,000 annual tax liability

        res = dist_svc.calculate_monthly_tds(self.employee, self.fy, total_annual_tax_liability=annual_tax, eval_date=eval_april)
        self.assertEqual(res.remaining_payroll_periods, 12)
        self.assertEqual(res.ytd_tds_deducted, 0.0)
        self.assertEqual(res.prev_employer_tds, 0.0)
        self.assertEqual(res.remaining_annual_tax_liability, 120000.0)
        self.assertEqual(res.current_month_tds, 10000.0)  # 1,20,000 / 12 = 10,000 / month

    def test_03_monthly_tds_distribution_with_form12b_prev_employer_tds(self):
        """Test MonthlyTDSDistributionService with Form 12B previous employer TDS adjustment."""
        dist_svc = MonthlyTDSDistributionService(self.env)

        # Create Form 12B declaration with ₹30,000 previous employer TDS deducted
        self.env['tds.employee.income.declaration'].create({
            'employee_id': self.employee.id,
            'financial_year_id': self.fy.id,
            'prev_employer_taxable_gross': 250000.0,
            'prev_employer_tds': 30000.0,
        })

        eval_january = fields.Date.from_string('2026-01-15')  # 3 remaining distribution periods for K=3
        annual_tax = 90000.0

        res = dist_svc.calculate_monthly_tds(self.employee, self.fy, total_annual_tax_liability=annual_tax, eval_date=eval_january)
        self.assertEqual(res.prev_employer_tds, 30000.0)
        self.assertEqual(res.remaining_annual_tax_liability, 60000.0)  # 90,000 - 30,000 = 60,000
        self.assertEqual(res.remaining_payroll_periods, 3)
        self.assertEqual(res.current_month_tds, 20000.0)  # 60,000 / 3 = 20,000 / month

    def test_04_zero_floor_remaining_liability(self):
        """Test that remaining liability does not become negative when TDS paid exceeds annual liability."""
        dist_svc = MonthlyTDSDistributionService(self.env)

        self.env['tds.employee.income.declaration'].create({
            'employee_id': self.employee.id,
            'financial_year_id': self.fy.id,
            'prev_employer_tds': 50000.0,
        })

        eval_april = fields.Date.from_string('2025-04-15')
        annual_tax = 40000.0  # Annual tax liability is 40k, but 50k already deducted

        res = dist_svc.calculate_monthly_tds(self.employee, self.fy, total_annual_tax_liability=annual_tax, eval_date=eval_april)
        self.assertEqual(res.remaining_annual_tax_liability, 0.0)
        self.assertEqual(res.current_month_tds, 0.0)

    def test_05_missing_input_validation(self):
        """Test error handling when required parameters are missing."""
        dist_svc = MonthlyTDSDistributionService(self.env)

        with self.assertRaises(ValidationError):
            dist_svc.calculate_monthly_tds(False, self.fy, 50000.0)

    def test_06_countdown_remaining_periods(self):
        """Test countdown of dynamic remaining periods."""
        period_svc = PayrollPeriodService(self.env)

        eval_nov = fields.Date.from_string('2025-11-15')
        eval_dec = fields.Date.from_string('2025-12-15')
        eval_jan = fields.Date.from_string('2026-01-15')

        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_nov), 5)
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_dec), 4)
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_jan), 3)

    def test_07_mid_year_salary_hike_dynamic_amortization(self):
        """
        Test Section 192 dynamic TDS redistribution when employee receives a mid-year salary hike in August.
        - Apr-Jul: TDS ₹10,000/mo deducted (Total YTD TDS = ₹40,000)
        - In August: Salary hike occurs. Projected annual tax increases to ₹2,00,000.
        - Remaining tax = ₹2,00,000 - ₹40,000 = ₹1,60,000.
        - Remaining periods = 8 (Aug to Mar).
        - August TDS = ₹1,60,000 / 8 = ₹20,000 (NOT the buggy ₹2,00,000 / 12 = ₹16,666.67).
        """
        dist_svc = MonthlyTDSDistributionService(self.env)

        # Mock previous employer / YTD TDS: create Form 12B or payslips
        self.env['tds.employee.income.declaration'].create({
            'employee_id': self.employee.id,
            'financial_year_id': self.fy.id,
            'prev_employer_tds': 40000.0,  # Represents ₹40,000 TDS deducted during Apr-Jul
        })

        eval_august = fields.Date.from_string('2025-08-15')
        new_annual_tax = 200000.0

        res = dist_svc.calculate_monthly_tds(
            self.employee,
            self.fy,
            total_annual_tax_liability=new_annual_tax,
            eval_date=eval_august
        )

        self.assertEqual(res.remaining_payroll_periods, 8)
        self.assertEqual(res.total_tds_paid_so_far, 40000.0)
        self.assertEqual(res.remaining_annual_tax_liability, 160000.0)
        self.assertEqual(res.current_month_tds, 20000.0)

    def test_08_mid_year_joiner_dynamic_amortization(self):
        """
        Test mid-year joiner (joining date = 2025-08-01).
        In August (month 8 of calendar, month 5 of FY), remaining periods must be 8.
        In September, remaining periods must be 7.
        """
        period_svc = PayrollPeriodService(self.env)
        dist_svc = MonthlyTDSDistributionService(self.env)

        mid_year_employee = self.env['hr.employee'].create({
            'name': 'Mid Year Joiner Employee',
            'birthday': '1995-08-20',
        })
        # Set joining date on employee (or first contract start date)
        if hasattr(mid_year_employee, 'first_contract_date'):
            mid_year_employee.first_contract_date = fields.Date.from_string('2025-08-01')
        if hasattr(mid_year_employee, 'joining_date'):
            mid_year_employee.joining_date = fields.Date.from_string('2025-08-01')

        eval_august = fields.Date.from_string('2025-08-15')
        remaining_periods_aug = period_svc.calculate_remaining_periods(mid_year_employee, self.fy, eval_date=eval_august)
        self.assertEqual(remaining_periods_aug, 8)

        eval_september = fields.Date.from_string('2025-09-15')
        remaining_periods_sep = period_svc.calculate_remaining_periods(mid_year_employee, self.fy, eval_date=eval_september)
        self.assertEqual(remaining_periods_sep, 7)

        # Test monthly TDS calculation for mid-year joiner in August (annual tax ₹1,60,000 for 8 months)
        res = dist_svc.calculate_monthly_tds(
            mid_year_employee,
            self.fy,
            total_annual_tax_liability=160000.0,
            eval_date=eval_august
        )
        self.assertEqual(res.remaining_payroll_periods, 8)
        self.assertEqual(res.remaining_annual_tax_liability, 160000.0)
        self.assertEqual(res.current_month_tds, 20000.0)

    def test_09_early_departure_employee_remaining_periods(self):
        """
        Test employee departing before FY end (resignation / departure date = 2025-11-30).
        In August, remaining periods should be 4 (Aug, Sep, Oct, Nov).
        In November, remaining periods should be 1.
        """
        period_svc = PayrollPeriodService(self.env)

        leaver_emp = self.env['hr.employee'].create({
            'name': 'Early Leaver Employee',
            'birthday': '1992-03-10',
        })
        if hasattr(leaver_emp, 'departure_date'):
            leaver_emp.departure_date = fields.Date.from_string('2025-11-30')

        eval_aug = fields.Date.from_string('2025-08-15')
        rem_aug = period_svc.calculate_remaining_periods(leaver_emp, self.fy, eval_date=eval_aug)
        self.assertEqual(rem_aug, 4)

        eval_nov = fields.Date.from_string('2025-11-15')
        rem_nov = period_svc.calculate_remaining_periods(leaver_emp, self.fy, eval_date=eval_nov)
        self.assertEqual(rem_nov, 1)

    def test_10_october_joiner_salary_projection_and_remaining_months(self):
        """
        User Requirement Test:
        When an employee joins in October with monthly salary ₹2,00,000:
        1. Total FY periods for employee must be 6 (Oct to Mar).
        2. In October (eval_date = 2025-10-15), SalaryProjectionService must project
           salary for 6 months: 6 * ₹2,00,000 = ₹12,00,000 (NOT the hardcoded 12 * ₹2,00,000 = ₹24,00,000).
        3. Remaining payroll periods under Section 192 must be 6.
        4. Payslip remaining future months (rem_periods - 1) must be 5 (Nov, Dec, Jan, Feb, Mar).
        """
        period_svc = PayrollPeriodService(self.env)
        salary_svc = SalaryProjectionService(self.env)

        oct_employee = self.env['hr.employee'].create({
            'name': 'October Joiner ₹2L Salary',
            'birthday': '1993-10-10',
        })
        if hasattr(oct_employee, 'first_contract_date'):
            oct_employee.first_contract_date = fields.Date.from_string('2025-10-01')
        if hasattr(oct_employee, 'joining_date'):
            oct_employee.joining_date = fields.Date.from_string('2025-10-01')

        contract = self.env['hr.contract'].create({
            'name': 'October Joiner Contract',
            'employee_id': oct_employee.id,
            'wage': 200000.0,
            'state': 'open',
            'date_start': '2025-10-01',
        })
        if hasattr(oct_employee, 'contract_id'):
            oct_employee.contract_id = contract.id

        # 1. Verify total periods in FY
        total_fy_periods = period_svc.calculate_total_periods_in_fy(oct_employee, self.fy)
        self.assertEqual(total_fy_periods, 6, "October joiner must have exactly 6 employment periods in the FY")

        # 2. Evaluate in October (2025-10-15)
        eval_oct = fields.Date.from_string('2025-10-15')
        sal_proj = salary_svc.project_salary(oct_employee, self.fy, eval_date=eval_oct)

        # Expected: 6 * 2,00,000 = 12,00,000 (NOT 24,00,000)
        self.assertEqual(sal_proj.total_projected_current_salary, 1200000.0,
                         "Projected annual salary for October joiner at ₹2L/month must be ₹12,00,000 (6 months), NOT ₹24,00,000")
        self.assertEqual(sal_proj.months_elapsed, 1)
        self.assertEqual(sal_proj.months_remaining, 5)

        # 3. Verify remaining periods for TDS
        rem_periods = period_svc.calculate_remaining_periods(oct_employee, self.fy, eval_date=eval_oct)
        self.assertEqual(rem_periods, 6, "October payroll run must have 6 remaining periods (Oct, Nov, Dec, Jan, Feb, Mar)")

        # 4. Verify payslip future remaining months: 6 - 1 = 5
        payslip_future_months = max(0, rem_periods - 1)
        self.assertEqual(payslip_future_months, 5, "Payslip future remaining months after October must be 5")

