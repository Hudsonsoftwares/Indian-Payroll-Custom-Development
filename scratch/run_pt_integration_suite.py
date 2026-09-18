# -*- coding: utf-8 -*-
import sys
import unittest

SERVER_PATH = r"C:\Program Files\Odoo 19.0.20260717\server"
CONF_PATH = r"C:\Program Files\Odoo 19.0.20260717\server\odoo.conf"
DB_NAME = "RevisedPayroll"

if SERVER_PATH not in sys.path:
    sys.path.insert(0, SERVER_PATH)

import odoo
from odoo import api, SUPERUSER_ID
from odoo.modules.registry import Registry

odoo.tools.config.parse_config(['-c', CONF_PATH, '-d', DB_NAME])
registry = Registry(DB_NAME)

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.hudson_in_payroll.tests.test_pt_payslip_integration import TestPTPayslipIntegration

    suite = unittest.TestSuite()
    for m in [
        'test_01_single_record_enforcement',
        'test_02_successful_payslip_delegation_january',
        'test_03_override_month_payslip_delegation_february',
        'test_04_disabled_company_payslip_delegation',
        'test_05_disabled_employee_payslip_delegation',
    ]:
        test_case = TestPTPayslipIntegration(m)
        test_case.env = env
        test_case.cr = cr
        suite.addTest(test_case)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    cr.rollback()
    assert result.wasSuccessful(), "Tests failed!"
    print("ALL 5 INTEGRATION TESTS (INCLUDING test_05_disabled_employee_payslip_delegation) PASSED!")
