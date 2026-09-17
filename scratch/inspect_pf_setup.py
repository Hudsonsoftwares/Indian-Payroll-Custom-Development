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
    admin = env['hr.employee'].search([('name', 'ilike', 'Administrator')], limit=1)
    contract = env['hr.version'].search([('employee_id', '=', admin.id)], limit=1)
    struct = contract.struct_id
    print(f"Contract: {contract.name}, Wage: {contract.wage}, Struct: {struct.name if struct else 'None'}")
    
    # Check PF settings on employee and company
    print(f"Employee PF Contribution Basis: {getattr(admin, 'hds_in_pf_contribution_basis', 'N/A')}")
    print(f"Employee PF Employer Basis: {getattr(admin, 'hds_in_pf_employer_basis', 'N/A')}")
    for f in admin._fields:
        if 'pf' in f.lower():
            print(f"  Employee field {f}: {getattr(admin, f)}")
    
    print("\nCompany fields with PF:")
    for f in admin.company_id._fields:
        if 'pf' in f.lower():
            print(f"  Company field {f}: {getattr(admin.company_id, f)}")
            
    print("\nContract fields with PF:")
    for f in contract._fields:
        if 'pf' in f.lower():
            print(f"  Contract field {f}: {getattr(contract, f)}")

    print("\nSalary Rules in Struct:")
    if struct:
        for r in struct.rule_ids:
            if r.code in ('BASIC', 'DA', 'HRA', 'PF', 'EPF', 'PF_EE', 'PF_ER', 'PF_WAGE', 'EPS') or r.hds_in_include_in_pf_wage:
                print(f"  Rule: {r.code} ({r.name}), Seq: {r.sequence}, Amount Type: {r.amount_select}, Incl PF: {r.hds_in_include_in_pf_wage}")
                if r.amount_select == 'code':
                    print(f"    Code:\n{r.amount_python_compute}")
                elif r.amount_select == 'percentage':
                    print(f"    Percentage: {r.amount_percentage}% of {r.amount_percentage_base}")
