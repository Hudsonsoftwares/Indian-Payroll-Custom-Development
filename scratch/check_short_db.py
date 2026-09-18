import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
from odoo import api, SUPERUSER_ID

config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
registry = Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    r = env['hr.salary.rule'].search([('code', '=', 'SHORT')], limit=1)
    print("SHORT rule:", r.name, r.sequence)
    print(r.amount_python_compute)
    print("=" * 40)
    u = env['hr.salary.rule'].search([('code', '=', 'UNPAID')], limit=1)
    print("UNPAID rule:", u.name, u.sequence)
    print(u.amount_python_compute)
    print("=" * 40)
    net = env['hr.salary.rule'].search([('code', '=', 'NET')], limit=1)
    print("NET rule:", net.name, net.sequence)
    print(net.amount_python_compute)
