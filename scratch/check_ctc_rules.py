import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    rules = env['hr.salary.rule'].search([('hds_in_contributes_to_employer_cost', '=', True)])
    for r in rules:
        print(f"Rule: code={r.code}, name={r.name}, struct={r.struct_id.name if r.struct_id else 'None'}, select={r.amount_select}")
