import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID
import datetime

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
reg = odoo.modules.registry.Registry('RevisedPayroll')
with reg.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Look at how payslip 363 was computed
    p = env['hr.payslip'].browse(363)
    print("Contract wage:", p.contract_id.wage)
    print("Worked days:", [(wd.code, wd.number_of_days, wd.number_of_hours) for wd in p.worked_days_line_ids])
    
    # Check effective paid days on p
    if hasattr(p, 'hds_in_get_paid_days'):
        print("hds_in_get_paid_days:", p.hds_in_get_paid_days())
    
    # Check if there is any ratio or paid days helper
    for m in dir(p):
        if 'paid_days' in m or 'worked' in m or 'attendance' in m:
            print("  payslip method:", m)
