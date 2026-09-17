import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    for c in env['res.company'].search([]):
        print(f"Company: id={c.id}, name={c.name}, country={c.country_id.code}, enable_lwf={getattr(c, 'hds_in_enable_lwf', None)}, lwf_state={getattr(c, 'hds_in_lwf_state_id', None)}")
