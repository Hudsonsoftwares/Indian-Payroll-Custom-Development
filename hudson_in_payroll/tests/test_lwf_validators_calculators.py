# -*- coding: utf-8 -*-
from datetime import date
from odoo.tests.common import TransactionCase
from ..services.lwf.company_configuration_validator import CompanyConfigurationValidator
from ..services.lwf.lwf_eligibility_validator import LWFEligibilityValidator
from ..services.lwf.lwf_calculator import LWFCalculator


class TestLWFValidatorsCalculators(TransactionCase):

    def setUp(self):
        super().setUp()
        self.comp_validator = CompanyConfigurationValidator(self.env)
        self.elig_validator = LWFEligibilityValidator(self.env)
        self.calculator = LWFCalculator(self.env)

        self.country_in = self.env.ref('base.in', raise_if_not_found=False) or self.env['res.country'].search([('code', '=', 'IN')], limit=1)

        self.state_mh = self.env['res.country.state'].create({
            'name': 'Maharashtra SOA Test State',
            'code': 'MH_SOA',
            'country_id': self.country_in.id,
        })

        self.rate_mh = self.env['lwf.state.rate'].create({
            'state_id': self.state_mh.id,
            'emp_contribution': 25.0,
            'empl_contribution': 75.0,
            'deduction_frequency': 'half_yearly',
            'deduction_month_1': '6',
            'deduction_month_2': '12',
            'min_employee_count': 10,
            'date_from': '2026-01-01',
            'active': True,
        })

        self.emp = self.env['hr.employee'].create({
            'name': 'SOA Test Employee',
        })

    def test_01_company_configuration_validator_enabled(self):
        """Validates company enablement check."""
        self.env.company.hds_in_enable_lwf = True
        self.env.company.hds_in_lwf_registration_no = "LWF/MH/2026/001"

        res = self.comp_validator.validate(self.env.company)
        self.assertTrue(res.is_valid)
        self.assertTrue(res.is_enabled)
        self.assertEqual(res.registration_no, "LWF/MH/2026/001")

    def test_02_company_configuration_validator_disabled(self):
        """Validates disabled company configuration."""
        self.env.company.hds_in_enable_lwf = False

        res = self.comp_validator.validate(self.env.company)
        self.assertFalse(res.is_valid)
        self.assertFalse(res.is_enabled)

    def test_03_lwf_eligibility_validator_threshold_met(self):
        """Validates eligibility when headcount threshold (15 >= 10) and deduction month (June) match."""
        res = self.elig_validator.validate(
            employee=self.emp,
            state=self.state_mh,
            rate_config=self.rate_mh,
            eval_date=date(2026, 6, 30),
            establishment_headcount=15
        )
        self.assertTrue(res.is_eligible)
        self.assertTrue(res.is_scheduled_month)

    def test_04_lwf_eligibility_validator_threshold_failed(self):
        """Validates ineligibility when headcount threshold (5 < 10) is not met."""
        res = self.elig_validator.validate(
            employee=self.emp,
            state=self.state_mh,
            rate_config=self.rate_mh,
            eval_date=date(2026, 6, 30),
            establishment_headcount=5
        )
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.headcount, 5)

    def test_05_lwf_eligibility_validator_off_cycle_month(self):
        """Validates ineligibility for off-cycle month (April)."""
        res = self.elig_validator.validate(
            employee=self.emp,
            state=self.state_mh,
            rate_config=self.rate_mh,
            eval_date=date(2026, 4, 30),
            establishment_headcount=15
        )
        self.assertFalse(res.is_eligible)
        self.assertFalse(res.is_scheduled_month)

    def test_06_lwf_calculator_contributions(self):
        """Validates calculation math and monetary rounding."""
        ee = self.calculator.calculate_employee_contribution(self.rate_mh)
        er = self.calculator.calculate_employer_contribution(self.rate_mh)

        self.assertEqual(ee, 25.0)
        self.assertEqual(er, 75.0)
