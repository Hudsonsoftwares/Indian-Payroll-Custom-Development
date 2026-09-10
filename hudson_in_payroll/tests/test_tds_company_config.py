# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from odoo.exceptions import ValidationError
from odoo.addons.hudson_in_payroll.services.tds.tds_company_config_validator import TdsCompanyConfigValidator


@tagged('post_install', '-at_install', 'tds', 'tds_company_config')
class TestTdsCompanyConfig(common.TransactionCase):

    def setUp(self):
        super(TestTdsCompanyConfig, self).setUp()
        self.company = self.env.company
        # Ensure company TDS is disabled initially for clean baseline
        self.company.write({
            'hds_in_tds_applicable': False,
            'hds_in_tan': False,
            'hds_in_default_tax_regime': 'new',
            'hds_in_default_tax_year': False,
        })
        self.validator = TdsCompanyConfigValidator(self.env)

    def test_01_tds_default_values(self):
        """Test default values for TDS company configuration fields."""
        self.assertFalse(self.company.hds_in_tds_applicable)
        self.assertEqual(self.company.hds_in_default_tax_regime, 'new')

    def test_02_enable_tds_with_valid_tan(self):
        """Test enabling TDS with valid 10-character TAN format (ABCD12345E)."""
        self.company.write({
            'hds_in_tds_applicable': True,
            'hds_in_tan': 'ABCD12345E',
            'hds_in_default_tax_regime': 'new',
        })
        self.assertTrue(self.company.hds_in_tds_applicable)
        self.assertEqual(self.company.hds_in_tan, 'ABCD12345E')
        self.assertEqual(self.company.hds_in_default_tax_regime, 'new')

    def test_03_enable_tds_missing_tan_raises(self):
        """Test enabling TDS without TAN raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.company.write({
                'hds_in_tds_applicable': True,
                'hds_in_tan': False,
            })

    def test_04_enable_tds_invalid_tan_raises(self):
        """Test enabling TDS with invalid TAN formats raises ValidationError."""
        invalid_tans = ['12345', 'ABCDE12345', 'abcd123', 'ABCD123456', '1234ABCD5E']
        for tan in invalid_tans:
            with self.subTest(tan=tan):
                with self.assertRaises(ValidationError):
                    self.company.write({
                        'hds_in_tds_applicable': True,
                        'hds_in_tan': tan,
                    })

    def test_05_tan_auto_uppercase_and_trim(self):
        """Test that lower-case TAN with whitespace is auto-trimmed and converted to uppercase."""
        self.company.write({
            'hds_in_tds_applicable': True,
            'hds_in_tan': '  mumb12345a  ',
            'hds_in_default_tax_regime': 'old',
        })
        self.assertEqual(self.company.hds_in_tan, 'MUMB12345A')
        self.assertEqual(self.company.hds_in_default_tax_regime, 'old')

    def test_06_res_config_settings_tds_integration(self):
        """Test reading and saving TDS configuration via res.config.settings transient model."""
        config = self.env['res.config.settings'].create({
            'hds_in_tds_applicable': True,
            'hds_in_tan': 'DELA98765B',
            'hds_in_default_tax_regime': 'new',
        })
        config.execute()

        self.assertTrue(self.company.hds_in_tds_applicable)
        self.assertEqual(self.company.hds_in_tan, 'DELA98765B')
        self.assertEqual(self.company.hds_in_default_tax_regime, 'new')

    def test_07_tds_company_validator_service(self):
        """Test TdsCompanyConfigValidator service behavior when TDS disabled vs enabled."""
        # 1. Disabled TDS -> returns valid (skipped)
        self.company.write({'hds_in_tds_applicable': False})
        res_disabled = self.validator.validate(self.company)
        self.assertTrue(res_disabled.is_valid)
        self.assertFalse(res_disabled.is_enabled)

        # 2. Enabled TDS with valid TAN -> returns valid and enabled
        self.company.write({
            'hds_in_tds_applicable': True,
            'hds_in_tan': 'PUNE54321C',
            'hds_in_default_tax_regime': 'new',
        })
        res_enabled = self.validator.validate(self.company)
        self.assertTrue(res_enabled.is_valid)
        self.assertTrue(res_enabled.is_enabled)
        self.assertEqual(res_enabled.tan, 'PUNE54321C')
        self.assertEqual(res_enabled.default_tax_regime, 'new')

    def test_08_tds_financial_year_model_relation(self):
        """Test linking tds.financial.year master record as default tax year on res.company."""
        fin_year = self.env['tds.financial.year'].create({
            'name': 'FY 2025-26 Test',
            'code': '2025-2026-TEST',
            'assessment_year': '2026-2027',
            'start_date': '2025-04-01',
            'end_date': '2026-03-31',
        })
        self.company.write({
            'hds_in_tds_applicable': True,
            'hds_in_tan': 'CHNA11223D',
            'hds_in_default_tax_year': fin_year.id,
        })
        self.assertEqual(self.company.hds_in_default_tax_year, fin_year)

    def test_09_strict_fy_validation_prohibits_silent_fallback(self):
        """Test that TdsParameterService.get_financial_year raises explicit ValidationError for unconfigured dates."""
        from odoo.addons.hudson_in_payroll.services.tds.tds_parameter_service import TdsParameterService
        param_svc = TdsParameterService(self.env)
        # Search for a future year date with no active FY record
        future_date = '2035-05-15'
        with self.assertRaises(ValidationError):
            param_svc.get_financial_year(eval_date=future_date)

    def test_10_financial_year_roll_over_wizard(self):
        """Test administrative Financial Year Roll-Over Wizard creating next FY and cloning slabs."""
        source_fy = self.env['tds.financial.year'].create({
            'name': 'FY 2026-27 Source',
            'code': '2026-2027-SRC',
            'assessment_year': '2027-2028',
            'start_date': '2026-04-01',
            'end_date': '2027-03-31',
            'active': True,
        })
        # Create a tax slab in source FY
        self.env['tds.tax.slab'].create({
            'financial_year_id': source_fy.id,
            'regime_code': 'new',
            'income_from': 0,
            'income_to': 400000,
            'rate': 0.0,
        })

        wizard = self.env['tds.financial.year.wizard'].create({
            'source_fy_id': source_fy.id,
            'name': 'FY 2027-28 Target',
            'code': '2027-2028-TRG',
            'assessment_year': '2028-2029',
            'start_date': '2027-04-01',
            'end_date': '2028-03-31',
            'copy_tax_slabs': True,
            'copy_surcharge_slabs': True,
            'set_as_company_default': True,
            'close_previous_fy': True,
        })
        wizard.action_create_financial_year()

        new_fy = self.env['tds.financial.year'].search([('code', '=', '2027-2028-TRG')], limit=1)
        self.assertTrue(new_fy)
        self.assertEqual(len(new_fy.tax_slab_ids), 1)
        self.assertTrue(source_fy.is_closed)
        self.assertEqual(self.company.hds_in_default_tax_year, new_fy)

    def test_11_closed_fy_immutability(self):
        """Test that closed Financial Years raise ValidationError when modified."""
        closed_fy = self.env['tds.financial.year'].create({
            'name': 'FY 2024-25 Closed',
            'code': '2024-2025-CLOSED',
            'assessment_year': '2025-2026',
            'start_date': '2024-04-01',
            'end_date': '2025-03-31',
            'is_closed': True,
        })
        with self.assertRaises(ValidationError):
            closed_fy.write({'name': 'Attempted Rename'})

