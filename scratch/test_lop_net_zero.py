import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
reg = odoo.modules.registry.Registry('RevisedPayroll')
with reg.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    p = env['hr.payslip'].browse(363)
    print("=== TEST 1: ABSENT EMPLOYEE (100% LOP / SHORTAGE) ===")
    print(f"Payslip {p.id}: {p.name}, Emp: {p.employee_id.name}, Contract wage: {p.contract_id.wage}")
    
    # Recompute sheet
    p.compute_sheet()
    
    print("\n--- Worked Days Lines ---")
    for wd in p.worked_days_line_ids:
        print(f"  {wd.code}: days={wd.number_of_days}, hrs={wd.number_of_hours}")
        
    print("\n--- Salary Lines ---")
    line_map = {}
    for line in p.line_ids:
        line_map[line.code] = line.total
        if line.code in ['BASIC', 'DA', 'FIXED', 'SHORT', 'UNPAID', 'GROSS', 'PF_WAGE', 'EPF', 'EMPLOYER_EPF', 'EPS', 'ESIC_WAGE', 'ESIC_EE', 'ESIC_ER', 'PT', 'LWF_EE', 'HDS_IN_TDS', 'NET']:
            print(f"  [{line.category_id.code}] {line.code}: {line.total}")

    print(f"\nNet Wage on payslip: {p.net_wage}")
    
    # Assertions
    assert p.net_wage == 0.0, f"Net wage must be 0.0, got {p.net_wage}"
    assert line_map.get('NET', 0.0) == 0.0, f"NET line must be 0.0, got {line_map.get('NET')}"
    assert line_map.get('SHORT', 0.0) == -15000.0, f"SHORT deduction must be -15000.0, got {line_map.get('SHORT')}"
    assert line_map.get('PF_WAGE', 0.0) == 0.0, f"PF_WAGE must be 0.0, got {line_map.get('PF_WAGE')}"
    assert line_map.get('EPF', 0.0) == 0.0, f"EPF must be 0.0, got {line_map.get('EPF')}"
    assert line_map.get('EMPLOYER_EPF', 0.0) == 0.0, f"EMPLOYER_EPF must be 0.0, got {line_map.get('EMPLOYER_EPF')}"
    assert line_map.get('EPS', 0.0) == 0.0, f"EPS must be 0.0, got {line_map.get('EPS')}"
    assert line_map.get('ESIC_WAGE', 0.0) == 0.0, f"ESIC_WAGE must be 0.0, got {line_map.get('ESIC_WAGE')}"
    assert line_map.get('ESIC_EE', 0.0) == 0.0, f"ESIC_EE must be 0.0, got {line_map.get('ESIC_EE')}"
    assert line_map.get('PT', 0.0) == 0.0, f"PT must be 0.0, got {line_map.get('PT')}"
    print("\n>>> ALL TEST 1 ASSERTIONS PASSED! <<<")

    print("\n=== TEST 2: FULL WORKED MONTH (0 SHORTAGE) ===")
    p_full = env['hr.payslip'].browse(188)
    if p_full:
        p_full.compute_sheet()
        print(f"Payslip {p_full.id}: {p_full.name}, Net: {p_full.net_wage}")
        assert p_full.net_wage > 0.0, f"Full worked payslip must have positive net wage, got {p_full.net_wage}"
        print(">>> TEST 2 (FULL ATTENDANCE) PASSED! <<<")

    print("\n=== TEST 3: PARTIAL SHORTAGE (11 HRS SHORTAGE) ===")
    p_partial = env['hr.payslip'].browse(189)
    if p_partial:
        p_partial.compute_sheet()
        print(f"Payslip {p_partial.id}: {p_partial.name}, Net: {p_partial.net_wage}")
        assert p_partial.net_wage > 0.0, f"Partial shortage payslip must have positive net wage, got {p_partial.net_wage}"
        print(">>> TEST 3 (PARTIAL SHORTAGE) PASSED! <<<")

    cr.rollback()

