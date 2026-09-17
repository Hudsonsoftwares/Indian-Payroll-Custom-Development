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

    # Let's inspect onchange specs for hr.employee form view
    view_info = emp.get_view(view_type='form')
    fields_spec = view_info.get('models', {}).get('hr.employee', {})
    print("Has onchange on hds_in_esic_applicable:", 'hds_in_esic_applicable' in Employee._onchange_methods)
    print("Methods for hds_in_esic_applicable:", Employee._onchange_methods.get('hds_in_esic_applicable'))
    print("Methods for hds_in_lwf_applicable:", Employee._onchange_methods.get('hds_in_lwf_applicable'))
    print("Methods for hds_in_epf_applicable:", Employee._onchange_methods.get('hds_in_epf_applicable'))

    # Now let's call onchange on an existing employee as the web client does
    initial_vals = {f: emp[f] for f in ['wage', 'basic_salary', 'hds_in_esic_applicable', 'hds_in_epf_applicable', 'hds_in_lwf_applicable', 'hds_in_employer_cost_monthly', 'hds_in_employer_cost_annual'] if f in Employee._fields}
    print("\nInitial values:", initial_vals)

    # Simulate web client onchange when toggling hds_in_esic_applicable from True to False
    values = dict(initial_vals)
    values['hds_in_esic_applicable'] = not values['hds_in_esic_applicable']
    res = emp.onchange(values, ['hds_in_esic_applicable'], {f: {} for f in Employee._fields})
    print("\nOnchange result when toggling ESIC:")
    print("  value keys returned:", [k for k in res.get('value', {}).keys() if 'employer_cost' in k or 'esic' in k])
    print("  hds_in_employer_cost_monthly:", res.get('value', {}).get('hds_in_employer_cost_monthly'))
    print("  hds_in_employer_cost_annual:", res.get('value', {}).get('hds_in_employer_cost_annual'))
