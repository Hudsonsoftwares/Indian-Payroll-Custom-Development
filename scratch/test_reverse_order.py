import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']

    emp = Employee.new({'name': 'Reverse Order Joiner'})
    print("1. Initial:", emp.hds_in_esic_contribution_period, emp.hds_in_esic_applicable)

    emp.contract_date_start = fields.Date.from_string('2026-10-01')
    emp._onchange_esic_default_triggers()
    print("2. After Oct 1 date:", emp.hds_in_esic_contribution_period, emp.hds_in_esic_applicable)

    emp.wage = 10000.0
    emp._onchange_esic_default_triggers()
    print("3. After wage 10k:", emp.hds_in_esic_contribution_period, emp.hds_in_esic_applicable)
