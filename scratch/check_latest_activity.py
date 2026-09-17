import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID

config_file = r"C:\Program Files\Odoo 19.0.20260717\server\odoo.conf"
odoo.tools.config.parse_config(['-c', config_file, '-d', 'RevisedPayroll'])
from odoo.modules.registry import Registry
registry = Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    print("=== LATEST 5 PAYSLIPS MODIFIED ===")
    for s in env['hr.payslip'].search([], order='write_date desc', limit=5):
        print(f"Slip {s.id}: {s.name}, Emp: {s.employee_id.name}, State: {s.state}, WriteDate: {s.write_date}, CreateDate: {s.create_date}")
        for l in s.line_ids:
            if 'LWF' in l.code or l.code in ('BASIC', 'NET', 'GROSS'):
                print(f"   Line: {l.code} = {l.total}")
        for w in s.worked_days_line_ids:
            print(f"   WorkedDay: {w.name} ({w.code}) days={w.number_of_days} hours={w.number_of_hours} amount={w.amount}")

    print("\n=== LATEST ATTENDANCES ===")
    for a in env['hr.attendance'].search([], order='write_date desc', limit=5):
        print(f"Att {a.id}: Emp: {a.employee_id.name}, In: {a.check_in}, Out: {a.check_out}, Hours: {a.worked_hours}, WriteDate: {a.write_date}")
