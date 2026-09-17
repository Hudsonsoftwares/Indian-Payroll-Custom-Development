import sys
import os
import datetime
import pytz

# Add odoo paths
odoo_server = r"C:\Program Files\Odoo 19.0.20260717\server"
if odoo_server not in sys.path:
    sys.path.insert(0, odoo_server)

import odoo
from odoo import api, fields, SUPERUSER_ID

def run_tests():
    odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
    registry = odoo.modules.registry.Registry('RevisedPayroll')

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        print("=== TEST ATTENDANCE & PAYROLL LINK WORKING SCHEDULE DYNAMICS ===")

        # 1. Verify View Changes (Settings View & Contract Form View)
        print("\n--- Test Case 1: UI View Inspection ---")
        settings_view = env['ir.ui.view'].search([
            ('name', '=', 'res.config.settings.view.form.inherit.hudson.attendance.payroll.link')
        ], limit=1)
        if settings_view:
            arch = settings_view.arch
            print("[Check] standard_working_days_setting in Settings view:", 'standard_working_days_setting' in arch)
            print("[Check] standard_hours_per_day_setting in Settings view:", 'standard_hours_per_day_setting' in arch)
            assert 'standard_working_days_setting' not in arch, "standard_working_days_setting should be REMOVED from settings view"
            assert 'standard_hours_per_day_setting' not in arch, "standard_hours_per_day_setting should be REMOVED from settings view"
        else:
            print("[Warning] settings_view not found by name, will verify after upgrade")

        contract_view = env['ir.ui.view'].search([
            ('name', '=', 'hr.version.view.form.inherit.rates')
        ], limit=1)
        if contract_view:
            arch = contract_view.arch
            print("[Check] standard_working_days_per_month in Contract view:", 'standard_working_days_per_month' in arch)
            print("[Check] standard_hours_per_day in Contract view:", 'standard_hours_per_day' in arch)
            assert 'standard_working_days_per_month' not in arch, "standard_working_days_per_month should be REMOVED from contract view"
            assert 'standard_hours_per_day' not in arch, "standard_hours_per_day should be REMOVED from contract view"

        # 2. Test Dynamic Schedule & Public Holiday Awareness
        print("\n--- Test Case 2: Schedule & Public Holiday Awareness ---")
        # Find employee & calendar
        emp = env['hr.employee'].search([('name', 'ilike', 'Devipriya')], limit=1)
        if not emp:
            emp = env['hr.employee'].search([], limit=1)

        cal = emp.resource_calendar_id or env['resource.calendar'].search([], limit=1)
        print(f"Employee: {emp.name}, Calendar: {cal.name}, Hours/Day: {cal.hours_per_day}")

        contract = env['hr.version'].search([('employee_id', '=', emp.id)], limit=1)
        if not contract:
            contract = env['hr.version'].create({
                'name': f'Test Contract {emp.name}',
                'employee_id': emp.id,
                'wage': 50000.0,
                'resource_calendar_id': cal.id,
                'pay_by_attendance': True,
                'salary_calculation_type': 'fixed',
            })
        else:
            contract.write({
                'wage': 50000.0,
                'resource_calendar_id': cal.id,
                'pay_by_attendance': True,
                'salary_calculation_type': 'fixed',
            })

        # June 2026: 2026-06-01 to 2026-06-30
        date_from = datetime.date(2026, 6, 1)
        date_to = datetime.date(2026, 6, 30)

        # A: Standard June month without public holiday
        slip_mock = env['hr.payslip'].new({
            'employee_id': emp.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        data_normal = slip_mock._get_attendance_vs_schedule(contract, date_from, date_to)
        sched_hours_normal = data_normal['scheduled_hours']
        sched_days_normal = data_normal['scheduled_days']
        hourly_rate_normal = contract.get_period_shortage_rate(date_from, date_to)
        day_rate_normal = contract.get_period_day_rate(date_from, date_to)
        print(f"June 2026 Normal: Scheduled Hours = {sched_hours_normal}, Scheduled Days = {sched_days_normal}")
        print(f"Normal Hourly Rate: INR {hourly_rate_normal:.2f}, Normal Day Rate: INR {day_rate_normal:.2f}")

        # B: Now add a Public Holiday on Monday 2026-06-15
        tz = pytz.timezone(cal.tz or 'UTC')
        dt_holiday_start = tz.localize(datetime.datetime(2026, 6, 15, 0, 0, 0)).astimezone(pytz.UTC).replace(tzinfo=None)
        dt_holiday_end = tz.localize(datetime.datetime(2026, 6, 15, 23, 59, 59)).astimezone(pytz.UTC).replace(tzinfo=None)

        holiday = env['resource.calendar.leaves'].create({
            'name': 'Test Statutory Public Holiday',
            'calendar_id': cal.id,
            'date_from': dt_holiday_start,
            'date_to': dt_holiday_end,
        })

        # Clear attendance cache to force recomputation with the holiday
        if hasattr(env, '_attendance_cache') and isinstance(env._attendance_cache, dict):
            env._attendance_cache.clear()

        data_holiday = slip_mock._get_attendance_vs_schedule(contract, date_from, date_to)
        sched_hours_holiday = data_holiday['scheduled_hours']
        sched_days_holiday = data_holiday['scheduled_days']
        hourly_rate_holiday = contract.get_period_shortage_rate(date_from, date_to)
        day_rate_holiday = contract.get_period_day_rate(date_from, date_to)
        print(f"\nJune 2026 with Public Holiday: Scheduled Hours = {sched_hours_holiday}, Scheduled Days = {sched_days_holiday}")
        print(f"Holiday Hourly Rate: INR {hourly_rate_holiday:.2f}, Holiday Day Rate: INR {day_rate_holiday:.2f}")

        # Assertions
        assert sched_hours_holiday < sched_hours_normal, f"Scheduled hours should decrease with holiday: {sched_hours_holiday} vs {sched_hours_normal}"
        assert sched_days_holiday == sched_days_normal - 1.0, f"Scheduled days should decrease by 1: {sched_days_holiday} vs {sched_days_normal}"
        assert hourly_rate_holiday > hourly_rate_normal, f"Hourly rate should adjust upwards due to fewer scheduled hours: {hourly_rate_holiday} vs {hourly_rate_normal}"
        assert day_rate_holiday > day_rate_normal, f"Day rate should adjust upwards due to fewer scheduled days: {day_rate_holiday} vs {day_rate_normal}"

        # C: Check that on the Public Holiday itself, absence does NOT trigger shortage
        print("\n--- Test Case 3: Public Holiday Absence Does NOT Trigger Shortage ---")
        # Evaluate for the holiday day alone
        holiday_date = datetime.date(2026, 6, 15)
        if hasattr(env, '_attendance_cache') and isinstance(env._attendance_cache, dict):
            env._attendance_cache.clear()
        data_holiday_day = slip_mock._get_attendance_vs_schedule(contract, holiday_date, holiday_date)
        print(f"Holiday Day (2026-06-15) Scheduled Hours: {data_holiday_day['scheduled_hours']}")
        print(f"Holiday Day Shortage Hours: {data_holiday_day['shortage_hours_delta']}")
        assert data_holiday_day['scheduled_hours'] == 0.0, f"Scheduled hours on holiday must be 0.0, got {data_holiday_day['scheduled_hours']}"
        assert data_holiday_day['shortage_hours_delta'] == 0.0, f"Shortage on public holiday must be 0.0, got {data_holiday_day['shortage_hours_delta']}"

        # Rollback so database stays pristine
        cr.rollback()
        print("\n>>> ALL WORKING SCHEDULE & PUBLIC HOLIDAY TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == '__main__':
    run_tests()
