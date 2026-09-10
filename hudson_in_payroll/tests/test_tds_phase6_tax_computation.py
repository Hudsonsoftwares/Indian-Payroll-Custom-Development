# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo import fields


class TestTdsPhase6TaxComputation(TransactionCase):

    def setUp(self):
        super(TestTdsPhase6TaxComputation, self).setUp()
        self.fy = self.env['tds.financial.year'].search([('code', '=', '2025-2026')], limit=1)
        if not self.fy:
            self.fy = self.env['tds.financial.year'].create({
                'name': 'Financial Year 2025-2026',
                'code': '2025-2026',
                'start_date': '2025-04-01',
                'end_date': '2026-03-31',
                'is_active': True,
            })

    def test_01_taxable_income_service(self):
        """Test TaxableIncomeService calculating Net Taxable Income = max(0, GTI - Deductions)."""
        from hudson_in_payroll.services.tds.taxable_income_service import TaxableIncomeService
        svc = TaxableIncomeService(self.env)

        res = svc.calculate_taxable_income(gross_total_income=1000000.0, total_approved_deductions=250000.0)
        self.assertEqual(res.net_taxable_income, 750000.0)

        # High deduction zero floor test
        res_zero = svc.calculate_taxable_income(gross_total_income=300000.0, total_approved_deductions=400000.0)
        self.assertEqual(res_zero.net_taxable_income, 0.0)

    def test_02_income_tax_slab_service_new_regime(self):
        """Test IncomeTaxSlabService progressive slab rates under New Regime FY 2025-26."""
        from hudson_in_payroll.services.tds.income_tax_slab_service import IncomeTaxSlabService
        svc = IncomeTaxSlabService(self.env)

        # Taxable Income = ₹12,00,000 under New Regime
        # Slabs: 0-4L@0% (0), 4L-8L@5% (20,000), 8L-12L@10% (40,000) -> Base Tax = ₹60,000
        res = svc.calculate_base_tax(net_taxable_income=1200000.0, financial_year=self.fy, regime_code='new')
        self.assertEqual(res.base_tax_liability, 600000.0 * 0.10)  # Capped up to 12L slab

    def test_03_rebate_engine_service_section_87a_and_marginal_relief(self):
        """Test Section 87A rebate and Section 115BAC marginal relief."""
        from hudson_in_payroll.services.tds.rebate_engine_service import RebateEngineService
        svc = RebateEngineService(self.env)

        # 1. New Regime Taxable Income ₹6,50,000 (<= 7.0L threshold) -> Full 87A rebate
        res_full = svc.apply_rebate(net_taxable_income=650000.0, base_tax_liability=12500.0, regime_code='new')
        self.assertEqual(res_full.rebate_applied, 12500.0)
        self.assertEqual(res_full.tax_after_rebate, 0.0)

        # 2. New Regime Taxable Income ₹7,10,000 (Slightly > 7.0L) -> Marginal relief applied so tax <= 10,000
        res_marginal = svc.apply_rebate(net_taxable_income=710000.0, base_tax_liability=15500.0, regime_code='new')
        self.assertGreater(res_marginal.rebate_applied, 0.0)
        self.assertEqual(res_marginal.tax_after_rebate, 10000.0)

    def test_04_surcharge_and_cess_services(self):
        """Test SurchargeEngineService and HealthEducationCessService."""
        from hudson_in_payroll.services.tds.surcharge_engine_service import SurchargeEngineService
        from hudson_in_payroll.services.tds.health_education_cess_service import HealthEducationCessService

        sur_svc = SurchargeEngineService(self.env)
        cess_svc = HealthEducationCessService(self.env)

        # 1. Low income (No surcharge)
        sur_res = sur_svc.calculate_surcharge(net_taxable_income=1000000.0, tax_after_rebate=50000.0, financial_year=self.fy, regime_code='new')
        self.assertEqual(sur_res.surcharge_amount, 0.0)

        # 2. Cess (4% of ₹50,000 = ₹2,000)
        cess_res = cess_svc.calculate_cess(tax_plus_surcharge=50000.0)
        self.assertEqual(cess_res.cess_amount, 2000.0)
        self.assertEqual(cess_res.total_annual_tax_liability, 52000.0)
