import sys
from datetime import datetime, timedelta
import pytz

sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
registry = odoo.modules.registry.Registry('RevisedPayroll')

with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    
    print("=== STARTING ATTENDANCE AUTO-CLOSE & GPS VALIDATION TESTS ===")

    # Check existing open attendances in DB
    open_atts = env['hr.attendance'].search([('check_out', '=', False)])
    print(f"Total open attendances currently in DB: {len(open_atts)}")
    for a in open_atts[:5]:
        print(f"  - Emp: {a.employee_id.name}, Check-in: {a.check_in}, ID: {a.id}")

    # Pick an employee without an open attendance, or test closing open ones
    closed_emp_ids = env['hr.employee'].search([('active', '=', True)]).ids
    open_emp_ids = open_atts.mapped('employee_id').ids
    avail_emp_ids = [eid for eid in closed_emp_ids if eid not in open_emp_ids]
    
    if avail_emp_ids:
        emp = env['hr.employee'].browse(avail_emp_ids[0])
    else:
        emp = env['hr.employee'].search([('active', '=', True)], limit=1)
        # Close open attendance for test
        open_atts.filtered(lambda a: a.employee_id.id == emp.id).write({'check_out': datetime.utcnow() - timedelta(days=2)})
    print(f"Selected test employee: {emp.name} (ID: {emp.id})")

    # 1. Test HR Manual Attendance Check-In without GPS (Must NOT raise ValidationError)
    print("\n[Test 1] Testing HR Manual Attendance Check-In without GPS...")
    now_utc = datetime.utcnow()
    check_in_time = now_utc - timedelta(hours=9)

    att = env['hr.attendance'].create({
        'employee_id': emp.id,
        'check_in': check_in_time,
        # in_latitude and in_longitude intentionally omitted (as in standard backend form)
    })
    print(f"SUCCESS: HR Manual Attendance created with ID: {att.id}, check_in: {att.check_in}")

    # 2. Test Auto Check-Out Hook & GPS Bypass
    print("\n[Test 2] Testing Auto Check-Out write & Missing Punch hook...")
    auto_checkout_time = check_in_time + timedelta(hours=8)
    att.write({
        'check_out': auto_checkout_time,
        'out_mode': 'auto_check_out',
        # out_latitude and out_longitude omitted
    })
    print(f"SUCCESS: Auto Check-Out written without GPS error. check_out: {att.check_out}, out_mode: {att.out_mode}")

    # Verify Anomaly was created
    anomaly = env['hudson.attendance.anomaly'].search([('attendance_id', '=', att.id)], limit=1)
    assert anomaly, "FAILED: hudson.attendance.anomaly was not created!"
    print(f"SUCCESS: Anomaly created! Name: '{anomaly.name}', Type: '{anomaly.anomaly_type}', Desc: '{anomaly.description}'")

    # Verify Regularization was created
    reg = env['hudson.attendance.regularization'].search([('attendance_id', '=', att.id)], limit=1)
    assert reg, "FAILED: hudson.attendance.regularization was not created!"
    print(f"SUCCESS: Draft Regularization created! ID: {reg.id}, State: '{reg.state}', Orig Check-out: {reg.orig_check_out}, Corrected Check-out: {reg.corrected_check_out}")
    assert reg.orig_check_out == False, "FAILED: orig_check_out should be False to indicate missing punch!"
    assert reg.state == 'draft', "FAILED: regularization should be in draft state!"

    # 3. Test Cron Past Day Auto-Close
    print("\n[Test 3] Testing Cron Auto-Close for an open attendance from yesterday...")
    yesterday_checkin = now_utc - timedelta(days=1, hours=8)
    att_past = env['hr.attendance'].create({
        'employee_id': emp.id,
        'check_in': yesterday_checkin,
    })
    print(f"Created past open attendance ID: {att_past.id}, check_in: {att_past.check_in}, check_out: {att_past.check_out}")

    # Run the audit cron
    env['hr.attendance']._cron_check_attendance_anomalies()
    att_past.invalidate_recordset()
    print(f"After cron: check_out: {att_past.check_out}, out_mode: {att_past.out_mode}")
    assert att_past.check_out, "FAILED: Past attendance was not auto-closed by cron!"
    assert att_past.out_mode == 'auto_check_out', f"FAILED: out_mode is {att_past.out_mode}, expected 'auto_check_out'"

    anomaly_past = env['hudson.attendance.anomaly'].search([('attendance_id', '=', att_past.id)], limit=1)
    reg_past = env['hudson.attendance.regularization'].search([('attendance_id', '=', att_past.id)], limit=1)
    assert anomaly_past, "FAILED: Anomaly not created for past attendance!"
    assert reg_past, "FAILED: Regularization not created for past attendance!"
    print(f"SUCCESS: Past open attendance was auto-closed and draft regularization created! ID: {reg_past.id}")

    # 4. Rollback transaction so test data is not left in DB
    cr.rollback()
    print("\n=== ALL TESTS PASSED SUCCESSFULLY! Transaction cleanly rolled back. ===")
