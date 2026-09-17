import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID

config_file = r"C:\Program Files\Odoo 19.0.20260717\server\odoo.conf"
odoo.tools.config.parse_config(['-c', config_file, '-d', 'RevisedPayroll'])
from odoo.modules.registry import Registry
registry = Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    Version = env['hr.version']
    for name, f in Version._fields.items():
        if f.type == 'boolean':
            print(f"hr.version boolean field: {name} ({f.string})")
            
    Employee = env['hr.employee']
    print("\n--- hr.employee booleans ---")
    for name, f in Employee._fields.items():
        if f.type == 'boolean' and any(k in name for k in ('pf', 'epf', 'wage', 'attend', 'day', 'per', 'basic', 'calc', 'stat')):
            print(f"hr.employee boolean field: {name} ({f.string})")
