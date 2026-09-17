import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']
    print("State / location fields on hr.employee:")
    for f in sorted(Employee._fields.keys()):
        if any(x in f for x in ('state', 'locat', 'addr', 'work')):
            print(f"  {f}: {Employee._fields[f].type}")
