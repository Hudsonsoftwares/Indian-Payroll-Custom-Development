import sys
server_path = r"C:\Program Files\Odoo 19.0.20260717\server"
if server_path not in sys.path:
    sys.path.insert(0, server_path)

import odoo
from odoo import api
from odoo.tools import config
from odoo.modules.registry import Registry

config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
registry = Registry('RevisedPayroll')

with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    dashboards = env['hds.payroll.dashboard'].search([])
    for d in dashboards:
        d._compute_dashboard_metrics()
        d._compute_dashboard_html()
        print(f"Recomputed dashboard id={d.id}, name={d.name}, html length={len(d.dashboard_html or '')}")
    cr.commit()
    print("Dashboard recomputation committed successfully!")
