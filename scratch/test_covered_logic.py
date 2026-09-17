import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    from odoo.addons.hudson_in_payroll.services.esic.contribution_period_service import ESICContributionPeriodService
    period_service = ESICContributionPeriodService(env)

    # New employee unsaved
    emp = env['hr.employee'].new({
        'name': 'Test Joiner',
        'wage': 10000.0,
        'contract_date_start': fields.Date.from_string('2026-10-01'),
        'hds_in_esic_applicable': False,
        'hds_in_esic_ip_status': 'exempt',
    })

    # Case 1: eval_date = 2026-10-01 (October period)
    res_oct = period_service.is_covered_for_contribution_period(emp, eval_date='2026-10-01', current_wage=10000.0)
    print("eval_date 2026-10-01 is_covered:", res_oct)

    # Case 2: eval_date = 2026-09-17 (today)
    res_today = period_service.is_covered_for_contribution_period(emp, eval_date='2026-09-17', current_wage=10000.0)
    print("eval_date 2026-09-17 is_covered:", res_today)
