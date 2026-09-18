# -*- coding: utf-8 -*-
from datetime import date
from odoo.tests.common import TransactionCase
from odoo.addons.hudson_in_payroll.services.professional_tax.professional_tax_service import ProfessionalTaxService
from odoo.addons.hudson_in_payroll.services.professional_tax.pt_period_config_service import PTPeriodScheduleService


class TestPTConfigurableEngine(TransactionCase):
    """
    Exhaustive Test Suite for Configurable Professional Tax (PT) Periodicity & Strategy Engine.
    Validates:
    - Monthly, Quarterly, Half-Yearly, and Annual periodicities
    - End of Period (lump sum) vs Every Payroll (distributed) deduction strategies
    - Mid-period joining and mid-period leaving
    - Currency rounding reconciliation down to exact statutory period liability
    """

    def setUp(self):
        super().setUp()
        self.pt_service = ProfessionalTaxService(self.env)
        self.sched_service = PTPeriodScheduleService(self.env)

        # Base company & states
        self.company = self.env.company
        self.state_mh = self.env.ref('base.state_in_mh', raise_if_not_found=False) or self.env['res.country.state'].search([('code', '=', 'MH')], limit=1)
        self.state_kl = self.env.ref('base.state_in_kl', raise_if_not_found=False) or self.env['res.country.state'].search([('code', '=', 'KL')], limit=1)
        self.state_mp = self.env.ref('base.state_in_mp', raise_if_not_found=False) or self.env['res.country.state'].search([('code', '=', 'MP')], limit=1)

        # Create test employee with valid contract start date
        self.emp = self.env['hr.employee'].create({
            'name': 'PT Engine Test Employee',
            'company_id': self.company.id,
        })
        if self.emp.version_id:
            self.emp.version_id.write({'date_start': '2025-01-01'})
        if hasattr(self.emp, '_compute_joining_date'):
            self.emp._compute_joining_date()

        self.contract = self.emp.version_id

    def test_01_monthly_every_payroll(self):
        """Tests Monthly periodicity with Every Payroll strategy."""
        sched = self.env['pt.period.schedule'].create({
            'state_id': self.state_mh.id,
            'periodicity': 'monthly',
            'deduction_strategy': 'every_payroll',
            'active': True,
        })
        self.assertEqual(sched.distribution_method, 'full_amount')
        self.assertFalse(sched.window_start_month)
        self.assertFalse(sched.window_end_month)
        start_d, end_d = self.sched_service.resolve_period_window(sched, eval_date='2026-05-31')
        self.assertEqual(start_d, date(2026, 5, 1))
        self.assertEqual(end_d, date(2026, 5, 31))

        rem_payrolls = self.sched_service.calculate_remaining_payrolls(self.emp, start_d, end_d, '2026-05-31')
        self.assertEqual(rem_payrolls, 1)

    def test_02_quarterly_end_of_period(self):
        """Tests Quarterly periodicity with End of Period lump sum strategy in June."""
        sched = self.env['pt.period.schedule'].create({
            'state_id': self.state_mp.id,
            'periodicity': 'quarterly',
            'window_start_month': '4',
            'window_end_month': '6',
            'deduction_strategy': 'end_of_period',
            'distribution_method': 'full_amount',
            'deduction_month': '6',
            'active': True,
        })

        # April (Non-deduction month)
        should_apr = self.sched_service.should_deduct(sched, eval_date='2026-04-30', employee=self.emp)
        self.assertFalse(should_apr)

        # May (Non-deduction month)
        should_may = self.sched_service.should_deduct(sched, eval_date='2026-05-31', employee=self.emp)
        self.assertFalse(should_may)

        # June (Deduction month)
        should_jun = self.sched_service.should_deduct(sched, eval_date='2026-06-30', employee=self.emp)
        self.assertTrue(should_jun)

    def test_03_quarterly_equal_distribution(self):
        """Tests Quarterly periodicity with Equal Distribution across Q1 (April, May, June)."""
        sched = self.env['pt.period.schedule'].create({
            'state_id': self.state_mp.id,
            'periodicity': 'quarterly',
            'window_start_month': '4',
            'window_end_month': '6',
            'deduction_strategy': 'every_payroll',
            'distribution_method': 'equal_distribution',
            'active': True,
        })

        # April: remaining = 3
        rem_apr = self.sched_service.calculate_remaining_payrolls(self.emp, date(2026, 4, 1), date(2026, 6, 30), '2026-04-30')
        self.assertEqual(rem_apr, 3)

        # May: remaining = 2
        rem_may = self.sched_service.calculate_remaining_payrolls(self.emp, date(2026, 4, 1), date(2026, 6, 30), '2026-05-31')
        self.assertEqual(rem_may, 2)

        # June: remaining = 1
        rem_jun = self.sched_service.calculate_remaining_payrolls(self.emp, date(2026, 4, 1), date(2026, 6, 30), '2026-06-30')
        self.assertEqual(rem_jun, 1)

    def test_04_half_yearly_rounding_reconciliation(self):
        """Tests Half-Yearly PT equal distribution and exact currency rounding reconciliation for 1250 over 6 months."""
        from odoo.addons.hudson_in_payroll.services.professional_tax.pt_periodicity_strategy import HalfYearlyPTStrategy
        strategy = HalfYearlyPTStrategy()

        sched = self.env['pt.period.schedule'].create({
            'state_id': self.state_kl.id,
            'periodicity': 'half_yearly',
            'window_start_month': '4',
            'window_end_month': '9',
            'deduction_strategy': 'every_payroll',
            'distribution_method': 'equal_distribution',
            'active': True,
        })

        cat_pt = self.env.ref('hudson_payroll_base.rule_category_ded', raise_if_not_found=False) or self.env['hr.salary.rule.category'].search([('code', '=', 'DED')], limit=1)
        if not cat_pt:
            cat_pt = self.env['hr.salary.rule.category'].search([], limit=1)
        cat_id = cat_pt.id

        rule_pt = self.env.ref('hudson_in_payroll.hr_rule_professional_tax', raise_if_not_found=False) or self.env['hr.salary.rule'].search([('code', '=', 'PT')], limit=1)
        if not rule_pt:
            rule_pt = self.env['hr.salary.rule'].search([], limit=1)
        rule_id = rule_pt.id

        period_liability = 1250.00
        c_id = self.contract.id if self.contract else False

        # April (remaining = 6)
        ded_apr = strategy.calculate_payroll_deduction(self.env, self.emp, period_liability, '2026-04-30', period_schedule=sched)

        # Mock payslip created for April
        slip_apr = self.env['hr.payslip'].create({
            'name': 'Payslip April 2026',
            'employee_id': self.emp.id,
            'contract_id': c_id,
            'date_from': '2026-04-01',
            'date_to': '2026-04-30',
            'state': 'done',
        })
        self.env['hr.payslip.line'].create({
            'slip_id': slip_apr.id,
            'name': 'Professional Tax',
            'code': 'PT',
            'category_id': cat_id,
            'salary_rule_id': rule_id,
            'amount': ded_apr,
            'total': ded_apr,
            'contract_id': c_id,
        })

        # May (remaining = 5)
        ded_may = strategy.calculate_payroll_deduction(self.env, self.emp, period_liability, '2026-05-31', period_schedule=sched)

        slip_may = self.env['hr.payslip'].create({
            'name': 'Payslip May 2026',
            'employee_id': self.emp.id,
            'contract_id': c_id,
            'date_from': '2026-05-01',
            'date_to': '2026-05-31',
            'state': 'done',
        })
        self.env['hr.payslip.line'].create({
            'slip_id': slip_may.id,
            'name': 'Professional Tax',
            'code': 'PT',
            'category_id': cat_id,
            'salary_rule_id': rule_id,
            'amount': ded_may,
            'total': ded_may,
            'contract_id': c_id,
        })

        # June (remaining = 4)
        ded_jun = strategy.calculate_payroll_deduction(self.env, self.emp, period_liability, '2026-06-30', period_schedule=sched)

        slip_jun = self.env['hr.payslip'].create({
            'name': 'Payslip June 2026',
            'employee_id': self.emp.id,
            'contract_id': c_id,
            'date_from': '2026-06-01',
            'date_to': '2026-06-30',
            'state': 'done',
        })
        self.env['hr.payslip.line'].create({
            'slip_id': slip_jun.id,
            'name': 'Professional Tax',
            'code': 'PT',
            'category_id': cat_id,
            'salary_rule_id': rule_id,
            'amount': ded_jun,
            'total': ded_jun,
            'contract_id': c_id,
        })

        # July (remaining = 3)
        ded_jul = strategy.calculate_payroll_deduction(self.env, self.emp, period_liability, '2026-07-31', period_schedule=sched)

        slip_jul = self.env['hr.payslip'].create({
            'name': 'Payslip July 2026',
            'employee_id': self.emp.id,
            'contract_id': c_id,
            'date_from': '2026-07-01',
            'date_to': '2026-07-31',
            'state': 'done',
        })
        self.env['hr.payslip.line'].create({
            'slip_id': slip_jul.id,
            'name': 'Professional Tax',
            'code': 'PT',
            'category_id': cat_id,
            'salary_rule_id': rule_id,
            'amount': ded_jul,
            'total': ded_jul,
            'contract_id': c_id,
        })

        # August (remaining = 2)
        ded_aug = strategy.calculate_payroll_deduction(self.env, self.emp, period_liability, '2026-08-31', period_schedule=sched)

        slip_aug = self.env['hr.payslip'].create({
            'name': 'Payslip August 2026',
            'employee_id': self.emp.id,
            'contract_id': c_id,
            'date_from': '2026-08-01',
            'date_to': '2026-08-31',
            'state': 'done',
        })
        self.env['hr.payslip.line'].create({
            'slip_id': slip_aug.id,
            'name': 'Professional Tax',
            'code': 'PT',
            'category_id': cat_id,
            'salary_rule_id': rule_id,
            'amount': ded_aug,
            'total': ded_aug,
            'contract_id': c_id,
        })

        # September (remaining = 1 - final period residual)
        ded_sep = strategy.calculate_payroll_deduction(self.env, self.emp, period_liability, '2026-09-30', period_schedule=sched)

        _logger.info(f"Monthly deductions: Apr={ded_apr}, May={ded_may}, Jun={ded_jun}, Jul={ded_jul}, Aug={ded_aug}, Sep={ded_sep}")

        # Total reconciliation check
        total_deducted = ded_apr + ded_may + ded_jun + ded_jul + ded_aug + ded_sep
        self.assertAlmostEqual(total_deducted, period_liability, places=2)

    def test_05_mid_period_joining(self):
        """Tests employee joining mid-period (e.g. May 15 in Q1 April-June)."""
        emp_mid = self.env['hr.employee'].create({
            'name': 'Mid Period Joiner',
            'company_id': self.company.id,
        })
        if emp_mid.version_id:
            emp_mid.version_id.write({'date_start': '2026-05-15'})
        if hasattr(emp_mid, '_compute_joining_date'):
            emp_mid._compute_joining_date()

        sched = self.env['pt.period.schedule'].create({
            'state_id': self.state_mp.id,
            'periodicity': 'quarterly',
            'window_start_month': '4',
            'window_end_month': '6',
            'deduction_strategy': 'every_payroll',
            'distribution_method': 'equal_distribution',
            'active': True,
        })

        # May: employee joined May 15. Total eligible payrolls in Q1 = 2 (May, June).
        tot_payrolls = self.sched_service.calculate_eligible_payrolls(emp_mid, date(2026, 4, 1), date(2026, 6, 30))
        self.assertEqual(tot_payrolls, 2)

        rem_may = self.sched_service.calculate_remaining_payrolls(emp_mid, date(2026, 4, 1), date(2026, 6, 30), '2026-05-31')
        self.assertEqual(rem_may, 2)

    def test_06_mid_period_leaving(self):
        """Tests employee leaving mid-period (e.g. August 25 in H1 April-September)."""
        emp_leave = self.env['hr.employee'].create({
            'name': 'Mid Period Leaver',
            'company_id': self.company.id,
            'departure_date': '2026-08-25',
        })
        if emp_leave.version_id:
            emp_leave.version_id.write({'date_start': '2025-01-01'})
        if hasattr(emp_leave, '_compute_joining_date'):
            emp_leave._compute_joining_date()

        sched = self.env['pt.period.schedule'].create({
            'state_id': self.state_kl.id,
            'periodicity': 'half_yearly',
            'window_start_month': '4',
            'window_end_month': '9',
            'deduction_strategy': 'every_payroll',
            'distribution_method': 'equal_distribution',
            'active': True,
        })

        # In August, departure_date is Aug 25, so August is the final eligible payroll (remaining = 1)
        rem_aug = self.sched_service.calculate_remaining_payrolls(emp_leave, date(2026, 4, 1), date(2026, 9, 30), '2026-08-31')
        self.assertEqual(rem_aug, 1)

        # In End of Period strategy, August must trigger full remaining deduction because it's the final eligible payroll
        sched_end = self.env['pt.period.schedule'].create({
            'state_id': self.state_kl.id,
            'periodicity': 'half_yearly',
            'window_start_month': '4',
            'window_end_month': '9',
            'deduction_strategy': 'end_of_period',
            'distribution_method': 'full_amount',
            'deduction_month': '9',
            'active': True,
        })
        should_aug = self.sched_service.should_deduct(sched_end, eval_date='2026-08-31', employee=emp_leave)
        self.assertTrue(should_aug)
