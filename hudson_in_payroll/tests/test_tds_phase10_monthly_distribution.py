# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields


class TestTdsPhase10MonthlyDistribution(TransactionCase):

    def setUp(self):
        super(TestTdsPhase10MonthlyDistribution, self).setUp()
        self.fy = self.env['tds.financial.year'].search([('code', '=', '2025-2026')], limit=1)
        if not self.fy:
            self.fy = self.env['tds.financial.year'].create({
                'name': 'Financial Year 2025-2026',
                'code': '2025-2026',
                'start_date': '2025-04-01',
                'end_date': '2026-03-31',
                'is_active': True,
            })

        self.employee = self.env['hr.employee'].create({
            'name': 'Phase 10 Monthly TDS Test Employee',
            'birthday': '1990-05-15',
        })

    def test_01_payroll_period_service_dynamic_periods(self):
        """Test PayrollPeriodService resolving remaining periods dynamically before and after recalculation start month."""
        from hudson_in_payroll.services.tds.payroll_period_service import PayrollPeriodService
        period_svc = PayrollPeriodService(self.env)

        # Set FY recalculation parameters: Distribution Months = 3 (final 3 months: Jan, Feb, Mar)
        self.fy.write({
            'tds_recalculation_distribution_months': 3
        })

        # April evaluation date (month 4) = 12 periods (Normal Phase)
        eval_april = fields.Date.from_string('2025-04-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_april), 12)

        # May evaluation date (month 5) = 12 periods (Normal Phase)
        eval_may = fields.Date.from_string('2025-05-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_may), 12)

        # October evaluation date (month 10) = 12 periods (Normal Phase)
        eval_oct = fields.Date.from_string('2025-10-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_oct), 12)

        # December evaluation date (month 12) = 12 periods (Normal Phase)
        eval_dec = fields.Date.from_string('2025-12-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_dec), 12)

        # January evaluation date (month 1) = 3 distribution periods (Redistribution Phase ACTIVE)
        eval_jan = fields.Date.from_string('2026-01-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_jan), 3)

        # February evaluation date (month 2) = 2 distribution periods (Redistribution Phase ACTIVE)
        eval_feb = fields.Date.from_string('2026-02-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_feb), 2)

        # March evaluation date (month 3) = 1 distribution period (Redistribution Phase ACTIVE)
        eval_march = fields.Date.from_string('2026-03-15')
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_march), 1)

    def test_02_monthly_tds_distribution_service_without_previous_employer(self):
        """Test MonthlyTDSDistributionService without Form 12B or YTD TDS."""
        from hudson_in_payroll.services.tds.monthly_tds_distribution_service import MonthlyTDSDistributionService
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
        from hudson_in_payroll.services.tds.monthly_tds_distribution_service import MonthlyTDSDistributionService
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
        from hudson_in_payroll.services.tds.monthly_tds_distribution_service import MonthlyTDSDistributionService
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
        from hudson_in_payroll.services.tds.monthly_tds_distribution_service import MonthlyTDSDistributionService
        dist_svc = MonthlyTDSDistributionService(self.env)

        with self.assertRaises(ValidationError):
            dist_svc.calculate_monthly_tds(False, self.fy, 50000.0)

    def test_06_configuration_driven_redistribution_months(self):
        """Test that changing tds_recalculation_distribution_months automatically updates redistribution period."""
        from hudson_in_payroll.services.tds.payroll_period_service import PayrollPeriodService
        period_svc = PayrollPeriodService(self.env)

        # Change configuration to 4 (final 4 months: Dec, Jan, Feb, Mar)
        self.fy.write({'tds_recalculation_distribution_months': 4})
        eval_nov = fields.Date.from_string('2025-11-15')
        eval_dec = fields.Date.from_string('2025-12-15')
        eval_jan = fields.Date.from_string('2026-01-15')

        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_nov), 12)
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_dec), 4)
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_jan), 3)

        # Change configuration to 2 (final 2 months: Feb, Mar)
        self.fy.write({'tds_recalculation_distribution_months': 2})
        eval_jan = fields.Date.from_string('2026-01-15')
        eval_feb = fields.Date.from_string('2026-02-15')

        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_jan), 12)
        self.assertEqual(period_svc.calculate_remaining_periods(self.employee, self.fy, eval_date=eval_feb), 2)
