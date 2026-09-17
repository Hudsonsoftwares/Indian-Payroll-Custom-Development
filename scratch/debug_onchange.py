import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']
    emp = Employee.search([('wage', '>', 0)], limit=1)

    initial_vals = {f: emp[f] for f in ['wage', 'basic_salary', 'hds_in_esic_applicable', 'hds_in_epf_applicable', 'hds_in_lwf_applicable', 'hds_in_employer_cost_monthly', 'hds_in_employer_cost_annual'] if f in Employee._fields}

    # Step by step onchange
    values = dict(initial_vals)
    values['hds_in_esic_applicable'] = True  # enable ESIC
    
    # Let's inspect onchange implementation in Odoo
    # When onchange runs, it creates a new record with values
    draft_record = Employee.new(values, origin=emp)
    print("Before onchange methods on draft_record:")
    print("  draft_record.hds_in_esic_applicable:", draft_record.hds_in_esic_applicable)
    print("  draft_record.hds_in_employer_cost_monthly:", draft_record.hds_in_employer_cost_monthly)

    draft_record._onchange_ctc_and_statutory_inputs()
    print("After _onchange_ctc_and_statutory_inputs:")
    print("  draft_record.hds_in_employer_cost_monthly:", draft_record.hds_in_employer_cost_monthly)

    # Let's check what onchange diff detects
    diff = draft_record._get_onchange_values() if hasattr(draft_record, '_get_onchange_values') else None
    print("Onchange diff:", diff)
