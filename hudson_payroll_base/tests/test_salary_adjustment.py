# -*- coding: utf-8 -*-
from datetime import date
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestSalaryAdjustment(TransactionCase):
    """
    Test suite for Salary Adjustment in Hudson Payroll Base.
    Completely country-independent and localization-agnostic.
    """

    def setUp(self):
        super().setUp()
        self.SalaryAdjustment = self.env['hr.salary.adjustment']
        self.SalaryAdjWizard = self.env['hr.salary.adjustment.wizard']
        self.Payslip = self.env['hr.payslip']
        self.Employee = self.env['hr.employee']
        self.Contract = self.env['hr.version']
        self.InputType = self.env['hr.payslip.input.type']
        self.Company = self.env['res.company']

        self.company = self.env.company

        # Ensure base structure exists
        self.structure = self.env.ref('hudson_payroll_base.structure_base', raise_if_not_found=False)
        if not self.structure:
            self.structure = self.env['hr.payroll.structure'].search([], limit=1)

        # Global, country-independent input types (country_id = False)
        self.input_type_child_support = self.InputType.search([('code', '=', 'CHILD_SUPPORT')], limit=1)
        if not self.input_type_child_support:
            self.input_type_child_support = self.InputType.create({
                'name': 'Child Support',
                'code': 'CHILD_SUPPORT',
                'country_id': False,
            })

        self.input_type_deduction = self.InputType.search([('code', '=', 'DEDUCTION')], limit=1)
        if not self.input_type_deduction:
            self.input_type_deduction = self.InputType.create({
                'name': 'Deduction',
                'code': 'DEDUCTION',
                'country_id': False,
            })

        self.input_type_reimbursement = self.InputType.search([('code', '=', 'REIMBURSEMENT')], limit=1)
        if not self.input_type_reimbursement:
            self.input_type_reimbursement = self.InputType.create({
                'name': 'Reimbursement',
                'code': 'REIMBURSEMENT',
                'country_id': False,
            })

        # Test employees (Generic / Country-agnostic)
        self.employee_1 = self.Employee.create({
            'name': 'Alex Morgan',
            'company_id': self.company.id,
        })
        self.employee_2 = self.Employee.create({
            'name': 'Jordan Lee',
            'company_id': self.company.id,
        })

        # Setup contracts
        if self.employee_1.version_id:
            self.contract_1 = self.employee_1.version_id
            self.contract_1.write({
                'wage': 50000.0,
                'basic_salary': 25000.0,
                'struct_id': self.structure.id if self.structure else False,
                'contract_date_start': date(2026, 1, 1),
            })
        else:
            self.contract_1 = self.Contract.create({
                'name': 'Contract - Alex Morgan',
                'employee_id': self.employee_1.id,
                'company_id': self.company.id,
                'wage': 50000.0,
                'basic_salary': 25000.0,
                'struct_id': self.structure.id if self.structure else False,
                'contract_date_start': date(2026, 1, 1),
            })
            self.employee_1.version_id = self.contract_1

        if self.employee_2.version_id:
            self.contract_2 = self.employee_2.version_id
            self.contract_2.write({
                'wage': 40000.0,
                'basic_salary': 20000.0,
                'struct_id': self.structure.id if self.structure else False,
                'contract_date_start': date(2026, 1, 1),
            })
        else:
            self.contract_2 = self.Contract.create({
                'name': 'Contract - Jordan Lee',
                'employee_id': self.employee_2.id,
                'company_id': self.company.id,
                'wage': 40000.0,
                'basic_salary': 20000.0,
                'struct_id': self.structure.id if self.structure else False,
                'contract_date_start': date(2026, 1, 1),
            })
            self.employee_2.version_id = self.contract_2

    def test_01_one_time_adjustment_sync_and_completion(self):
        """Test one-time adjustment syncs into payslip inputs and auto-completes on slip confirmation."""
        adj = self.SalaryAdjustment.create({
            'employee_id': self.employee_1.id,
            'input_type_id': self.input_type_child_support.id,
            'amount': 5000.0,
            'duration': 'one_time',
            'date_start': date(2026, 9, 1),
            'note': 'Court Ordered Child Support',
        })
        self.assertEqual(adj.state, 'running')

        slip = self.Payslip.create({
            'name': 'Payslip Sep 2026',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        slip.action_compute_sheet()

        # Check input line created
        input_line = slip.input_line_ids.filtered(lambda l: l.adjustment_id == adj)
        self.assertTrue(input_line, "Payslip should have an input line linked to the adjustment")
        self.assertEqual(input_line.amount, 5000.0)
        self.assertEqual(input_line.code, 'CHILD_SUPPORT')

        # Confirm payslip
        slip.action_payslip_done()
        self.assertEqual(slip.state, 'done')
        self.assertEqual(adj.state, 'done', "One-time adjustment should be marked done after payslip confirmation")

    def test_02_limited_adjustment_date_boundary(self):
        """Test limited duration adjustment applies within date range and excludes outside."""
        adj = self.SalaryAdjustment.create({
            'employee_id': self.employee_1.id,
            'input_type_id': self.input_type_reimbursement.id,
            'amount': 2500.0,
            'duration': 'limited',
            'date_start': date(2026, 8, 1),
            'date_end': date(2026, 9, 30),
            'note': 'Internet Reimbursement Q3',
        })

        # Payslip within range (Sep 2026)
        slip_sep = self.Payslip.create({
            'name': 'Payslip Sep 2026',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        slip_sep.action_compute_sheet()
        self.assertTrue(slip_sep.input_line_ids.filtered(lambda l: l.adjustment_id == adj))

        # Payslip outside range (Oct 2026)
        slip_oct = self.Payslip.create({
            'name': 'Payslip Oct 2026',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 10, 1),
            'date_to': date(2026, 10, 31),
        })
        slip_oct.action_compute_sheet()
        self.assertFalse(slip_oct.input_line_ids.filtered(lambda l: l.adjustment_id == adj))

    def test_03_limited_adjustment_with_until_amount_cap(self):
        """Test until_amount capping behavior across multiple payslips."""
        adj = self.SalaryAdjustment.create({
            'employee_id': self.employee_1.id,
            'input_type_id': self.input_type_deduction.id,
            'amount': 3000.0,
            'duration': 'limited',
            'date_start': date(2026, 1, 1),
            'date_end': date(2026, 12, 31),
            'until_amount': 5000.0,
            'note': 'Equipment Advance Recovery',
        })

        # Period 1: Sep 2026 -> should take full 3000
        slip_1 = self.Payslip.create({
            'name': 'Slip Sep',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        slip_1.action_compute_sheet()
        inp_1 = slip_1.input_line_ids.filtered(lambda l: l.adjustment_id == adj)
        self.assertEqual(inp_1.amount, 3000.0)
        slip_1.action_payslip_done()

        # Period 2: Oct 2026 -> should cap remaining at 2000 (5000 - 3000)
        slip_2 = self.Payslip.create({
            'name': 'Slip Oct',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 10, 1),
            'date_to': date(2026, 10, 31),
        })
        slip_2.action_compute_sheet()
        inp_2 = slip_2.input_line_ids.filtered(lambda l: l.adjustment_id == adj)
        self.assertEqual(inp_2.amount, 2000.0, "Input amount must be capped at remaining until_amount")
        slip_2.action_payslip_done()
        self.assertEqual(adj.state, 'done', "Adjustment should be done once until_amount cap is reached")

    def test_04_unlimited_adjustment(self):
        """Test unlimited adjustment persists indefinitely across payslips."""
        adj = self.SalaryAdjustment.create({
            'employee_id': self.employee_1.id,
            'input_type_id': self.input_type_reimbursement.id,
            'amount': 1200.0,
            'duration': 'unlimited',
            'date_start': date(2026, 1, 1),
            'note': 'Monthly Mobile Allowance Input',
        })

        for month in (8, 9, 10):
            slip = self.Payslip.create({
                'name': f'Slip {month}',
                'employee_id': self.employee_1.id,
                'contract_id': self.contract_1.id,
                'struct_id': self.structure.id if self.structure else False,
                'date_from': date(2026, month, 1),
                'date_to': date(2026, month, 28),
            })
            slip.action_compute_sheet()
            inp = slip.input_line_ids.filtered(lambda l: l.adjustment_id == adj)
            self.assertTrue(inp)
            self.assertEqual(inp.amount, 1200.0)
            slip.action_payslip_done()
            self.assertEqual(adj.state, 'running', "Unlimited adjustment stays running")

    def test_05_multi_employee_wizard(self):
        """Test batch creation wizard creates adjustments for multiple employees."""
        wizard = self.SalaryAdjWizard.create({
            'employee_ids': [(6, 0, [self.employee_1.id, self.employee_2.id])],
            'input_type_id': self.input_type_reimbursement.id,
            'amount': 4500.0,
            'duration': 'one_time',
            'date_start': date(2026, 9, 15),
            'note': 'Company Performance Bonus Input',
        })
        wizard.action_create_adjustments()

        adj_1 = self.SalaryAdjustment.search([
            ('employee_id', '=', self.employee_1.id),
            ('note', '=', 'Company Performance Bonus Input'),
        ])
        adj_2 = self.SalaryAdjustment.search([
            ('employee_id', '=', self.employee_2.id),
            ('note', '=', 'Company Performance Bonus Input'),
        ])
        self.assertEqual(len(adj_1), 1)
        self.assertEqual(len(adj_2), 1)
        self.assertEqual(adj_1.amount, 4500.0)
        self.assertEqual(adj_2.amount, 4500.0)

    def test_06_negative_value_adjustment(self):
        """Test negative value flag sets negative amount in payslip input."""
        adj = self.SalaryAdjustment.create({
            'employee_id': self.employee_1.id,
            'input_type_id': self.input_type_deduction.id,
            'amount': 1500.0,
            'negative': True,
            'duration': 'one_time',
            'date_start': date(2026, 9, 1),
        })

        slip = self.Payslip.create({
            'name': 'Slip Negative Value',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        slip.action_compute_sheet()
        inp = slip.input_line_ids.filtered(lambda l: l.adjustment_id == adj)
        self.assertEqual(inp.amount, -1500.0, "Negative flag should pass negative amount")

    def test_07_idempotent_recompute(self):
        """Test recomputing sheet multiple times does not duplicate input lines."""
        adj = self.SalaryAdjustment.create({
            'employee_id': self.employee_1.id,
            'input_type_id': self.input_type_child_support.id,
            'amount': 7500.0,
            'duration': 'one_time',
            'date_start': date(2026, 9, 1),
        })

        slip = self.Payslip.create({
            'name': 'Slip Idempotency',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        slip.action_compute_sheet()
        lines_count_first = len(slip.input_line_ids.filtered(lambda l: l.adjustment_id == adj))
        self.assertEqual(lines_count_first, 1)

        # Recompute sheet 2 more times
        slip.action_compute_sheet()
        slip.action_compute_sheet()
        lines_count_after = len(slip.input_line_ids.filtered(lambda l: l.adjustment_id == adj))
        self.assertEqual(lines_count_after, 1, "Recomputing sheet should never duplicate adjustment inputs")

    def test_08_manual_input_preservation(self):
        """Test that manually entered inputs are preserved and not overwritten."""
        slip = self.Payslip.create({
            'name': 'Slip Manual Input',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        # Add manual input
        manual_inp = self.env['hr.payslip.input'].create({
            'payslip_id': slip.id,
            'input_type_id': self.input_type_reimbursement.id,
            'code': 'REIMBURSEMENT',
            'name': 'Manual Custom Travel Bill',
            'amount': 999.0,
        })

        # Add separate adjustment with different code
        adj = self.SalaryAdjustment.create({
            'employee_id': self.employee_1.id,
            'input_type_id': self.input_type_child_support.id,
            'amount': 3000.0,
            'duration': 'one_time',
            'date_start': date(2026, 9, 1),
        })

        slip.action_compute_sheet()
        # Verify manual input still exists with amount 999.0
        self.assertTrue(manual_inp.exists())
        self.assertEqual(manual_inp.amount, 999.0, "Manual input amount must not be altered")
        self.assertFalse(manual_inp.adjustment_id, "Manual input should remain unlinked")

    def test_09_payslip_cancel_reverts_adjustment_status(self):
        """Test cancelling a payslip reverts one-time adjustment status back to running."""
        adj = self.SalaryAdjustment.create({
            'employee_id': self.employee_1.id,
            'input_type_id': self.input_type_child_support.id,
            'amount': 5000.0,
            'duration': 'one_time',
            'date_start': date(2026, 9, 1),
        })

        slip = self.Payslip.create({
            'name': 'Slip to Cancel',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        slip.action_compute_sheet()
        slip.action_payslip_done()
        self.assertEqual(adj.state, 'done')

        # Cancel payslip
        slip.action_payslip_cancel()
        self.assertEqual(slip.state, 'cancel')
        self.assertEqual(adj.state, 'running', "Cancelling payslip should revert adjustment to running")

    def test_10_validation_constraints(self):
        """Test validation constraints on dates and amount."""
        with self.assertRaises(ValidationError):
            self.SalaryAdjustment.create({
                'employee_id': self.employee_1.id,
                'input_type_id': self.input_type_child_support.id,
                'amount': 0.0,
                'duration': 'one_time',
                'date_start': date(2026, 9, 1),
            })

        with self.assertRaises(ValidationError):
            self.SalaryAdjustment.create({
                'employee_id': self.employee_1.id,
                'input_type_id': self.input_type_child_support.id,
                'amount': 1000.0,
                'duration': 'limited',
                'date_start': date(2026, 9, 1),
                'date_end': False,
            })

        with self.assertRaises(ValidationError):
            self.SalaryAdjustment.create({
                'employee_id': self.employee_1.id,
                'input_type_id': self.input_type_child_support.id,
                'amount': 1000.0,
                'duration': 'limited',
                'date_start': date(2026, 9, 15),
                'date_end': date(2026, 9, 1),
            })

    def test_11_smart_button_and_traceability(self):
        """Test smart button action_view_payslips and applied count."""
        adj = self.SalaryAdjustment.create({
            'employee_id': self.employee_1.id,
            'input_type_id': self.input_type_child_support.id,
            'amount': 2000.0,
            'duration': 'unlimited',
            'date_start': date(2026, 9, 1),
        })

        slip = self.Payslip.create({
            'name': 'Slip Traceability',
            'employee_id': self.employee_1.id,
            'contract_id': self.contract_1.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        slip.action_compute_sheet()

        self.assertEqual(adj.applied_count, 1)
        action = adj.action_view_payslips()
        self.assertEqual(action['res_model'], 'hr.payslip')
        self.assertEqual(action['res_id'], slip.id)

    def test_12_country_independence_multinational(self):
        """Test that salary adjustment functions in multinational and non-Indian companies without any statutory dependency."""
        country_ae = self.env.ref('base.ae', raise_if_not_found=False) or self.env['res.country'].search([('code', '=', 'AE')], limit=1)
        company_ae = self.Company.search([('name', '=', 'Global Horizon FZE')], limit=1)
        if not company_ae:
            partner_ae = self.env['res.partner'].create({'name': 'Global Horizon FZE Partner', 'is_company': True})
            company_ae = self.Company.create({
                'name': 'Global Horizon FZE',
                'partner_id': partner_ae.id,
                'country_id': country_ae.id if country_ae else False,
            })
        else:
            if country_ae and company_ae.country_id != country_ae:
                company_ae.country_id = country_ae.id
        partner_emp = self.env['res.partner'].create({'name': 'Fatima Al-Nuaimi Partner'})
        emp_ae = self.Employee.create({
            'name': 'Fatima Al-Nuaimi',
            'work_contact_id': partner_emp.id,
            'company_id': company_ae.id,
        })
        if emp_ae.version_id:
            contract_ae = emp_ae.version_id
            contract_ae.write({
                'wage': 18000.0,
                'company_id': company_ae.id,
                'struct_id': self.structure.id if self.structure else False,
                'contract_date_start': date(2026, 1, 1),
            })
        else:
            contract_ae = self.Contract.create({
                'name': 'Contract - Fatima',
                'employee_id': emp_ae.id,
                'company_id': company_ae.id,
                'wage': 18000.0,
                'struct_id': self.structure.id if self.structure else False,
                'contract_date_start': date(2026, 1, 1),
            })
            emp_ae.version_id = contract_ae

        # Create salary adjustment for UAE company employee
        adj_ae = self.SalaryAdjustment.create({
            'employee_id': emp_ae.id,
            'company_id': company_ae.id,
            'input_type_id': self.input_type_reimbursement.id,
            'amount': 1500.0,
            'duration': 'one_time',
            'date_start': date(2026, 9, 1),
            'note': 'Relocation Expense',
        })
        self.assertEqual(adj_ae.company_id.id, company_ae.id)
        if country_ae:
            self.assertEqual(adj_ae.country_id.id, country_ae.id)

        # Generate and compute payslip for UAE employee
        slip_ae = self.Payslip.create({
            'name': 'Payslip UAE - Sep 2026',
            'employee_id': emp_ae.id,
            'contract_id': contract_ae.id,
            'company_id': company_ae.id,
            'struct_id': self.structure.id if self.structure else False,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 30),
        })
        slip_ae.action_compute_sheet()

        inp_ae = slip_ae.input_line_ids.filtered(lambda l: l.adjustment_id == adj_ae)
        self.assertTrue(inp_ae, "Salary adjustment must sync for any country's company and employee")
        self.assertEqual(inp_ae.amount, 1500.0)

        # Confirm payslip
        slip_ae.action_payslip_done()
        self.assertEqual(adj_ae.state, 'done', "Adjustment must complete on confirmation regardless of country")
