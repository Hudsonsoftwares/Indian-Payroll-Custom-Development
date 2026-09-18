import sys
sys.path.insert(0, r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo.modules.registry import Registry
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
registry = Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    from odoo.addons.hudson_in_payroll.services.lwf.lwf_service import LWFService
    
    # Inspect Kerala LWF rate
    state_kl = env['res.country.state'].search([('name', '=', 'Kerala'), ('country_id.code', '=', 'IN')], limit=1)
    rate_kl = env['lwf.state.rate'].search([('state_id', '=', state_kl.id)], limit=1)
    print(f"Kerala Rate ID: {rate_kl.id}, State: {rate_kl.state_id.name}, EE: {rate_kl.emp_contribution}, ER: {rate_kl.empl_contribution}")
    
    # Payslip 363 (September 2026, 100% LOP, attendance 0)
    slip_lop = env['hr.payslip'].browse(363)
    print(f"\n--- Checking Payslip {slip_lop.id} ({slip_lop.employee_id.name}) ---")
    print(f"Earned Wage Ratio: {slip_lop._get_earned_wage_ratio()}")
    
    # Save original rate parameters
    orig_freq = rate_kl.deduction_frequency
    orig_min_emp = rate_kl.min_employee_count
    orig_company_lwf = slip_lop.company_id.hds_in_enable_lwf

    # Configure Kerala rate for testing
    rate_kl.min_employee_count = 0
    rate_kl.deduction_frequency = 'monthly'
    slip_lop.company_id.hds_in_enable_lwf = True
    
    service = LWFService(env)

    # Test Scenario 1: Attendance 0 (100% LOP / 0 Earned Wage)
    # Employee has 0 attendance / 0 net salary.
    # Employee LWF must be 0.0, but Employer LWF MUST be paid (₹45.0)
    ee_val_lop = service.compute_lwf_employee(slip_lop)
    er_val_lop = service.compute_lwf_employer(slip_lop)
    print(f"[TEST 1 - Attendance 0 / 100% LOP]:")
    print(f"  Employee LWF: {ee_val_lop} (Expected: 0.0)")
    print(f"  Employer LWF: {er_val_lop} (Expected: {rate_kl.empl_contribution})")
    assert ee_val_lop == 0.0, f"Expected 0.0, got {ee_val_lop}"
    assert er_val_lop == rate_kl.empl_contribution, f"Expected {rate_kl.empl_contribution}, got {er_val_lop}"
    
    # Test Scenario 2: Active Employee with Net/Earned Salary >= State LWF amount
    # Devipriya slip 189 (Net Wage: ₹16,620.0 >= ₹45.0)
    slip_devi = env['hr.payslip'].browse(189)
    print(f"\n--- Checking Payslip {slip_devi.id} ({slip_devi.employee_id.name}) ---")
    print(f"Devipriya Net Wage: {slip_devi.net_wage}")
    
    ee_val_norm = service.compute_lwf_employee(slip_devi)
    er_val_norm = service.compute_lwf_employer(slip_devi)
    print(f"[TEST 2 - Net/Earned Salary >= State Amount ({rate_kl.emp_contribution})]:")
    print(f"  Employee LWF: {ee_val_norm} (Expected: {rate_kl.emp_contribution})")
    print(f"  Employer LWF: {er_val_norm} (Expected: {rate_kl.empl_contribution})")
    assert ee_val_norm == rate_kl.emp_contribution, f"Expected {rate_kl.emp_contribution}, got {ee_val_norm}"
    assert er_val_norm == rate_kl.empl_contribution, f"Expected {rate_kl.empl_contribution}, got {er_val_norm}"
    
    # Test Scenario 3: Employee with Net/Earned Salary < State LWF amount (e.g. earned only ₹20, less than ₹45)
    # Using localdict simulation
    class FakeCategories:
        BASIC = 20.0
        ALW = 0.0
        GROSS = 20.0
        DED = 0.0
    sim_service = LWFService(env, localdict={'categories': FakeCategories(), 'payslip_record': slip_devi})
    ee_val_insufficient = sim_service.compute_lwf_employee(slip_devi)
    er_val_insufficient = sim_service.compute_lwf_employer(slip_devi)
    print(f"\n[TEST 3 - Net/Earned Salary (INR 20) < State Amount ({rate_kl.emp_contribution})]:")
    print(f"  Employee LWF: {ee_val_insufficient} (Expected: 0.0 because INR 20 < INR 45)")
    print(f"  Employer LWF: {er_val_insufficient} (Expected: {rate_kl.empl_contribution})")
    assert ee_val_insufficient == 0.0, f"Expected 0.0, got {ee_val_insufficient}"
    assert er_val_insufficient == rate_kl.empl_contribution, f"Expected {rate_kl.empl_contribution}, got {er_val_insufficient}"
    
    # Revert test rate settings back to half_yearly
    slip_lop.company_id.hds_in_enable_lwf = orig_company_lwf
    rate_kl.deduction_frequency = orig_freq
    rate_kl.min_employee_count = orig_min_emp
    cr.rollback()
    
    print("\nALL LWF ATTENDANCE & NET / EARNED SALARY TESTS PASSED PERFECTLY!")
