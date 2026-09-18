# -*- coding: utf-8 -*-
import sys
from datetime import date

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
    from odoo.addons.hudson_in_payroll.services.professional_tax.pt_period_config_service import PTPeriodScheduleService
    from odoo.addons.hudson_in_payroll.services.professional_tax.professional_tax_service import ProfessionalTaxService

    sched_service = PTPeriodScheduleService(env)
    pt_service = ProfessionalTaxService(env)
    sched_4 = env['pt.period.schedule'].browse(4)
    print(f"Direct Browse Schedule 4: ID {sched_4.id}, Name: {sched_4.name}, State: {sched_4.state_id.name} (ID: {sched_4.state_id.id}), Company: {sched_4.company_id}")
    ap_state = sched_4.state_id
    sched = sched_service.resolve_schedule(ap_state, company=sched_4.company_id or env.company, eval_date='2026-05-31')
    print(f"Resolved AP Schedule: {sched}")
    print(f"  Periodicity: {sched.periodicity}")
    print(f"  Window Start: {sched.window_start_month}, Window End: {sched.window_end_month}")
    print(f"  Strategy: {sched.deduction_strategy}, Dist Method: {sched.distribution_method}")

    assert sched.periodicity == 'monthly'
    assert not sched.window_start_month
    assert not sched.window_end_month
    assert sched.deduction_strategy == 'every_payroll'
    assert sched.distribution_method == 'full_amount'

    start_d, end_d = sched_service.resolve_period_window(sched, eval_date='2026-05-31')
    print(f"Resolved Window for 2026-05-31: {start_d} to {end_d}")
    assert start_d == date(2026, 5, 1)
    assert end_d == date(2026, 5, 31)

    # Test PT calculation for AP with Gross = 25000
    emp = env['hr.employee'].search([], limit=1)
    pt_res = pt_service.compute_pt(
        employee=emp,
        salary=25000.0,
        eval_date='2026-05-31',
        company=sched_4.company_id,
        state=ap_state
    )
    pt_val = pt_res.amount
    print(f"AP Monthly PT for Rs. 25,000 in May 2026: INR {pt_val}")
    assert pt_val == 200.0, f"Expected 200.0, got {pt_val}"

    print("ALL MONTHLY SCHEDULE CHECKS PASSED PERFECTLY!")
