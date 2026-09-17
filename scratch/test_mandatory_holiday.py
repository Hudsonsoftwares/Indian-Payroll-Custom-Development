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
        print("=== TEST TIME OFF MANDATORY HOLIDAY CONNECTION ===")

        # 1. Verify Model & Views
        print("\n--- Test Case 1: Field & View Inspection ---")
        LeaveModel = env['resource.calendar.leaves']
        assert 'is_mandatory' in LeaveModel._fields, "is_mandatory field must exist on resource.calendar.leaves"
        print("[Check] is_mandatory field exists on resource.calendar.leaves: OK")

        form_v = env['ir.ui.view'].search([('name', '=', 'resource.calendar.leaves.form.inherit.mandatory')], limit=1)
        tree_v = env['ir.ui.view'].search([('name', '=', 'resource.calendar.leaves.tree.inherit.mandatory')], limit=1)
        print("[Check] Form View extension installed:", bool(form_v))
        print("[Check] Tree View extension installed:", bool(tree_v))
        assert form_v and tree_v, "Both form and tree view extensions must be installed in Odoo"

        # 2. Test Mandatory vs Optional Holiday Dynamics
        print("\n--- Test Case 2: Mandatory vs Optional Holiday Dynamics ---")
        emp = env['hr.employee'].search([('name', 'ilike', 'Devipriya')], limit=1)
        if not emp:
            emp = env['hr.employee'].search([], limit=1)

        cal = emp.resource_calendar_id or env['resource.calendar'].search([], limit=1)
        tz = pytz.timezone(cal.tz or 'UTC')

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

        date_from = datetime.date(2026, 6, 1)
        date_to = datetime.date(2026, 6, 30)

        slip = env['hr.payslip'].new({
            'employee_id': emp.id,
            'date_from': date_from,
            'date_to': date_to,
        })

        if hasattr(env, '_attendance_cache') and isinstance(env._attendance_cache, dict):
            env._attendance_cache.clear()

        # Baseline: Normal month without holidays
        baseline = slip._get_attendance_vs_schedule(contract, date_from, date_to)
        base_days = baseline['scheduled_days']
        base_hours = baseline['scheduled_hours']
        print(f"Baseline (No Holidays): {base_days} days, {base_hours} hrs")

        # Create Mandatory Holiday on 2026-06-15 (Monday)
        dt_mand_start = tz.localize(datetime.datetime(2026, 6, 15, 0, 0, 0)).astimezone(pytz.UTC).replace(tzinfo=None)
        dt_mand_end = tz.localize(datetime.datetime(2026, 6, 15, 23, 59, 59)).astimezone(pytz.UTC).replace(tzinfo=None)

        mand_holiday = env['resource.calendar.leaves'].create({
            'name': 'Republic Day / National Mandatory Holiday',
            'calendar_id': cal.id,
            'date_from': dt_mand_start,
            'date_to': dt_mand_end,
            'is_mandatory': True,
        })

        # Create Optional / Floating Holiday on 2026-06-16 (Tuesday)
        dt_opt_start = tz.localize(datetime.datetime(2026, 6, 16, 0, 0, 0)).astimezone(pytz.UTC).replace(tzinfo=None)
        dt_opt_end = tz.localize(datetime.datetime(2026, 6, 16, 23, 59, 59)).astimezone(pytz.UTC).replace(tzinfo=None)

        opt_holiday = env['resource.calendar.leaves'].create({
            'name': 'Optional / Floating Holiday',
            'calendar_id': cal.id,
            'date_from': dt_opt_start,
            'date_to': dt_opt_end,
            'is_mandatory': False,
        })

        if hasattr(env, '_attendance_cache') and isinstance(env._attendance_cache, dict):
            env._attendance_cache.clear()

        result = slip._get_attendance_vs_schedule(contract, date_from, date_to)
        print(f"With 1 Mandatory + 1 Optional: {result['scheduled_days']} days, {result['scheduled_hours']} hrs")

        # Crucial checks:
        # ONLY Mandatory holiday should reduce scheduled company days (1 day reduction, NOT 2)
        assert result['scheduled_days'] == base_days - 1.0, f"Expected {base_days - 1.0} days, got {result['scheduled_days']}"
        assert result['scheduled_hours'] == base_hours - 8.0, f"Expected {base_hours - 8.0} hrs, got {result['scheduled_hours']}"

        # Check day-specific behavior:
        # On Mandatory Holiday (2026-06-15): Scheduled hours = 0.0, Shortage = 0.0
        if hasattr(env, '_attendance_cache') and isinstance(env._attendance_cache, dict):
            env._attendance_cache.clear()
        mand_day = slip._get_attendance_vs_schedule(contract, datetime.date(2026, 6, 15), datetime.date(2026, 6, 15))
        print(f"Mandatory Holiday Day: Scheduled = {mand_day['scheduled_hours']}, Shortage = {mand_day['shortage_hours_delta']}")
        assert mand_day['scheduled_hours'] == 0.0
        assert mand_day['shortage_hours_delta'] == 0.0

        # On Optional Holiday (2026-06-16): Scheduled hours = 8.0 (Normal day unless individual applies for leave)
        if hasattr(env, '_attendance_cache') and isinstance(env._attendance_cache, dict):
            env._attendance_cache.clear()
        opt_day = slip._get_attendance_vs_schedule(contract, datetime.date(2026, 6, 16), datetime.date(2026, 6, 16))
        print(f"Optional Holiday Day: Scheduled = {opt_day['scheduled_hours']}, Shortage = {opt_day['shortage_hours_delta']}")
        assert opt_day['scheduled_hours'] == 8.0
        assert opt_day['shortage_hours_delta'] == 8.0  # Absent without leave triggers shortage

        # Rollback so DB remains pristine
        cr.rollback()
        print("\n>>> ALL MANDATORY HOLIDAY & TIME OFF CONNECTION TESTS PASSED! <<<")

if __name__ == '__main__':
    run_tests()
