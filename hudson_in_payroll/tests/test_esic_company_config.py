# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestEsicCompanyConfig(common.TransactionCase):

    def setUp(self):
        super(TestEsicCompanyConfig, self).setUp()
        self.company = self.env.company

    def test_01_res_company_esic_fields(self):
        """Test default values and update on res.company ESIC configuration fields."""
        self.assertTrue(self.company.hds_in_esic_applicable)

        self.company.write({
            'hds_in_esic_applicable': True,
            'hds_in_esic_employer_code': '31000123450000101',
            'hds_in_esic_registration_no': 'ESIC/MH/3100012',
            'hds_in_esic_branch_office': 'Sub-Regional Office Thane',
        })

        self.assertEqual(self.company.hds_in_esic_employer_code, '31000123450000101')
        self.assertEqual(self.company.hds_in_esic_registration_no, 'ESIC/MH/3100012')
        self.assertEqual(self.company.hds_in_esic_branch_office, 'Sub-Regional Office Thane')

    def test_02_res_config_settings_esic_related_fields(self):
        """Test reading and writing ESIC fields via res.config.settings transient model."""
        config = self.env['res.config.settings'].create({
            'hds_in_esic_applicable': True,
            'hds_in_esic_employer_code': '31999999990000101',
            'hds_in_esic_registration_no': 'ESIC/KA/9999999',
            'hds_in_esic_branch_office': 'SRO Peenya',
        })
        config.execute()

        self.assertEqual(self.company.hds_in_esic_employer_code, '31999999990000101')
        self.assertEqual(self.company.hds_in_esic_registration_no, 'ESIC/KA/9999999')
        self.assertEqual(self.company.hds_in_esic_branch_office, 'SRO Peenya')
