# -*- coding: utf-8 -*-
import base64
from datetime import date
from odoo import api, SUPERUSER_ID
from odoo.modules.registry import Registry

db_name = 'RevisedPayroll'
registry = Registry(db_name)

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    company = env['res.company'].search([], limit=1)

    # Check available payslips
    slips = env['hr.payslip'].search([('company_id', '=', company.id)], order='date_to desc')
    print(f"Total payslips found in DB: {len(slips)}")
    for s in slips[:5]:
        print(f"  Slip: ID={s.id}, Emp={s.employee_id.name}, State={s.state}, Period={s.date_from} to {s.date_to}, Lines={len(s.line_ids)}")

    sample_slip = slips.filtered(lambda s: bool(s.line_ids))[:1]
    if not sample_slip:
        print("No computed slips found!")
    else:
        test_year = str(sample_slip.date_to.year)
        test_month = str(sample_slip.date_to.month)
        date_from = sample_slip.date_from
        date_to = sample_slip.date_to
        print(f"\nUsing test period: Year={test_year}, Month={test_month}, {date_from} to {date_to}")

        print("\n=== TESTING REPORT 1: SALARY STATEMENT REPORT ===")
        stat_report = env['hds.salary.statement.report'].create({
            'year': test_year,
            'month': test_month,
            'company_id': company.id,
            'payslip_state': 'all',
        })
        stat_report.action_populate()
        print(f"Salary Statement Lines count: {len(stat_report.line_ids)}")
        for l in stat_report.line_ids[:3]:
            print(f"  Line: {l.employee_id.name} | Gross: {l.gross} | EE PF: {l.pf_ee} | Net: {l.net_pay} | ER PF: {l.pf_er} | ER ESI: {l.esi_er} | CTC: {l.total_employer_cost}")

        # Test XLSX export
        res_xlsx = stat_report.action_export_xlsx()
        print(f"XLSX action result: {res_xlsx.get('url')}")
        assert stat_report.xlsx_file, "XLSX file binary not generated!"
        xlsx_bytes = base64.b64decode(stat_report.xlsx_file)
        print(f"Generated XLSX size: {len(xlsx_bytes)} bytes")

        # Test Print PDF action
        res_pdf = stat_report.action_print_pdf()
        print(f"PDF action result: {res_pdf}")
        report_act = env.ref('hudson_in_payroll.action_report_salary_statement')
        # Render QWeb HTML
        html_content, doc_type = report_act._render_qweb_html(stat_report.ids)
        print(f"Salary Statement QWeb HTML rendered successfully! Size: {len(html_content)} bytes")

        print("\n=== TESTING REPORT 2: SALARY REGISTER WIZARD ===")
        reg_wizard = env['hds.salary.register.wizard'].create({
            'date_from': date_from,
            'date_to': date_to,
            'company_id': company.id,
            'payslip_state': 'all',
        })
        reg_data = reg_wizard._get_salary_register_data()
        print(f"Salary Register Rows count: {len(reg_data['rows'])}")
        for r in reg_data['rows'][:3]:
            print(f"  Row: {r['emp_name']} | Gross: {r['gross']} | Net: {r['net']} | Cost: {r['cost']}")

        # Test XLSX export
        res_reg_xlsx = reg_wizard.action_export_xlsx()
        print(f"Salary Register XLSX action result: {res_reg_xlsx.get('url')}")
        assert reg_wizard.xlsx_file, "Salary Register XLSX binary not generated!"
        xlsx_reg_bytes = base64.b64decode(reg_wizard.xlsx_file)
        print(f"Generated XLSX size: {len(xlsx_reg_bytes)} bytes")

        # Test Print PDF action
        res_reg_pdf = reg_wizard.action_print_pdf()
        print(f"Salary Register PDF action result: {res_reg_pdf}")
        report_reg_act = env.ref('hudson_in_payroll.action_report_salary_register')
        html_reg_content, _ = report_reg_act._render_qweb_html(reg_wizard.ids)
        print(f"Salary Register QWeb HTML rendered successfully! Size: {len(html_reg_content)} bytes")

        print("\n=== TESTING REPORT 3: YEARLY SALARY BY EMPLOYEE WIZARD ===")
        yearly_wizard = env['hds.yearly.salary.employee.wizard'].create({
            'year': test_year,
            'company_id': company.id,
            'payslip_state': 'all',
        })
        yearly_data = yearly_wizard._get_yearly_data()
        print(f"Yearly Summary Rows count: {len(yearly_data['summary_rows'])}")
        print(f"Yearly Detail Rows count: {len(yearly_data['detail_rows'])}")
        for sr in yearly_data['summary_rows'][:3]:
            print(f"  Summary: {sr['emp_name']} | Ann Gross: {sr['ann_gross']} | Ann Net: {sr['ann_net']} | Ann CTC: {sr['ann_ctc']}")

        # Test XLSX export
        res_yearly_xlsx = yearly_wizard.action_print_xlsx()
        print(f"Yearly XLSX action result: {res_yearly_xlsx.get('url')}")
        assert yearly_wizard.xlsx_file, "Yearly XLSX binary not generated!"
        xlsx_yr_bytes = base64.b64decode(yearly_wizard.xlsx_file)
        print(f"Generated Yearly XLSX size: {len(xlsx_yr_bytes)} bytes")

        # Test Print PDF action
        res_yearly_pdf = yearly_wizard.action_print_pdf()
        print(f"Yearly PDF action result: {res_yearly_pdf}")
        report_yearly_act = env.ref('hudson_in_payroll.action_report_yearly_salary_employee')
        html_yr_content, _ = report_yearly_act._render_qweb_html(yearly_wizard.ids)
        print(f"Yearly Salary QWeb HTML rendered successfully! Size: {len(html_yr_content)} bytes")

        print("\n>>> ALL THREE REPORTS (XLSX & PDF PRINT) VERIFIED AND WORKING PERFECTLY! <<<")
