import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    for r in env['lwf.state.rate'].search([]):
        print(f"LWF State Rate: State={r.state_id.name} ({r.state_id.code}), emp={r.emp_contribution}, empl={r.empl_contribution}")
    for c in env['res.company'].search([]):
        print(f"Company: {c.name}, hds_in_enable_lwf={getattr(c, 'hds_in_enable_lwf', None)}")
