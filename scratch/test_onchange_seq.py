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

    field_onchange = Employee._onchange_methods
    print("Methods triggered on hds_in_esic_applicable:")
    for m in field_onchange.get('hds_in_esic_applicable', []):
        print(" ", m)

    # Let's test onchange manually step-by-step
    rec = Employee.new({
        'name': emp.name,
        'wage': emp.wage,
        'basic_salary': emp.basic_salary,
        'hds_in_epf_applicable': True,
        'hds_in_esic_applicable': True,
        'hds_in_lwf_applicable': True,
    }, origin=emp)

    print("\nInitial cost on new record:", rec.hds_in_employer_cost_monthly)
    rec.hds_in_esic_applicable = False
    rec._onchange_esic_applicable()
    rec._onchange_ctc_and_statutory_inputs()
    print("After turning ESIC False:", rec.hds_in_employer_cost_monthly)

    rec.hds_in_esic_applicable = True
    rec._onchange_esic_applicable()
    rec._onchange_ctc_and_statutory_inputs()
    print("After turning ESIC True:", rec.hds_in_employer_cost_monthly)
