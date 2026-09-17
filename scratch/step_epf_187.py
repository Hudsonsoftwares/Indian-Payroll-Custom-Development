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
    slip = env['hr.payslip'].browse(187)
    
    from odoo.addons.hudson_in_payroll.services.epf.epf_service import EPFService
    
    # We will run compute_sheet with logging or step through
    # Let's inspect what happens during slip.compute_sheet()
    def inspect_rule_compute(rule_code):
        rule = slip.struct_id.rule_ids.filtered(lambda r: r.code == rule_code)
        print(f"Rule {rule_code}: {rule.name}, select: {rule.amount_select}, code: {rule.amount_python_compute}")
        
    inspect_rule_compute('PF_WAGE')
    inspect_rule_compute('EPF')
    inspect_rule_compute('EMPLOYER_EPF')
    
    # Let's see what EPFService returns when called with slip
    # Create fake localdict as during payroll
    rules_dict = {l.code: l for l in slip.line_ids}
    ld = {
        'payslip': slip,
        'payslip_record': slip,
        'employee': slip.employee_id,
        'contract': slip.contract_id,
        'rules': rules_dict,
        'BASIC': 2400.0,
        'DA': 300.0,
        'PF_WAGE': 234.78,
    }
    svc = EPFService(env, localdict=ld)
    print("\n--- Testing with simulated localdict ---")
    print("employee.hds_in_epf_applicable:", slip.employee_id.hds_in_epf_applicable)
    print("company.hds_in_epf_applicable:", slip.company_id.hds_in_epf_applicable)
    print("wage_calc.get_actual_pf_wage:", svc.wage_calc.get_actual_pf_wage(slip, localdict=ld))
    print("wage_calc.get_pf_contribution_wage:", svc.wage_calc.get_pf_contribution_wage(slip, localdict=ld))
    print("employee_calc.compute:", svc.employee_calc.compute(slip))
    print("employer_calc.compute_employer_epf:", svc.employer_calc.compute_employer_epf(slip))
