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
    for v in env['hr.version'].search([], limit=5):
        print(f"Contract {v.id}: {v.employee_id.name} | wage={v.wage} | basic={v.basic_salary} | HRA={v.hra} | DA={v.da} | pay_by_att={v.pay_by_attendance}")
