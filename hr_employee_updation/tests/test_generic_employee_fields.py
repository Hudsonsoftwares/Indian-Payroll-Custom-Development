# -*- coding: utf-8 -*-
import base64
from datetime import timedelta
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestGenericEmployeeFields(common.TransactionCase):

    def setUp(self):
        super(TestGenericEmployeeFields, self).setUp()
        self.lang_en = self.env['res.lang'].search([('code', '=', 'en_US')], limit=1)
        if not self.lang_en:
            self.lang_en = self.env['res.lang'].search([], limit=1)

        self.country_in = self.env.ref('base.in', raise_if_not_found=False) or self.env['res.country'].search([('code', '=', 'IN')], limit=1)
        self.country_ae = self.env.ref('base.ae', raise_if_not_found=False) or self.env['res.country'].search([('code', '=', 'AE')], limit=1)

        self.company_1 = self.env['res.company'].create({
            'name': 'Global Corp A',
            'country_id': self.country_in.id if self.country_in else False,
        })
        self.company_2 = self.env['res.company'].create({
            'name': 'Global Corp B',
            'country_id': self.country_ae.id if self.country_ae else False,
        })

    def test_01_personal_info_and_preferences(self):
        """Test generic personal info fields: show_birthday_to_employees, is_disabled, payslip_lang_id."""
        employee = self.env['hr.employee'].create({
            'name': 'Alice Smith',
            'company_id': self.company_1.id,
            'show_birthday_to_employees': True,
            'is_disabled': False,
            'payslip_lang_id': self.lang_en.id if self.lang_en else False,
        })
        self.assertTrue(employee.show_birthday_to_employees)
        self.assertFalse(employee.is_disabled)
        if self.lang_en:
            self.assertEqual(employee.payslip_lang_id.id, self.lang_en.id)

    def test_02_visa_work_permit_expiry(self):
        """Test generic work permit expiry date saving."""
        expiry_date = fields.Date.today() + timedelta(days=365)
        employee = self.env['hr.employee'].create({
            'name': 'Bob Johnson',
            'company_id': self.company_1.id,
            'work_permit_expiry_date': expiry_date,
        })
        self.assertEqual(employee.work_permit_expiry_date, expiry_date)

    def test_03_citizenship_non_resident(self):
        """Test generic non-resident boolean field."""
        employee = self.env['hr.employee'].create({
            'name': 'Carlos Gomez',
            'company_id': self.company_2.id,
            'is_non_resident': True,
        })
        self.assertTrue(employee.is_non_resident)

    def test_04_family_spouse_fields(self):
        """Test spouse legal name and valid spouse birthdate."""
        past_birthdate = fields.Date.today() - timedelta(days=365 * 30)
        employee = self.env['hr.employee'].create({
            'name': 'David Miller',
            'company_id': self.company_1.id,
            'spouse_legal_name': 'Eleanor Vance-Miller',
            'spouse_birthdate': past_birthdate,
        })
        self.assertEqual(employee.spouse_legal_name, 'Eleanor Vance-Miller')
        self.assertEqual(employee.spouse_birthdate, past_birthdate)

    def test_05_spouse_birthdate_future_validation(self):
        """Test that a future spouse birthdate raises a ValidationError."""
        future_birthdate = fields.Date.today() + timedelta(days=10)
        with self.assertRaises(ValidationError):
            self.env['hr.employee'].create({
                'name': 'Frank Castle',
                'company_id': self.company_1.id,
                'spouse_legal_name': 'Maria Castle',
                'spouse_birthdate': future_birthdate,
            })

    def test_06_document_attachments_upload(self):
        """Test uploading SIM Card Copy and Internet Subscription Invoice attachments."""
        sim_data = base64.b64encode(b"Dummy SIM Card PDF Content")
        invoice_data = base64.b64encode(b"Dummy Internet Invoice PDF Content")

        employee = self.env['hr.employee'].create({
            'name': 'Grace Hopper',
            'company_id': self.company_2.id,
            'sim_card_copy': sim_data,
            'sim_card_copy_filename': 'sim_card_scan.pdf',
            'internet_subscription_invoice': invoice_data,
            'internet_subscription_invoice_filename': 'internet_bill_jan2026.pdf',
        })

        self.assertEqual(employee.sim_card_copy_filename, 'sim_card_scan.pdf')
        self.assertEqual(employee.internet_subscription_invoice_filename, 'internet_bill_jan2026.pdf')
        self.assertTrue(bool(employee.sim_card_copy))
        self.assertTrue(bool(employee.internet_subscription_invoice))

    def test_07_multi_company_independence(self):
        """Test that generic fields function independently across companies and country contexts."""
        emp_comp1 = self.env['hr.employee'].create({
            'name': 'Emp India Corp',
            'company_id': self.company_1.id,
            'is_non_resident': False,
            'is_disabled': True,
        })
        emp_comp2 = self.env['hr.employee'].create({
            'name': 'Emp UAE Corp',
            'company_id': self.company_2.id,
            'is_non_resident': True,
            'is_disabled': False,
        })

        self.assertFalse(emp_comp1.is_non_resident)
        self.assertTrue(emp_comp1.is_disabled)

        self.assertTrue(emp_comp2.is_non_resident)
        self.assertFalse(emp_comp2.is_disabled)
