# -*- coding: utf-8 -*-
import sys

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
    from odoo.addons.hudson_in_payroll.services.professional_tax.professional_tax_service import ProfessionalTaxService
    from odoo.addons.hudson_in_payroll.services.professional_tax.pt_validator import PTValidator

    pt_service = ProfessionalTaxService(env)
    validator = PTValidator(env)

    ap_state = env['res.country.state'].search([('country_id.code', '=', 'IN'), ('code', '=', 'AP')], limit=1)
    company = env.company

    # Pick an employee
    emp = env['hr.employee'].search([('active', '=', True)], limit=1)
    print(f"Testing with employee: {emp.name} (ID: {emp.id})")

    # 1. Test when PT Applicable is True
    emp.hds_in_pt_applicable = True
    print("\n--- CASE 1: PT Applicable = TRUE ---")
    val_res = validator.validate(employee=emp, salary=25000.0, state=ap_state, company=company, eval_date='2026-05-31')
    print(f"Validator Result: valid={val_res.is_valid}, status={val_res.validation_status}")
    assert val_res.is_valid is True

    pt_res = pt_service.compute_pt(employee=emp, salary=25000.0, state=ap_state, company=company, eval_date='2026-05-31')
    print(f"Service Result: amount={pt_res.amount}, valid={pt_res.is_valid}, status={pt_res.validation_status}")
    assert pt_res.amount == 200.0

    # Test Payslip method with localdict
    slip = env['hr.payslip'].new({'employee_id': emp.id, 'company_id': company.id})
    localdict = {'employee': emp, 'company': company, 'salary': 25000.0, 'gross_salary': 25000.0, 'categories': {'GROSS': 25000.0}}
    slip._get_statutory_context(localdict)
    slip_amount = slip.hds_in_compute_professional_tax()
    print(f"Payslip delegation amount when TRUE: {slip_amount}")
    assert slip_amount != 0.0

    # 2. Test when PT Applicable is False
    emp.hds_in_pt_applicable = False
    print("\n--- CASE 2: PT Applicable = FALSE ---")
    val_res_disabled = validator.validate(employee=emp, salary=25000.0, state=ap_state, company=company, eval_date='2026-05-31')
    print(f"Validator Result: valid={val_res_disabled.is_valid}, status={val_res_disabled.validation_status}")
    assert val_res_disabled.is_valid is False
    assert val_res_disabled.validation_status == 'DISABLED_EMPLOYEE'

    pt_res_disabled = pt_service.compute_pt(employee=emp, salary=25000.0, state=ap_state, company=company, eval_date='2026-05-31')
    print(f"Service Result: amount={pt_res_disabled.amount}, valid={pt_res_disabled.is_valid}, status={pt_res_disabled.validation_status}")
    assert pt_res_disabled.amount == 0.0
    assert pt_res_disabled.is_valid is False
    assert pt_res_disabled.validation_status == 'DISABLED_EMPLOYEE'

    slip_amount_disabled = slip.hds_in_compute_professional_tax()
    print(f"Payslip delegation amount when FALSE: {slip_amount_disabled}")
    assert slip_amount_disabled == 0.0

    # Reset back to True
    emp.hds_in_pt_applicable = True
    cr.rollback()

    print("\nALL PT APPLICABLE TOGGLE TESTS PASSED PERFECTLY!")
