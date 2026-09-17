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
    # Find employee with 20k or test with devipriya / administrator
    admin = env['hr.employee'].search([('name', 'ilike', 'Administrator')], limit=1)
    admin.hds_in_epf_applicable = True
    admin.hds_in_pf_contribution_basis = 'statutory_ceiling'
    
    contract = env['hr.version'].search([('employee_id', '=', admin.id)], limit=1)
    print(f"Contract: {contract.name}, Wage: {contract.wage}, pay_by_attendance: {contract.pay_by_attendance}")
    
    # Check slip 388 (October 2026: 22 days scheduled, 21 days shortage = 1 day worked)
    slip = env['hr.payslip'].search([('employee_id', '=', admin.id), ('name', 'ilike', 'October 2026')], limit=1)
    if slip:
        slip.compute_sheet()
        print(f"\nPayslip {slip.id} ({slip.name}):")
        for l in slip.line_ids:
            print(f"  {l.code} ({l.name}): {l.total}")
        for w in slip.worked_days_line_ids:
            print(f"  WorkedDay {w.code} ({w.name}): days={w.number_of_days}, hours={w.number_of_hours}")
