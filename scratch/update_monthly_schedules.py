# -*- coding: utf-8 -*-
import sys
import os

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
    schedules = env['pt.period.schedule'].search([('periodicity', '=', 'monthly')])
    print(f"Found {len(schedules)} monthly schedules.")
    for s in schedules:
        print(f"Before: ID {s.id}, Name: {s.name}, Window: {s.window_start_month}-{s.window_end_month}, Strategy: {s.deduction_strategy}, Dist: {s.distribution_method}")
        s.write({
            'window_start_month': False,
            'window_end_month': False,
            'deduction_month': False,
            'deduction_strategy': 'every_payroll',
            'distribution_method': 'full_amount',
        })
        s._compute_name()
        print(f"After: ID {s.id}, Name: {s.name}, Window: {s.window_start_month}-{s.window_end_month}, Strategy: {s.deduction_strategy}, Dist: {s.distribution_method}")
    cr.commit()
print("Monthly schedules updated successfully!")
