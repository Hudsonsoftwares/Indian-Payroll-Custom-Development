import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']

    emp1 = Employee.new({'basic_salary': 10000.0})
    print("emp with basic_salary=10000, _get_gross_wage():", emp1._get_gross_wage())

    emp2 = Employee.new({'wage': 10000.0})
    print("emp with wage=10000, _get_gross_wage():", emp2._get_gross_wage())

    emp3 = Employee.new({'basic_salary': 5000.0, 'da': 5000.0})
    print("emp with basic=5000, da=5000, _get_gross_wage():", emp3._get_gross_wage())
