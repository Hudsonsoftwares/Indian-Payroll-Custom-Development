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

    # Simulate creating employee in memory
    emp = env['hr.employee'].new({
        'name': 'Oct Joiner Employee',
        'contract_date_start': fields.Date.from_string('2026-10-01'),
        'wage': 10000.0,
    })

    # Let's inspect ref_date resolution
    today = fields.Date.today()
    join_date = (
        getattr(emp, 'contract_date_start', None) or
        getattr(emp, 'date_start', None) or
        getattr(emp, 'hds_in_esic_joining_date', None) or
        getattr(emp, 'date_version', None)
    )
    ref_date = join_date if (join_date and join_date > today) else today
    print("Resolved ref_date:", ref_date)

    year = ref_date.year
    month = ref_date.month
    if 4 <= month <= 9:
        period_str = f"April {year} – September {year}"
        valid_until = f"30-Sep-{year}"
    elif month >= 10:
        period_str = f"October {year} – March {year + 1}"
        valid_until = f"31-Mar-{year + 1}"
    else:
        period_str = f"October {year - 1} – March {year}"
        valid_until = f"31-Mar-{year}"

    print("Period string:", period_str)
    print("Valid until:", valid_until)
