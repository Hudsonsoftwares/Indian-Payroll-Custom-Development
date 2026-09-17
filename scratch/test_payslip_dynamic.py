# test_payslip_dynamic.py
import sys

def run_test(env):
    print("--- TESTING PAYSLIP DYNAMIC REGIME & PAYMENT MODE ---")
    
    # 1. Fetch any payslip
    slip = env['hr.payslip'].search([], order='id desc', limit=1)
    if not slip:
        print("No payslip found!")
        return

    print(f"Testing Payslip ID: {slip.id}, Name: {slip.name}, Employee: {slip.employee_id.name}")
    
    # Initial data
    pdata = slip.get_payslip_pdf_data()
    print(f"Regime Code: {pdata.get('regime_code')}")
    print(f"Regime Display: {pdata.get('regime_display')}")
    print(f"Regime Header: {pdata.get('regime_header')}")
    print(f"Payment Mode: {pdata.get('payment_mode')}")
    print(f"Bank Name: {pdata.get('bank_name')}")
    print(f"Account No: {pdata.get('acc_no')}")
    print(f"Tax Comp Deductions: {pdata.get('tax_comp_deductions')}")
    
    # Test Cash mode
    slip.hds_in_payment_mode = 'cash'
    pdata_cash = slip.get_payslip_pdf_data()
    print("\n--- After Setting Payment Mode = 'cash' ---")
    print(f"Payment Mode: {pdata_cash.get('payment_mode')}")
    print(f"Bank Name: {pdata_cash.get('bank_name')}")
    print(f"Account No: {pdata_cash.get('acc_no')}")
    assert pdata_cash.get('payment_mode') == 'CASH', "Payment mode should be CASH"
    assert pdata_cash.get('bank_name') == 'N/A', "Bank should be N/A for cash"
    assert pdata_cash.get('acc_no') == 'N/A', "Account should be N/A for cash"

    # Test UPI mode
    slip.hds_in_payment_mode = 'upi'
    pdata_upi = slip.get_payslip_pdf_data()
    print("\n--- After Setting Payment Mode = 'upi' ---")
    print(f"Payment Mode: {pdata_upi.get('payment_mode')}")
    assert pdata_upi.get('payment_mode') == 'UPI', "Payment mode should be UPI"

    # Test NEFT / RTGS mode
    slip.hds_in_payment_mode = 'neft_rtgs'
    pdata_neft = slip.get_payslip_pdf_data()
    print("\n--- After Setting Payment Mode = 'neft_rtgs' ---")
    print(f"Payment Mode: {pdata_neft.get('payment_mode')}")
    assert pdata_neft.get('payment_mode') == 'NEFT / RTGS', "Payment mode should be NEFT / RTGS"

    # Test template rendering
    report = env.ref('hudson_payroll_base.action_report_payslip', raise_if_not_found=False)
    if report:
        print("\nRendering QWeb payslip report HTML to verify no XML errors...")
        html_content, _ = report._render_qweb_html('hudson_payroll_base.report_payslip_document', [slip.id])
        if isinstance(html_content, bytes):
            html_content = html_content.decode('utf-8')
        print(f"Rendered HTML successfully! String length: {len(html_content)}")
        
        # Verify Tax Regime and Payment Mode presence in rendered HTML
        assert "Tax Regime" in html_content, "Tax Regime label missing in HTML!"
        assert pdata_neft.get('regime_display') in html_content, f"Regime display '{pdata_neft.get('regime_display')}' missing in HTML!"
        assert "DEDUCTIONS (" in html_content, "DEDUCTIONS header missing in HTML!"
        assert pdata_neft.get('regime_header') in html_content, f"Regime header '{pdata_neft.get('regime_header')}' missing in HTML!"
        assert "NEFT / RTGS" in html_content, "Payment mode 'NEFT / RTGS' missing in HTML!"
        print("All HTML content assertions PASSED!")

    # Reset payment mode back
    slip.hds_in_payment_mode = 'bank_transfer'
    env.cr.rollback()
    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

run_test(env)
