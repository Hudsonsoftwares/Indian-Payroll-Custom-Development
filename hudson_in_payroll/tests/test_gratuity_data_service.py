# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.fields import Date
from odoo.addons.hudson_in_payroll.services.gratuity.gratuity_data_service import GratuityDataService


class TestGratuityDataService(TransactionCase):

    def setUp(self):
        super(TestGratuityDataService, self).setUp()
        self.data_service = GratuityDataService(self.env)
        
        self.company = self.env['res.company'].create({
            'name': 'Gratuity Data Service Test Company',
            'hds_in_enable_gratuity': True,
        })

        self.employee = self.env['hr.employee'].create({
            'name': 'Data Service Employee',
            'company_id': self.company.id,
            'first_contract_date': Date.from_string('2018-01-01'),
        })

        self.contract = self.env['hr.version'].create({
            'name': 'Data Service Contract',
            'employee_id': self.employee.id,
            'date_start': Date.from_string('2018-01-01'),
            'wage': 40000.0,
            'basic_salary': 30000.0,
            'da': 5000.0,
        })

    def test_01_joining_date_resolution(self):
        """Test resolving original joining date from employee/contract."""
        joining_date = self.data_service._resolve_joining_date(self.employee, self.contract)
        self.assertEqual(joining_date, Date.from_string('2018-01-01'))

    def test_02_separation_date_resolution(self):
        """Test resolving separation date with fallback hierarchy."""
        sep_date = self.data_service._resolve_separation_date(
            self.employee, self.contract, explicit_date='2024-03-31'
        )
        self.assertEqual(sep_date, Date.from_string('2024-03-31'))

    def test_03_completed_service_calculation(self):
        """Test statutory service duration calculation (6 years 3 months = 6 completed years)."""
        joining = Date.from_string('2018-01-01')
        separation = Date.from_string('2024-04-15')
        duration = self.data_service._calculate_service_duration(joining, separation)
        self.assertEqual(duration['total_years'], 6)
        self.assertEqual(duration['remaining_months'], 3)
        self.assertEqual(duration['completed_years'], 6)

    def test_04_last_drawn_salary_retrieval(self):
        """Test last drawn Basic + DA component retrieval."""
        salary = self.data_service._retrieve_last_drawn_salary(self.employee, self.contract)
        self.assertEqual(salary['basic'], 30000.0)
        self.assertEqual(salary['da'], 5000.0)
        self.assertEqual(salary['wage_base'], 35000.0)

    def test_05_rule_parameters_resolution(self):
        """Test resolving statutory gratuity parameters via lookup engine."""
        params = self.data_service._resolve_rule_parameters(Date.today())
        self.assertEqual(params['days_multiplier'], 15.0)
        self.assertEqual(params['month_divisor'], 26.0)
        self.assertEqual(params['min_service_years'], 5.0)
        self.assertEqual(params['statutory_ceiling'], 2000000.0)

    def test_06_prepare_calculation_data_dto(self):
        """Test complete data preparation returning structured DTO object."""
        dto = self.data_service.prepare_calculation_data(
            employee=self.employee,
            contract=self.contract,
            separation_date='2024-03-31'
        )
        self.assertEqual(dto.employee_id, self.employee.id)
        self.assertEqual(dto.completed_years, 6)
        self.assertEqual(dto.last_drawn_basic, 30000.0)
        self.assertEqual(dto.last_drawn_da, 5000.0)
        self.assertEqual(dto.wage_base, 35000.0)
        self.assertEqual(dto.days_multiplier, 15.0)
        self.assertEqual(dto.month_divisor, 26.0)
        self.assertEqual(dto.statutory_ceiling, 2000000.0)
        
        dto_dict = dto.to_dict()
        self.assertIsInstance(dto_dict, dict)
        self.assertEqual(dto_dict['wage_base'], 35000.0)
