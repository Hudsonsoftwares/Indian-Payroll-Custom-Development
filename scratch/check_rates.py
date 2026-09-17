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
    admin = env['hr.employee'].search([('name', 'ilike', 'Administrator')], limit=1)
    contract = env['hr.version'].search([('employee_id', '=', admin.id)], limit=1)
    print("Contract Wage:", contract.wage)
    print("Basic Salary:", contract.basic_salary)
    print("DA:", contract.da)
    print("HRA:", contract.hra)
    print("Fixed Allowance:", contract.fixed_allowance)
    print("Pay by Attendance:", contract.pay_by_attendance)
    print("Shortage Rate:", contract.get_period_shortage_rate('2026-10-01', '2026-10-31'))
    print("Day Rate:", contract.get_period_day_rate('2026-10-01', '2026-10-31'))
