import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']
    emp = Employee.browse(11)  # devipriya

    print(f"Testing on devipriya (id=11):")
    print(f"wage={emp.wage}, ctc_m={emp.hds_in_employer_cost_monthly}")
    print(f"epf={emp.hds_in_epf_applicable}, esic={emp.hds_in_esic_applicable}, lwf={emp.hds_in_lwf_applicable}")

    # Build values dict as web client sends in onchange
    all_fields = list(Employee._fields.keys())
    values = {f: emp[f] for f in all_fields if f in emp}

    # 1. Toggle ESIC False
    vals1 = dict(values)
    vals1['hds_in_esic_applicable'] = False
    res1 = emp.onchange(vals1, ['hds_in_esic_applicable'], {f: {} for f in all_fields})
    print("\n1. Result after toggling ESIC False:")
    print("   value returned:", {k: res1['value'][k] for k in res1.get('value', {}) if 'employer_cost' in k or 'esic' in k})

    # 2. Toggle EPF False
    vals2 = dict(values)
    vals2['hds_in_epf_applicable'] = False
    res2 = emp.onchange(vals2, ['hds_in_epf_applicable'], {f: {} for f in all_fields})
    print("\n2. Result after toggling EPF False:")
    print("   value returned:", {k: res2['value'][k] for k in res2.get('value', {}) if 'employer_cost' in k or 'epf' in k})

    # 3. Toggle LWF False
    vals3 = dict(values)
    vals3['hds_in_lwf_applicable'] = False
    res3 = emp.onchange(vals3, ['hds_in_lwf_applicable'], {f: {} for f in all_fields})
    print("\n3. Result after toggling LWF False:")
    print("   value returned:", {k: res3['value'][k] for k in res3.get('value', {}) if 'employer_cost' in k or 'lwf' in k})
