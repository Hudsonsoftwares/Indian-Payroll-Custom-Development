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
    emps = env['hr.employee'].search([])
    for e in emps:
        pt_app = getattr(e, 'hds_in_pt_applicable', 'FIELD_NOT_FOUND')
        print(f"Emp ID {e.id}: {e.name}, PT Applicable: {pt_app}")
