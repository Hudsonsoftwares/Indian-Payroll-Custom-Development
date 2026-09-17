import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
reg = odoo.modules.registry.Registry('RevisedPayroll')
with reg.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})

    print("=== TEST 1: ABSENT EMPLOYEE (Administrator - Payslip 187) ===")
    p187 = env['hr.payslip'].browse(187)
    p187.compute_sheet()
    print(f"Payslip {p187.id}: {p187.name}")
    print("Worked Days Lines:")
    for wd in p187.worked_days_line_ids:
        print(f"  [{wd.code}] {wd.name}: {wd.number_of_days} days, {wd.number_of_hours} hrs")
    print(f"Total Worked Days: {p187.total_worked_days}")
    print(f"Total Worked Hours: {p187.total_worked_hours}")
    print(f"Total Scheduled Days: {p187.total_scheduled_days}")
    print(f"Expected Hours: {p187.attendance_expected_hours}")

    work_line = p187.worked_days_line_ids.filtered(lambda l: l.code == 'WORK100')
    assert work_line.number_of_days == 22.0, f"WORK100 days must be 22.0, got {work_line.number_of_days}"
    assert work_line.number_of_hours == 176.0, f"WORK100 hours must be 176.0, got {work_line.number_of_hours}"
    assert p187.total_worked_days == 0.0, f"total_worked_days must be 0.0, got {p187.total_worked_days}"
    assert p187.total_worked_hours == 0.0, f"total_worked_hours must be 0.0, got {p187.total_worked_hours}"
    assert p187.total_scheduled_days == 22.0, f"total_scheduled_days must be 22.0, got {p187.total_scheduled_days}"
    assert p187.attendance_expected_hours == 176.0, f"attendance_expected_hours must be 176.0, got {p187.attendance_expected_hours}"
    print(">>> TEST 1 PASSED! <<<")

    print("\n=== TEST 2: SALARIED EMPLOYEE (Prince Shaji - Payslip 188) ===")
    p188 = env['hr.payslip'].browse(188)
    p188.compute_sheet()
    print(f"Payslip {p188.id}: {p188.name}")
    print(f"Total Worked Days: {p188.total_worked_days}")
    print(f"Total Worked Hours: {p188.total_worked_hours}")
    print(f"Total Scheduled Days: {p188.total_scheduled_days}")
    print(f"Expected Hours: {p188.attendance_expected_hours}")
    assert p188.total_worked_days == 22.0, f"total_worked_days must be 22.0, got {p188.total_worked_days}"
    assert p188.total_worked_hours == 176.0, f"total_worked_hours must be 176.0, got {p188.total_worked_hours}"
    assert p188.total_scheduled_days == 22.0, f"total_scheduled_days must be 22.0, got {p188.total_scheduled_days}"
    assert p188.attendance_expected_hours == 176.0, f"attendance_expected_hours must be 176.0, got {p188.attendance_expected_hours}"
    print(">>> TEST 2 PASSED! <<<")

    print("\n=== TEST 3: PARTIAL SHORTAGE (Payslip 189 - 11 hrs shortage) ===")
    p189 = env['hr.payslip'].browse(189)
    p189.compute_sheet()
    print(f"Payslip {p189.id}: {p189.name}")
    print(f"Total Worked Days: {p189.total_worked_days}")
    print(f"Total Worked Hours: {p189.total_worked_hours}")
    print(f"Total Scheduled Days: {p189.total_scheduled_days}")
    print(f"Expected Hours: {p189.attendance_expected_hours}")
    assert p189.total_worked_hours == 165.0, f"total_worked_hours must be 165.0, got {p189.total_worked_hours}"
    assert abs(p189.total_worked_days - 20.625) < 0.01, f"total_worked_days must be ~20.625, got {p189.total_worked_days}"
    print(">>> TEST 3 PASSED! <<<")

    cr.rollback()
