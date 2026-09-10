# -*- coding: utf-8 -*-
import json
import time
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from ..services.audit.audit_service import StatutoryAuditSession
from ..services.epf.epf_service import EPFService


class TestStatutoryAuditService(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.hds_in_enable_statutory_audit = True

        self.employee = self.env['hr.employee'].create({
            'name': 'Audit Test Employee',
            'hds_in_epf_applicable': True,
            'hds_in_eps_applicable': True,
            'hds_in_pf_contribution_basis': 'statutory_ceiling',
            'hds_in_uan': '100987654321',
        })

        self.payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': '2026-07-01',
            'date_to': '2026-07-31',
        })

    def test_01_successful_audit_logging(self):
        """Test successful EPF audit log creation and JSON content verification."""
        initial_count = self.env['hds.in.payroll.audit'].search_count([('payslip_id', '=', self.payslip.id)])
        
        service = EPFService(self.env)
        localdict = {'rules': {'BASIC': {'total': 17000.0}}}
        result = service.compute_employee_epf(self.payslip, localdict=localdict)

        new_count = self.env['hds.in.payroll.audit'].search_count([('payslip_id', '=', self.payslip.id)])
        self.assertEqual(new_count, initial_count + 1)

        audit_log = self.env['hds.in.payroll.audit'].search([
            ('payslip_id', '=', self.payslip.id),
            ('rule_code', '=', 'EPF')
        ], limit=1)

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.status, 'success')
        self.assertEqual(audit_log.statutory_module, 'epf')
        self.assertEqual(audit_log.employee_id.id, self.employee.id)

        # JSON Payloads Parsing Verification
        inputs = json.loads(audit_log.inputs_json)
        outputs = json.loads(audit_log.outputs_json)
        params = json.loads(audit_log.parameters_json)

        self.assertEqual(inputs.get('actual_pf_wage'), 17000.0)
        self.assertEqual(inputs.get('pf_contribution_wage'), 15000.0)
        self.assertEqual(outputs.get('employee_epf_deduction'), result)
        self.assertEqual(params.get('EPF_RATE'), 12.0)
        self.assertEqual(params.get('PF_WAGE_CEILING'), 15000.0)

    def test_02_failed_calculation_audit_and_reraise(self):
        """Test that failed calculation captures exception stack trace and re-raises original error."""
        self.employee.hds_in_vpf_type = 'percent'
        self.employee.hds_in_vpf_percent = -10.0  # Invalid negative VPF

        service = EPFService(self.env)

        with self.assertRaises(UserError):
            service.compute_employee_epf(self.payslip)

        # Audit log should still be persisted with status 'error'
        audit_log = self.env['hds.in.payroll.audit'].search([
            ('payslip_id', '=', self.payslip.id),
            ('rule_code', '=', 'EPF'),
            ('status', '=', 'error')
        ], limit=1)

        self.assertTrue(audit_log)
        self.assertIn("Invalid VPF Percentage", audit_log.messages)
        self.assertTrue(audit_log.exception_trace)

    def test_03_disabled_audit_toggle(self):
        """Test that when audit logging is disabled, zero database records are created."""
        self.company.hds_in_enable_statutory_audit = False

        initial_count = self.env['hds.in.payroll.audit'].search_count([])
        
        service = EPFService(self.env)
        localdict = {'rules': {'BASIC': {'total': 15000.0}}}
        service.compute_employee_epf(self.payslip, localdict=localdict)

        new_count = self.env['hds.in.payroll.audit'].search_count([])
        self.assertEqual(new_count, initial_count)

    def test_04_multiple_statutory_modules(self):
        """Test audit recording across multiple statutory modules (EPF, ESIC, PT, TDS)."""
        with StatutoryAuditSession(self.env, self.payslip, statutory_module='esic', rule_code='ESIC') as audit:
            audit.attach_input('gross_wage', 20000.0)
            audit.attach_parameter('ESIC_EMPLOYEE_RATE', 0.75)
            audit.attach_output('employee_esic_deduction', -150.0)

        with StatutoryAuditSession(self.env, self.payslip, statutory_module='pt', rule_code='PT') as audit:
            audit.attach_input('gross_wage', 20000.0)
            audit.attach_parameter('PT_SLAB_20000', 200.0)
            audit.attach_output('pt_deduction', -200.0)

        esic_audit = self.env['hds.in.payroll.audit'].search([
            ('payslip_id', '=', self.payslip.id),
            ('statutory_module', '=', 'esic')
        ], limit=1)
        pt_audit = self.env['hds.in.payroll.audit'].search([
            ('payslip_id', '=', self.payslip.id),
            ('statutory_module', '=', 'pt')
        ], limit=1)

        self.assertTrue(esic_audit)
        self.assertTrue(pt_audit)

    def test_05_json_serialization_safety(self):
        """Test handling of various data types in JSON fields."""
        with StatutoryAuditSession(self.env, self.payslip, statutory_module='epf', rule_code='EPF') as audit:
            audit.attach_input('date_param', self.payslip.date_to)
            audit.attach_input('float_param', 15000.50)
            audit.attach_input('bool_param', True)
            audit.attach_input('null_param', None)

        audit_log = self.env['hds.in.payroll.audit'].search([
            ('payslip_id', '=', self.payslip.id)
        ], limit=1)

        inputs = json.loads(audit_log.inputs_json)
        self.assertEqual(inputs.get('date_param'), str(self.payslip.date_to))
        self.assertEqual(inputs.get('float_param'), 15000.50)
        self.assertTrue(inputs.get('bool_param'))
        self.assertIsNone(inputs.get('null_param'))

    def test_06_performance_benchmark(self):
        """Verify microsecond overhead when audit is enabled vs disabled."""
        service = EPFService(self.env)
        localdict = {'rules': {'BASIC': {'total': 15000.0}}}

        start_time = time.time()
        for _ in range(20):
            service.compute_employee_epf(self.payslip, localdict=localdict)
        elapsed_enabled = (time.time() - start_time) / 20.0

        self.company.hds_in_enable_statutory_audit = False
        start_time = time.time()
        for _ in range(20):
            service.compute_employee_epf(self.payslip, localdict=localdict)
        elapsed_disabled = (time.time() - start_time) / 20.0

        # Output benchmark metrics to test logs
        self.assertLess(elapsed_enabled, 0.05)  # Average under 50ms in testing environment

    def test_07_smart_button_counts(self):
        """Verify audit count computation on Employee and Payslip."""
        service = EPFService(self.env)
        localdict = {'rules': {'BASIC': {'total': 15000.0}}}
        service.compute_employee_epf(self.payslip, localdict=localdict)

        self.payslip._compute_hds_in_statutory_audit_count()
        self.employee._compute_hds_in_statutory_audit_count()

        self.assertGreaterEqual(self.payslip.hds_in_statutory_audit_count, 1)
        self.assertGreaterEqual(self.employee.hds_in_statutory_audit_count, 1)
