# -*- coding: utf-8 -*-
from datetime import date
from odoo.tests.common import TransactionCase
from ..services.payroll.work_location_service import PayrollWorkLocationService
from ..services.lwf.lwf_rate_service import LWFRateService
from ..services.lwf.lwf_service import LWFService


class TestLWFService(TransactionCase):

    def setUp(self):
        super().setUp()
        self.location_service = PayrollWorkLocationService(self.env)
        self.rate_service = LWFRateService(self.env)

        self.country_in = self.env.ref('base.in', raise_if_not_found=False) or self.env['res.country'].search([('code', '=', 'IN')], limit=1)

        # States
        self.state_mh = self.env['res.country.state'].create({
            'name': 'Maharashtra LWF State',
            'code': 'MH_LWF',
            'country_id': self.country_in.id,
        })
        self.state_ka = self.env['res.country.state'].create({
            'name': 'Karnataka LWF State',
            'code': 'KA_LWF',
            'country_id': self.country_in.id,
        })

        # Partners & Work Location
        self.partner_mh = self.env['res.partner'].create({
            'name': 'Mumbai Office Partner',
            'state_id': self.state_mh.id,
            'country_id': self.country_in.id,
        })
        self.work_loc_mh = self.env['hr.work.location'].create({
            'name': 'Mumbai Location',
            'address_id': self.partner_mh.id,
        })

        # LWF Rate Configurations
        # Maharashtra: EE ₹25, ER ₹75, Half-Yearly in June (6) & December (12)
        self.lwf_mh = self.env['lwf.state.rate'].create({
            'state_id': self.state_mh.id,
            'emp_contribution': 25.0,
            'empl_contribution': 75.0,
            'deduction_frequency': 'half_yearly',
            'deduction_month_1': '6',
            'deduction_month_2': '12',
            'date_from': '2026-01-01',
            'active': True,
        })

        # Karnataka: EE ₹50, ER ₹100, Annual in December (12)
        self.lwf_ka = self.env['lwf.state.rate'].create({
            'state_id': self.state_ka.id,
            'emp_contribution': 50.0,
            'empl_contribution': 100.0,
            'deduction_frequency': 'annual',
            'deduction_month_1': '12',
            'date_from': '2026-01-01',
            'active': True,
        })

        # Employee assigned to Mumbai Work Location
        self.emp_mh = self.env['hr.employee'].create({
            'name': 'Maharashtra Employee',
            'work_location_id': self.work_loc_mh.id,
        })

    def test_01_rate_service_lookup(self):
        """Verify active rate config lookup by state and date effectiveness."""
        rate_mh = self.rate_service.get_rate_config(self.state_mh, eval_date=date(2026, 6, 30))
        self.assertEqual(rate_mh, self.lwf_mh)

        rate_ka = self.rate_service.get_rate_config(self.state_ka, eval_date=date(2026, 12, 31))
        self.assertEqual(rate_ka, self.lwf_ka)

    def test_02_deduction_month_schedule(self):
        """Verify deduction month applicability."""
        # MH: June (6) and Dec (12) trigger LWF; April (4) does not.
        self.assertTrue(self.rate_service.is_deduction_scheduled(self.lwf_mh, eval_date=date(2026, 6, 30)))
        self.assertTrue(self.rate_service.is_deduction_scheduled(self.lwf_mh, eval_date=date(2026, 12, 31)))
        self.assertFalse(self.rate_service.is_deduction_scheduled(self.lwf_mh, eval_date=date(2026, 4, 30)))

        # KA: Dec (12) triggers LWF; June (6) does not.
        self.assertTrue(self.rate_service.is_deduction_scheduled(self.lwf_ka, eval_date=date(2026, 12, 31)))
        self.assertFalse(self.rate_service.is_deduction_scheduled(self.lwf_ka, eval_date=date(2026, 6, 30)))

    def test_03_lwf_service_june_deduction(self):
        """June 2026 payslip for MH Employee -> EE LWF = 25, ER LWF = 75."""
        payslip_june = self.env['hr.payslip'].create({
            'employee_id': self.emp_mh.id,
            'date_from': '2026-06-01',
            'date_to': '2026-06-30',
        })
        service = LWFService(self.env)
        ee_amount = service.compute_lwf_employee(payslip_june)
        er_amount = service.compute_lwf_employer(payslip_june)
        self.assertEqual(ee_amount, 25.0)
        self.assertEqual(er_amount, 75.0)

    def test_04_lwf_service_april_off_cycle(self):
        """April 2026 payslip for MH Employee -> LWF = 0 (Not a scheduled deduction month)."""
        payslip_april = self.env['hr.payslip'].create({
            'employee_id': self.emp_mh.id,
            'date_from': '2026-04-01',
            'date_to': '2026-04-30',
        })
        service = LWFService(self.env)
        ee_amount = service.compute_lwf_employee(payslip_april)
        er_amount = service.compute_lwf_employer(payslip_april)
        self.assertEqual(ee_amount, 0.0)
        self.assertEqual(er_amount, 0.0)
