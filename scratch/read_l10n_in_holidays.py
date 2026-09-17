import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID
import inspect

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
reg = odoo.modules.registry.Registry('RevisedPayroll')
with reg.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    m = env['l10n.in.hr.leave.optional.holiday']
    # Look at m._module and its class hierarchy
    for base in type(m).__mro__:
        if 'l10n_in' in getattr(base, '__module__', ''):
            print("Base class:", base, "Module:", base.__module__)
            try:
                print(inspect.getsource(base))
            except Exception as e:
                print("Could not get source:", e)
