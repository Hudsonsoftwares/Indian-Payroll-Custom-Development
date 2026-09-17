import sys
import os
import datetime

# Add odoo paths
odoo_server = r"C:\Program Files\Odoo 19.0.20260717\server"
if odoo_server not in sys.path:
    sys.path.insert(0, odoo_server)

import odoo
from odoo import api, SUPERUSER_ID

def run_tests():
    odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
    registry = odoo.modules.registry.Registry('RevisedPayroll')

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        print("=== TEST RULE 51-B ESIC DAILY-WAGE EXEMPTION ===")

        # 1. Test Parameter Existence & Retrieval
        param_model = env['hr.rule.parameter']
        threshold_canonical = param_model.get_parameter('esic_daily_wage_exemption_threshold', date=datetime.date(2026, 9, 1), as_decimal=False)
        threshold_hds = param_model.get_parameter('hds_in_esic_daily_wage_exemption', date=datetime.date(2026, 9, 1), as_decimal=False)
        print(f"[Check 1] esic_daily_wage_exemption_threshold: {threshold_canonical}")
        print(f"[Check 1] hds_in_esic_daily_wage_exemption: {threshold_hds}")
        assert float(threshold_canonical or 0) == 176.0, f"Expected 176.0, got {threshold_canonical}"

        from odoo.addons.hudson_in_payroll.services.esic.esic_service import ESICService
        esic_service = ESICService(env)
        ee_calc = esic_service.employee_calc
        er_calc = esic_service.employer_calc

        # Find or create a test employee
        emp = env['hr.employee'].search([('name', 'ilike', 'Devipriya')], limit=1)
        if not emp:
            emp = env['hr.employee'].search([], limit=1)

        # 2. Test Case 1: Standard Wage > 176/day
        # 30 days, ESI Wage 15,000 -> Daily Wage = 500 -> Not Exempt
        print("\n--- Test Case 1: Standard Earner (Above 176/day) ---")
        slip_1 = env['hr.payslip'].new({
            'employee_id': emp.id,
            'date_from': datetime.date(2026, 9, 1),
            'date_to': datetime.date(2026, 9, 30),
            'company_id': emp.company_id.id,
        })
        is_exempt_1, avg_wage_1, paid_days_1, thresh_1 = ee_calc.check_daily_wage_exemption(slip_1, esic_wage=15000.0)
        ee_ded_1 = ee_calc.compute(slip_1, esic_wage=15000.0)
        er_ded_1 = er_calc.compute(slip_1, esic_wage=15000.0)
        print(f"Paid Days: {paid_days_1}, Wage: 15,000, Avg Daily Wage: {avg_wage_1}, Threshold: {thresh_1}")
        print(f"Is Exempt: {is_exempt_1}, EE ESIC: {ee_ded_1}, ER ESIC: {er_ded_1}")
        assert not is_exempt_1, "Case 1 should NOT be exempt"
        assert ee_ded_1 == 113.0, f"Expected 113.0, got {ee_ded_1}"
        assert er_ded_1 == 487.5 or er_ded_1 == 488.0, f"Expected ~488, got {er_ded_1}"

        # 3. Test Case 2: Low Earner <= 176/day
        # 26 days worked, ESI Wage 4,000 -> Daily Wage = 4000/26 = 153.85 <= 176 -> Exempt
        print("\n--- Test Case 2: Low Earner (<= 176/day) ---")
        slip_2 = env['hr.payslip'].new({
            'employee_id': emp.id,
            'date_from': datetime.date(2026, 9, 1),
            'date_to': datetime.date(2026, 9, 26),
            'company_id': emp.company_id.id,
        })
        is_exempt_2, avg_wage_2, paid_days_2, thresh_2 = ee_calc.check_daily_wage_exemption(slip_2, esic_wage=4000.0)
        ee_ded_2 = ee_calc.compute(slip_2, esic_wage=4000.0)
        er_ded_2 = er_calc.compute(slip_2, esic_wage=4000.0)
        print(f"Paid Days: {paid_days_2}, Wage: 4,000, Avg Daily Wage: {avg_wage_2}, Threshold: {thresh_2}")
        print(f"Is Exempt: {is_exempt_2}, EE ESIC: {ee_ded_2}, ER ESIC: {er_ded_2}")
        assert is_exempt_2, "Case 2 MUST be exempt under Rule 51-B"
        assert ee_ded_2 == 0.0, f"Expected EE ESIC 0.0, got {ee_ded_2}"
        assert er_ded_2 == 130.0, f"Expected ER ESIC 130.0 (3.25% of 4,000), got {er_ded_2}"

        # 4. Test Case 3: Mid-month Joiner
        print("\n--- Test Case 3: Mid-month Joiner (12 days, Wage 2,000 -> Avg 166.67 <= 176) ---")
        mid_emp = env['hr.employee'].new({
            'name': 'Mid-Month Joiner',
            'contract_date_start': datetime.date(2026, 9, 19),
            'company_id': emp.company_id.id,
        })
        slip_3 = env['hr.payslip'].new({
            'employee_id': mid_emp,
            'date_from': datetime.date(2026, 9, 1),
            'date_to': datetime.date(2026, 9, 30),
            'company_id': emp.company_id.id,
        })
        is_exempt_3, avg_wage_3, paid_days_3, thresh_3 = ee_calc.check_daily_wage_exemption(slip_3, esic_wage=2000.0)
        ee_ded_3 = ee_calc.compute(slip_3, esic_wage=2000.0)
        er_ded_3 = er_calc.compute(slip_3, esic_wage=2000.0)
        print(f"Paid Days: {paid_days_3} (expected 12), Wage: 2,000, Avg Daily Wage: {avg_wage_3}")
        print(f"Is Exempt: {is_exempt_3}, EE ESIC: {ee_ded_3}, ER ESIC: {er_ded_3}")
        assert paid_days_3 == 12.0, f"Expected 12 paid days for mid-month joiner, got {paid_days_3}"
        assert is_exempt_3, "Mid-month joiner with 166.67 daily wage MUST be exempt"
        assert ee_ded_3 == 0.0, f"Expected EE ESIC 0.0, got {ee_ded_3}"
        assert er_ded_3 == 65.0, f"Expected ER ESIC 65.0 (3.25% of 2,000), got {er_ded_3}"

        # 5. Test Case 4: Heavy LOP / Unpaid Leave
        print("\n--- Test Case 4: Heavy LOP (5 days worked, Wage 800 -> Avg 160.0 <= 176) ---")
        slip_4 = env['hr.payslip'].create({
            'name': 'Test Payslip LOP Rule 51-B',
            'employee_id': emp.id,
            'date_from': datetime.date(2026, 9, 1),
            'date_to': datetime.date(2026, 9, 30),
            'company_id': emp.company_id.id,
            'worked_days_line_ids': [
                (0, 0, {'name': 'Attendance', 'code': 'WORK100', 'number_of_days': 5, 'number_of_hours': 40}),
                (0, 0, {'name': 'Unpaid Leave', 'code': 'LOP', 'number_of_days': 25, 'number_of_hours': 200}),
            ]
        })
        paid_days_4 = ee_calc.get_paid_days(slip_4)
        is_exempt_4, avg_wage_4, _, _ = ee_calc.check_daily_wage_exemption(slip_4, esic_wage=800.0)
        ee_ded_4 = ee_calc.compute(slip_4, esic_wage=800.0)
        er_ded_4 = er_calc.compute(slip_4, esic_wage=800.0)
        print(f"Paid Days: {paid_days_4} (expected 5), Wage: 800, Avg Daily Wage: {avg_wage_4}")
        print(f"Is Exempt: {is_exempt_4}, EE ESIC: {ee_ded_4}, ER ESIC: {er_ded_4}")
        assert paid_days_4 == 5.0, f"Expected 5 paid days after 25 days LOP, got {paid_days_4}"
        assert is_exempt_4, "Heavy LOP with avg daily wage 160 MUST be exempt"
        assert ee_ded_4 == 0.0, f"Expected EE ESIC 0.0, got {ee_ded_4}"
        assert er_ded_4 == 26.0, f"Expected ER ESIC 26.0 (3.25% of 800), got {er_ded_4}"

        # 6. Test Case 5: Audit Session & Payslip Snapshot Persistence
        print("\n--- Test Case 5: Audit Session & Payslip Snapshot Persistence ---")
        esic_svc_with_wage = ESICService(env, localdict={'ESIC_WAGE': 800.0})
        deduction_computed = esic_svc_with_wage.compute_esic_employee(slip_4)
        print(f"Computed Deduction via Service: {deduction_computed}")
        print(f"Snapshot Exempt Field: {slip_4.hds_in_esic_daily_wage_exempt}")
        print(f"Snapshot Avg Daily Wage: {slip_4.hds_in_esic_average_daily_wage}")
        print(f"Snapshot Paid Days: {slip_4.hds_in_esic_paid_days}")
        assert deduction_computed == 0.0
        assert slip_4.hds_in_esic_daily_wage_exempt is True
        assert slip_4.hds_in_esic_average_daily_wage == 160.0
        assert slip_4.hds_in_esic_paid_days == 5.0

        # Roll back changes so database remains clean
        cr.rollback()
        print("\n>>> ALL RULE 51-B ESIC EXEMPTION TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == '__main__':
    run_tests()
