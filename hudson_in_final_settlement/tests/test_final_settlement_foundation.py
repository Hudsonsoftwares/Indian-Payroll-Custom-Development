# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.fields import Date


class TestFinalSettlementFoundation(TransactionCase):

    def setUp(self):
        super(TestFinalSettlementFoundation, self).setUp()
        self.company = self.env['res.company'].create({
            'name': 'Final Settlement Test Company'
        })
        self.employee = self.env['hr.employee'].create({
            'name': 'Final Settlement Exiting Employee',
            'company_id': self.company.id,
            'first_contract_date': Date.from_string('2019-01-01'),
        })

    def test_01_final_settlement_creation_and_sequence(self):
        """Test master record creation and auto sequence generation."""
        settlement = self.env['final.settlement'].create({
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'exit_reason': 'resignation',
            'last_working_day': Date.from_string('2026-03-31'),
            'settlement_date': Date.from_string('2026-03-31'),
        })
        self.assertTrue(settlement.name.startswith('FSET/'))
        self.assertEqual(settlement.state, 'draft')
        self.assertEqual(settlement.employee_id, self.employee)
        self.assertEqual(settlement.company_id, self.company)

    def test_02_optional_resignation_linkage(self):
        """Test optional linked resignation request field."""
        resignation = self.env['hr.resignation'].create({
            'employee_id': self.employee.id,
            'resignation_type': 'resignation',
            'joined_date': Date.from_string('2019-01-01'),
            'expected_revealing_date': Date.from_string('2026-03-31'),
            'reason': 'Career advancement',
        })
        settlement = self.env['final.settlement'].create({
            'employee_id': self.employee.id,
            'resignation_id': resignation.id,
            'last_working_day': Date.from_string('2026-03-31'),
        })
        self.assertEqual(settlement.resignation_id, resignation)
        self.assertEqual(settlement.employee_id, self.employee)

    def test_03_status_workflow_transitions(self):
        """Test status workflow field values."""
        settlement = self.env['final.settlement'].create({
            'employee_id': self.employee.id,
            'last_working_day': Date.from_string('2026-03-31'),
        })
        self.assertEqual(settlement.state, 'draft')

        settlement.write({'state': 'under_review'})
        self.assertEqual(settlement.state, 'under_review')

        settlement.write({'state': 'approved'})
        self.assertEqual(settlement.state, 'approved')

        settlement.write({'state': 'paid'})
        self.assertEqual(settlement.state, 'paid')
