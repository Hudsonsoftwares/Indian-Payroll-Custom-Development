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

    rec = Employee.new({
        'name': emp.name,
        'wage': 20000.0,
        'basic_salary': 18000.0,
        'hds_in_epf_applicable': True,
        'hds_in_esic_applicable': True,
        'hds_in_lwf_applicable': True,
    }, origin=emp)

    rec._onchange_ctc_and_statutory_inputs()
    print("Cost with ESIC=True:", rec.hds_in_employer_cost_monthly)

    rec.hds_in_esic_applicable = False
    rec._onchange_esic_applicable()
    rec._onchange_ctc_and_statutory_inputs()
    print("Cost after setting ESIC=False:", rec.hds_in_employer_cost_monthly)

    rec.hds_in_epf_applicable = False
    rec._onchange_ctc_and_statutory_inputs()
    print("Cost after setting EPF=False:", rec.hds_in_employer_cost_monthly)

    rec.hds_in_lwf_applicable = False
    rec._onchange_ctc_and_statutory_inputs()
    print("Cost after setting LWF=False:", rec.hds_in_employer_cost_monthly)
