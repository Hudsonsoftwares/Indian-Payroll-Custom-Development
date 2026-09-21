# -*- coding: utf-8 -*-
from datetime import date
from odoo.tests.common import TransactionCase
from odoo.addons.hudson_in_payroll.services.professional_tax.professional_tax_service import ProfessionalTaxService
from odoo.addons.hudson_in_payroll.services.professional_tax.pt_period_config_service import PTPeriodScheduleService
from odoo.addons.hudson_in_payroll.services.professional_tax.pt_periodicity_strategy import (
    PTPeriodicityStrategyRegistry, PT_COUNTED_PAYSLIP_STATES
)


class TestPTMinServiceDays(TransactionCase):
    """
    Test suite for Kerala 60-day PT rule and PT engine guards:
    1. min_service_days and appointment days service calculation in PTPeriodScheduleService
    2. BELOW_MIN_SERVICE_DAYS status when service days < 60 in half-year window
    3. ZERO_WAGE guard when earned wage is 0 (except simulation)
    4. Net Pay Guard (PT capped at GROSS + DED)
    5. get_period_already_deducted states (verify/done/paid only, never draft/cancel)
    """

    def setUp(self):
        super().setUp()
        self.pt_service = ProfessionalTaxService(self.env)
        self.sched_service = PTPeriodScheduleService(self.env)
        self.company = self.env.company

        self.state_kl = self.env.ref('base.state_in_kl', raise_if_not_found=False) or self.env['res.country.state'].search([('code', '=', 'KL')], limit=1)
        self.state_mh = self.env.ref('base.state_in_mh', raise_if_not_found=False) or self.env['res.country.state'].search([('code', '=', 'MH')], limit=1)

        # Create test employee
        self.emp = self.env['hr.employee'].create({
            'name': 'PT Min Service Days Test Employee',
            'company_id': self.company.id,
            'hds_in_pt_applicable': True,
        })
        self.emp.write({'contract_date_start': '2026-04-01', 'date_start': '2026-04-01'})
        if self.emp.version_id:
            self.emp.version_id.write({'contract_date_start': '2026-04-01', 'date_start': '2026-04-01'})

    def test_01_service_days_calculation(self):
        """Tests exact calculation of service days in half-yearly period window."""
        window_start = date(2026, 4, 1)
        window_end = date(2026, 9, 30)

        # Case A: Joined 2 Aug 2026 -> 30 days in Aug + 30 days in Sep = 60 days
        self.emp.write({'contract_date_start': '2026-08-02', 'date_start': '2026-08-02'})
        if self.emp.version_id:
            self.emp.version_id.write({'contract_date_start': '2026-08-02', 'date_start': '2026-08-02'})
        days_60 = self.sched_service.compute_service_days(self.emp, window_start, window_end)
        self.assertEqual(days_60, 60, "Joining on 2 Aug should yield exactly 60 service days in Apr-Sep window.")

        # Also test calculate_service_days alias
        days_alias = self.sched_service.calculate_service_days(self.emp, window_start, window_end)
        self.assertEqual(days_alias, 60)

        # Case B: Joined 3 Aug 2026 -> 29 days in Aug + 30 days in Sep = 59 days
        self.emp.write({'contract_date_start': '2026-08-03', 'date_start': '2026-08-03'})
        if self.emp.version_id:
            self.emp.version_id.write({'contract_date_start': '2026-08-03', 'date_start': '2026-08-03'})
        days_59 = self.sched_service.compute_service_days(self.emp, window_start, window_end)
        self.assertEqual(days_59, 59, "Joining on 3 Aug should yield 59 service days in Apr-Sep window.")

        # Case C: Resigned mid-period (joined 1 Apr, left 15 May -> 45 days)
        self.emp.write({
            'contract_date_start': '2026-04-01', 'date_start': '2026-04-01',
            'departure_date': '2026-05-15', 'contract_date_end': '2026-05-15'
        })
        if self.emp.version_id:
            self.emp.version_id.write({
                'contract_date_start': '2026-04-01', 'date_start': '2026-04-01',
                'departure_date': '2026-05-15', 'contract_date_end': '2026-05-15'
            })
        days_45 = self.sched_service.compute_service_days(self.emp, window_start, window_end)
        self.assertEqual(days_45, 45, "Resignation on 15 May should yield 45 service days.")

    def test_02_kerala_min_service_days_guard(self):
        """Tests that Kerala PT returns BELOW_MIN_SERVICE_DAYS when service days < 60."""
        sched = self.env['pt.period.schedule'].search([
            ('state_id', '=', self.state_kl.id),
            ('periodicity', '=', 'half_yearly'),
            ('window_start_month', '=', '4'),
            ('window_end_month', '=', '9'),
        ], limit=1)
        if not sched:
            sched = self.env['pt.period.schedule'].create({
                'state_id': self.state_kl.id,
                'periodicity': 'half_yearly',
                'window_start_month': '4',
                'window_end_month': '9',
                'deduction_strategy': 'end_of_period',
                'deduction_month': '9',
                'min_service_days': 60,
                'active': True,
            })
        else:
            sched.write({'min_service_days': 60})

        # Sub-scenario 1: Joined 3 Aug 2026 (59 days) -> PT = 0, BELOW_MIN_SERVICE_DAYS
        self.emp.write({'contract_date_start': '2026-08-03', 'date_start': '2026-08-03', 'departure_date': False})
        if self.emp.version_id:
            self.emp.version_id.write({'contract_date_start': '2026-08-03', 'date_start': '2026-08-03', 'departure_date': False})

        res_59 = self.pt_service.compute_pt(
            employee=self.emp,
            salary=50000.0,
            eval_date=date(2026, 9, 30),
            state=self.state_kl,
        )
        self.assertEqual(res_59.amount, 0.0)
        self.assertEqual(res_59.validation_status, 'BELOW_MIN_SERVICE_DAYS')
        self.assertFalse(res_59.is_valid)

        # Sub-scenario 2: Joined 2 Aug 2026 (60 days) -> PT applies
        self.emp.write({'contract_date_start': '2026-08-02', 'date_start': '2026-08-02'})
        if self.emp.version_id:
            self.emp.version_id.write({'contract_date_start': '2026-08-02', 'date_start': '2026-08-02'})

        res_60 = self.pt_service.compute_pt(
            employee=self.emp,
            salary=50000.0,
            eval_date=date(2026, 9, 30),
            state=self.state_kl,
        )
        self.assertNotEqual(res_60.validation_status, 'BELOW_MIN_SERVICE_DAYS')
        self.assertTrue(res_60.amount > 0.0)

    def test_03_zero_earned_wage_guard(self):
        """Tests that zero earned wage results in ZERO_WAGE status (skipped in simulation)."""
        # Actual computation with zero wage
        res_zero = self.pt_service.compute_pt(
            employee=self.emp,
            salary=0.0,
            eval_date=date(2026, 9, 30),
            state=self.state_kl,
            is_simulation=False,
        )
        self.assertEqual(res_zero.amount, 0.0)
        self.assertEqual(res_zero.validation_status, 'ZERO_WAGE')
        self.assertFalse(res_zero.is_valid)

        # Simulation mode should not trigger ZERO_WAGE
        res_sim = self.pt_service.compute_pt(
            employee=self.emp,
            salary=0.0,
            eval_date=date(2026, 9, 30),
            state=self.state_kl,
            is_simulation=True,
        )
        self.assertNotEqual(res_sim.validation_status, 'ZERO_WAGE')

    def test_04_net_pay_guard(self):
        """Tests that PT deduction is capped at GROSS + DED from localdict."""
        class MockCategories:
            def __init__(self, gross, ded):
                self.GROSS = gross
                self.DED = ded

        # Sub-scenario 1: Gross 5000, other deductions -4900 -> net available = 100
        # If PT would be 1250, it should be capped at 100
        cats = MockCategories(gross=5000.0, ded=-4900.0)
        res_capped = self.pt_service.compute_pt(
            employee=self.emp,
            salary=50000.0,
            eval_date=date(2026, 9, 30),
            state=self.state_kl,
            localdict={'categories': cats},
            is_simulation=False,
        )
        self.assertEqual(res_capped.amount, 100.0, "PT should be capped at remaining net earnings (100.0).")

        # Sub-scenario 2: Gross 5000, other deductions -5000 -> net available = 0
        cats_zero = MockCategories(gross=5000.0, ded=-5000.0)
        res_zero_net = self.pt_service.compute_pt(
            employee=self.emp,
            salary=50000.0,
            eval_date=date(2026, 9, 30),
            state=self.state_kl,
            localdict={'categories': cats_zero},
            is_simulation=False,
        )
        self.assertEqual(res_zero_net.amount, 0.0, "PT should be capped at 0 when other deductions equal gross.")

        # Sub-scenario 3: Simulation skips net pay guard
        res_sim = self.pt_service.compute_pt(
            employee=self.emp,
            salary=50000.0,
            eval_date=date(2026, 9, 30),
            state=self.state_kl,
            localdict={'categories': cats},
            is_simulation=True,
        )
        self.assertTrue(res_sim.amount > 100.0, "Simulation should skip net pay guard capping.")

    def test_05_counted_payslip_states(self):
        """Tests that get_period_already_deducted counts only verify, done, paid states."""
        strategy = PTPeriodicityStrategyRegistry.get_strategy('half_yearly')
        self.assertEqual(PT_COUNTED_PAYSLIP_STATES, ('verify', 'done', 'paid'))

        struct = self.env.ref('hudson_payroll_base.structure_base', raise_if_not_found=False) or self.env['hr.payroll.structure'].search([], limit=1)

        pt_rule = self.env.ref('hudson_in_payroll.hds_in_rule_pt', raise_if_not_found=False) or self.env['hr.salary.rule'].search([('code', '=', 'PT')], limit=1)

        contract = getattr(self.emp, 'contract_id', False) or getattr(self.emp, 'version_id', False)
        # Create a draft payslip with PT line
        slip_draft = self.env['hr.payslip'].create({
            'name': 'Draft Slip Apr',
            'employee_id': self.emp.id,
            'contract_id': contract.id if contract else False,
            'date_from': '2026-04-01',
            'date_to': '2026-04-30',
            'struct_id': struct.id if struct else False,
            'state': 'draft',
        })
        line = self.env['hr.payslip.line'].create({
            'slip_id': slip_draft.id,
            'employee_id': self.emp.id,
            'contract_id': contract.id if contract else False,
            'salary_rule_id': pt_rule.id if pt_rule else False,
            'name': 'Professional Tax',
            'code': 'PT',
            'amount': -500.0,
            'quantity': 1.0,
            'total': -500.0,
        })
        self.env.invalidate_all()

        deducted = strategy.get_period_already_deducted(
            self.env, employee=self.emp, start_date=date(2026, 4, 1), eval_date=date(2026, 9, 30)
        )
        self.assertEqual(deducted, 0.0, "Draft payslip should NOT be counted in already deducted PT.")

        # Mark slip as paid
        slip_draft.write({'state': 'paid'})
        self.env.invalidate_all()
        deducted_paid = strategy.get_period_already_deducted(
            self.env, employee=self.emp, start_date=date(2026, 4, 1), eval_date=date(2026, 9, 30)
        )
        self.assertEqual(deducted_paid, 500.0, "Paid payslip SHOULD be counted in already deducted PT.")
