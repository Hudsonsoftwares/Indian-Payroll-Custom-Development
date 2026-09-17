import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    # Test creating employee with new() or in memory
    emp = env['hr.employee'].new({
        'name': 'Test Joiner Oct',
        'wage': 10000.0,
        'contract_date_start': fields.Date.from_string('2026-10-01'),
    })
    print("New employee before onchange:")
    print("contract_date_start:", emp.contract_date_start)
    print("date_start:", getattr(emp, 'date_start', None))
    print("date_version:", getattr(emp, 'date_version', None))
    print("hds_in_esic_applicable:", emp.hds_in_esic_applicable)
    print("hds_in_esic_contribution_period:", emp.hds_in_esic_contribution_period)

    # Let's trigger onchanges
    emp._onchange_esic_default_triggers()
    print("\nAfter _onchange_esic_default_triggers:")
    print("hds_in_esic_applicable:", emp.hds_in_esic_applicable)
    print("hds_in_esic_contribution_period:", emp.hds_in_esic_contribution_period)
