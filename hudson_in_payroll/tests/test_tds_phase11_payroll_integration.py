# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields


class TestTdsPhase11PayrollIntegration(TransactionCase):

    def setUp(self):
        super(TestTdsPhase11PayrollIntegration, self).setUp()
        self.fy = self.env['tds.financial.year'].search([('code', '=', '2025-2026')], limit=1)
        if not self.fy:
            self.fy = self.env['tds.financial.year'].create({
                'name': 'Financial Year 2025-2026',
                'code': '2025-2026',
                'start_date': '2025-04-01',
                'end_date': '2026-03-31',
                'is_active': True,
            })

        self.regime_new = self.env['tds.tax.regime'].search([('code', '=', 'new')], limit=1)
        if not self.regime_new:
            self.regime_new = self.env['tds.tax.regime'].create({
                'name': 'New Tax Regime (Section 115BAC)',
                'code': 'new',
                'is_active': True,
            })

        self.employee = self.env['hr.employee'].create({
            'name': 'Phase 11 Payroll Integration Test Employee',
            'birthday': '1991-03-10',
        })

        contract_model = 'hr.contract' if 'hr.contract' in self.env else 'hr.version'
        contract_vals = {
            'name': 'Integration Test Contract',
            'employee_id': self.employee.id,
            'wage': 100000.0,
            'date_start': '2025-04-01',
        }
        if contract_model == 'hr.contract':
            contract_vals['state'] = 'open'
        self.contract = self.env[contract_model].create(contract_vals)
        if hasattr(self.employee, 'contract_id'):
            self.employee.contract_id = self.contract.id
        if hasattr(self.employee, 'version_id'):
            self.employee.version_id = self.contract.id

        self.env.company.write({'hds_in_tds_applicable': True})

        self.env['tds.employee.tax.regime'].create({
            'employee_id': self.employee.id,
            'financial_year_id': self.fy.id,
            'regime_id': self.regime_new.id,
        })

    def test_01_hr_payslip_hds_in_compute_tds(self):
        """Test hr.payslip model method hds_in_compute_tds() producing current month TDS."""
        payslip = self.env['hr.payslip'].create({
            'name': 'April 2025 Payslip Integration Test',
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'date_from': '2025-04-01',
            'date_to': '2025-04-30',
        })

        tds_amount = payslip.hds_in_compute_tds()
        # Annual Salary = 12,00,000, Std Ded = 75,000, Taxable = 11,25,000
        # Base Tax = 52,500, Cess = 2,100, Total Annual Tax = 54,600
        # Monthly TDS (April, 12 periods) = 54,600 / 12 = 4,550
        self.assertEqual(tds_amount, 4550.0)

    def test_02_payslip_compute_sheet_generates_tds_line(self):
        """Test full payslip compute_sheet() generating the HDS_IN_TDS salary rule line."""
        payslip = self.env['hr.payslip'].create({
            'name': 'April 2025 Full Payslip Test',
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'struct_id': self.env.ref('hudson_payroll_base.structure_base').id,
            'date_from': '2025-04-01',
            'date_to': '2025-04-30',
        })

        payslip.action_compute_sheet()
        tds_line = payslip.line_ids.filtered(lambda l: l.code == 'HDS_IN_TDS')
        self.assertTrue(tds_line)
        self.assertEqual(tds_line.total, 4550.0)

    def test_03_tds_disabled_when_company_tds_applicable_false(self):
        """When company TDS is disabled, TDS calculation returns 0.0 without requiring a Financial Year."""
        self.env.company.write({'hds_in_tds_applicable': False})
        payslip = self.env['hr.payslip'].create({
            'name': 'September 2026 Payslip Without TDS Test',
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'struct_id': self.env.ref('hudson_payroll_base.structure_base').id,
            'date_from': '2026-09-01',
            'date_to': '2026-09-30',
        })
        tds_amount = payslip.hds_in_compute_tds()
        self.assertEqual(tds_amount, 0.0)
        payslip.action_compute_sheet()
        tds_line = payslip.line_ids.filtered(lambda l: l.code == 'HDS_IN_TDS')
        self.assertTrue(tds_line)
        self.assertEqual(tds_line.total, 0.0)
