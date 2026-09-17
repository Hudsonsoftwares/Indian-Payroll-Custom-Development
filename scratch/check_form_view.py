import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    # Let's inspect hr.employee view arch to see what field the user sees as "Joining Date" or "Start Date"
    view = env['hr.employee'].get_view(view_type='form')
    arch = view.get('arch', '')
    for line in arch.split('\n'):
        if any(x in line.lower() for x in ['join', 'date_start', 'contract_date', 'date_version']):
            print(line.strip())
