# scratch/test_lwf_dynamic.py
import sys

def test_lwf(env):
    print("=== TESTING DYNAMIC LWF IN CONTRACT CTC & SALARY REVISION ===")
    
    from odoo.addons.hudson_in_payroll.services.revision.salary_preview_service import SalaryPreviewService
    from odoo.addons.hudson_in_payroll.services.payroll.work_location_service import PayrollWorkLocationService
    from odoo.addons.hudson_in_payroll.services.lwf.lwf_rate_service import LWFRateService

    # 1. Fetch an employee
    emp = env['hr.employee'].search([('active', '=', True)], limit=1)
    company = emp.company_id or env.company
    contract = env['hr.version'].search([('employee_id', '=', emp.id)], limit=1)
    
    print(f"Employee: {emp.name} (ID: {emp.id}), Company: {company.name}")
    print(f"Initial Company LWF Enabled: {company.hds_in_enable_lwf}")
    print(f"Initial Employee LWF Applicable: {emp.hds_in_lwf_applicable}")
    
    preview_svc = SalaryPreviewService(env)

    # CASE 1: Company LWF is False (Current actual state in My Company)
    # Even if employee has hds_in_lwf_applicable=True, preview and CTC MUST be 0.0, NOT hardcoded 20.0!
    emp.hds_in_lwf_applicable = True
    company.hds_in_enable_lwf = False
    preview = preview_svc.calculate_preview(emp, 25000.0, 30000.0)
    print(f"\n[Test 1: Company LWF Disabled] Preview LWF Amount: {preview.get('lwf_amount')}")
    assert preview.get('lwf_amount') == 0.0, f"Expected 0.0 when company LWF disabled, got {preview.get('lwf_amount')}"
    
    lwf_rule = env['hr.salary.rule'].search([('code', '=', 'LWF_ER')], limit=1)
    if contract and lwf_rule:
        amt = contract._estimate_statutory_rule_amount(contract, lwf_rule, employee=emp)
        print(f"[Test 1: Contract CTC Rule LWF_ER when company LWF disabled]: {amt}")
        assert amt == 0.0, f"Expected 0.0 for contract when company LWF disabled, got {amt}"

    # CASE 2: When LWF is Enabled for Company & Employee
    # Temporarily set min_employee_count = 1 on Kerala rate so threshold check passes in test
    state_kl = env.ref('base.state_in_kl', raise_if_not_found=False)
    rate_kl = env['lwf.state.rate'].search([('state_id', '=', state_kl.id)], limit=1) if state_kl else False
    if rate_kl:
        orig_min = rate_kl.min_employee_count
        rate_kl.min_employee_count = 1
        company.hds_in_enable_lwf = True
        emp.hds_in_lwf_applicable = True
        emp.address_id.state_id = state_kl.id

        print(f"\nKerala LWF Master Rate: emp={rate_kl.emp_contribution}, empl={rate_kl.empl_contribution}")
        preview = preview_svc.calculate_preview(emp, 25000.0, 30000.0)
        print(f"[Test 2: Kerala] Preview LWF (Employee Deduction): {preview.get('lwf_amount')}")
        assert preview.get('lwf_amount') == rate_kl.emp_contribution, f"Expected {rate_kl.emp_contribution}, got {preview.get('lwf_amount')}"
        
        if contract and lwf_rule:
            amt = contract._estimate_statutory_rule_amount(contract, lwf_rule, employee=emp)
            print(f"[Test 2: Kerala] Contract CTC Rule LWF_ER (Employer Contribution): {amt}")
            assert amt == rate_kl.empl_contribution, f"Expected {rate_kl.empl_contribution}, got {amt}"

    # CASE 3: LWF Enabled with Maharashtra State
    state_mh = env.ref('base.state_in_mh', raise_if_not_found=False)
    rate_mh = env['lwf.state.rate'].search([('state_id', '=', state_mh.id)], limit=1) if state_mh else False
    if rate_mh:
        print(f"\nMaharashtra LWF Master Rate: emp={rate_mh.emp_contribution}, empl={rate_mh.empl_contribution}")
        emp.address_id.state_id = state_mh.id
        preview = preview_svc.calculate_preview(emp, 25000.0, 30000.0)
        print(f"[Test 3: Maharashtra] Preview LWF (Employee Deduction): {preview.get('lwf_amount')}")
        assert preview.get('lwf_amount') == rate_mh.emp_contribution, f"Expected {rate_mh.emp_contribution}, got {preview.get('lwf_amount')}"
        
        if contract and lwf_rule:
            amt = contract._estimate_statutory_rule_amount(contract, lwf_rule, employee=emp)
            print(f"[Test 3: Maharashtra] Contract CTC Rule LWF_ER (Employer Contribution): {amt}")
            assert amt == rate_mh.empl_contribution, f"Expected {rate_mh.empl_contribution}, got {amt}"

    # Rollback test transaction
    env.cr.rollback()
    print("\nALL DYNAMIC LWF TESTS PASSED PERFECTLY!")

test_lwf(env)
