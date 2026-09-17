import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID
import logging

# Enable debug logging for epf
logging.getLogger('odoo.addons.hudson_in_payroll.services.epf').setLevel(logging.DEBUG)

config_file = r"C:\Program Files\Odoo 19.0.20260717\server\odoo.conf"
odoo.tools.config.parse_config(['-c', config_file, '-d', 'RevisedPayroll'])
from odoo.modules.registry import Registry
registry = Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    slip = env['hr.payslip'].browse(388)
    
    # We will hook into get_actual_pf_wage to print caller stack and arguments
    from odoo.addons.hudson_in_payroll.services.epf.wage_calculator import EPFWageCalculator
    orig_get_actual = EPFWageCalculator.get_actual_pf_wage
    def debug_get_actual(self, payslip, localdict=None):
        res = orig_get_actual(self, payslip, localdict=localdict)
        print(f"DEBUG get_actual_pf_wage -> {res}, localdict keys: {list(localdict.keys()) if localdict else None}")
        return res
    EPFWageCalculator.get_actual_pf_wage = debug_get_actual
    
    slip.compute_sheet()
    print("Computed lines:")
    for l in slip.line_ids.filtered(lambda x: 'PF' in x.code or 'EPF' in x.code or x.code in ('BASIC', 'DA', 'SHORT')):
        print(f"  {l.code}: {l.total}")
