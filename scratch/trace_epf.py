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
    svc = EPFService(env)
    print("Actual PF Wage:", svc.wage_calc.get_actual_pf_wage(slip))
    print("PF Contribution Wage:", svc.wage_calc.get_pf_contribution_wage(slip))
    print("Employee EPF:", svc.employee_calc.compute(slip))
