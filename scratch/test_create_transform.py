import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']

    # Test create with wage=10000, contract_date_start='2026-10-01', and hds_in_esic_applicable=False (from web form)
    emp_vals = {
        'name': 'Test Oct 1 Joiner 10k',
        'wage': 10000.0,
        'contract_date_start': '2026-10-01',
        'hds_in_esic_applicable': False,
    }
    gross = float(emp_vals.get('wage', 0.0))
    ceiling = 21000.0
    if 0 < gross <= ceiling and not emp_vals.get('hds_in_esic_applicable'):
        emp_vals['hds_in_esic_applicable'] = True
        emp_vals['hds_in_esic_ip_status'] = 'active'
        emp_vals['hds_in_esic_exit_reason'] = False

    print("Transformed vals:", emp_vals)
