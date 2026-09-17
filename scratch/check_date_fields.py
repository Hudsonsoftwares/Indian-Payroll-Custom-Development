import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']
    date_fields = [f for f in Employee._fields if any(x in f for x in ['date', 'join', 'start', 'version', 'contract'])]
    print("Employee relevant fields:", sorted(date_fields))
    if 'hr.version' in env:
        v_fields = [f for f in env['hr.version']._fields if any(x in f for x in ['date', 'join', 'start'])]
        print("hr.version fields:", sorted(v_fields))
    if 'hr.contract' in env:
        c_fields = [f for f in env['hr.contract']._fields if any(x in f for x in ['date', 'join', 'start'])]
        print("hr.contract fields:", sorted(c_fields))
