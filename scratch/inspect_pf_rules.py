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
    rules = env['hr.salary.rule'].search([('code', 'in', ('PF', 'EPF', 'PF_EE', 'PF_ER', 'PF_WAGE', 'BASIC', 'DA'))])
    for r in rules:
        print(f"Rule: {r.code} ({r.name}) | Struct: {r.struct_id.name} | Select: {r.amount_select}")
        if r.amount_select == 'code':
            print(f"  Code:\n{r.amount_python_compute}")
        elif r.amount_select == 'percentage':
            print(f"  Percentage: {r.amount_percentage}% of {r.amount_percentage_base}")
