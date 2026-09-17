import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']

    # Simulate default_get when clicking "New"
    default_vals = Employee.default_get(list(Employee._fields.keys()))
    print("Default values on New:")
    print("  hds_in_esic_applicable:", default_vals.get('hds_in_esic_applicable'))
    print("  hds_in_esic_ip_status:", default_vals.get('hds_in_esic_ip_status'))

    emp = Employee.new(default_vals)
    print("\nInitial emp record:")
    print("  wage:", emp.wage)
    print("  contract_date_start:", emp.contract_date_start)
    print("  hds_in_esic_applicable:", emp.hds_in_esic_applicable)
    print("  hds_in_esic_contribution_period:", emp.hds_in_esic_contribution_period)

    # Now simulate user typing wage = 10000
    emp.wage = 10000.0
    print("\nAfter setting wage=10000 (before onchange):")
    print("  hds_in_esic_applicable:", emp.hds_in_esic_applicable)
    print("  hds_in_esic_contribution_period:", emp.hds_in_esic_contribution_period)

    # Now trigger onchanges that Odoo web client triggers
    # In web client, onchange is called for fields with on_change=True
    # Let's check which onchange methods exist
    onchange_result = emp._onchange_esic_default_triggers()
    print("\nAfter _onchange_esic_default_triggers:")
    print("  hds_in_esic_applicable:", emp.hds_in_esic_applicable)
    print("  hds_in_esic_contribution_period:", emp.hds_in_esic_contribution_period)

    # Now user sets contract_date_start = '2026-10-01'
    emp.contract_date_start = fields.Date.from_string('2026-10-01')
    print("\nAfter setting contract_date_start='2026-10-01':")
    print("  hds_in_esic_applicable:", emp.hds_in_esic_applicable)
    print("  hds_in_esic_contribution_period:", emp.hds_in_esic_contribution_period)
