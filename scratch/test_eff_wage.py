import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    from odoo.addons.hudson_in_payroll.services.esic.contribution_period_service import ESICContributionPeriodService
    svc = ESICContributionPeriodService(env)

    # What does get_effective_wage_on_date return on an employee with wage=10000?
    emp = env['hr.employee'].new({
        'name': 'Test Oct Joiner',
        'wage': 10000.0,
        'contract_date_start': fields.Date.from_string('2026-10-01'),
        'hds_in_esic_applicable': False,
    })
    eff_wage = svc.get_effective_wage_on_date(emp, fields.Date.from_string('2026-10-01'))
    print("get_effective_wage_on_date:", eff_wage)
    cov = svc.is_covered_for_contribution_period(emp, eval_date=fields.Date.from_string('2026-10-01'), current_wage=10000.0)
    print("is_covered:", cov)
