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
    admin.hds_in_epf_applicable = True
    admin.hds_in_lwf_applicable = True
    
    slip = env['hr.payslip'].browse(187)
    slip.compute_sheet()
    cr.commit()
    print("Slip 187 recomputed and committed to DB!")
    for l in slip.line_ids:
        if 'PF' in l.code or 'EPF' in l.code or 'LWF' in l.code:
            print(f"  {l.code} ({l.name}): {l.total}")
