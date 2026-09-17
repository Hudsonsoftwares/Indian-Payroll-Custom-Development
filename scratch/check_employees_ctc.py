import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']
    emp = Employee.search([('wage', '>', 0)], limit=1)

    # Let's inspect Administrator (or any employee)
    for e in Employee.search([('wage', '>', 0)]):
        print(f"Employee {e.name} (id={e.id}): wage={e.wage}, basic={e.basic_salary}, epf={e.hds_in_epf_applicable}, esic={e.hds_in_esic_applicable}, lwf={e.hds_in_lwf_applicable}, ctc_m={e.hds_in_employer_cost_monthly}")
