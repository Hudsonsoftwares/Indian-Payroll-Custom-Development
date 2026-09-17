import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']

    # Let's find an employee who has a contract
    emp = Employee.search([('wage', '>', 0)], limit=1)
    if emp:
        print(f"Testing on existing employee {emp.name}, ID: {emp.id}, wage: {emp.wage}")
        print("Initial employer cost monthly:", emp.hds_in_employer_cost_monthly)
        print("EPF:", emp.hds_in_epf_applicable, "ESIC:", emp.hds_in_esic_applicable, "LWF:", emp.hds_in_lwf_applicable)

        # Toggle ESIC off
        emp.hds_in_esic_applicable = not emp.hds_in_esic_applicable
        emp._onchange_ctc_and_statutory_inputs()
        print("After toggling ESIC:", emp.hds_in_employer_cost_monthly)

        # Toggle EPF off
        emp.hds_in_epf_applicable = not emp.hds_in_epf_applicable
        emp._onchange_ctc_and_statutory_inputs()
        print("After toggling EPF:", emp.hds_in_employer_cost_monthly)

        # Toggle LWF off
        emp.hds_in_lwf_applicable = not emp.hds_in_lwf_applicable
        emp._onchange_ctc_and_statutory_inputs()
        print("After toggling LWF:", emp.hds_in_employer_cost_monthly)
    else:
        print("No employee with wage found")
