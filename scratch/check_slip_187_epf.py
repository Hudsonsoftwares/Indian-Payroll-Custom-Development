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
    slip = env['hr.payslip'].search([('employee_id', '=', admin.id), ('date_from', '>=', '2026-12-01'), ('date_to', '<=', '2026-12-31')], limit=1)
    
    print(f"Slip: {slip.id} - {slip.name}")
    print(f"Employee: {admin.name}")
    print(f"Employee hds_in_epf_applicable: {admin.hds_in_epf_applicable}")
    print(f"Company hds_in_epf_applicable: {admin.company_id.hds_in_epf_applicable}")
    
    print("\nAll lines on Slip 187:")
    for l in slip.line_ids:
        print(f"  {l.code} ({l.name}): total={l.total}, appears_on_payslip={l.appears_on_payslip}")
