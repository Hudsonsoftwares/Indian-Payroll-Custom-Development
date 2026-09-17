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
    from odoo.addons.hudson_in_payroll.services.epf.epf_service import EPFService
    slip = env['hr.payslip'].browse(388)
    
    # Let's inspect how payslip computes EPF during compute_sheet
    lines = {l.code: l.total for l in slip.line_ids}
    print("Slip lines in DB:", lines)
    print("PF_WAGE line in DB:", lines.get('PF_WAGE'))
    print("EPF line in DB:", lines.get('EPF'))
    
    # If we call hds_in_compute_employee_epf now:
    res = slip.hds_in_compute_employee_epf()
    print("Direct call hds_in_compute_employee_epf():", res)
