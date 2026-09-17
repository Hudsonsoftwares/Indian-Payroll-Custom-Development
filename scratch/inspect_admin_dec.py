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
    admin = env['hr.employee'].search([('name', 'ilike', 'Administrator')], limit=1)
    print(f"Admin ID: {admin.id}, Name: {admin.name}")
    print(f"LWF Applicable: {admin.hds_in_lwf_applicable}")
    print(f"Company: {admin.company_id.name}, Enable LWF: {admin.company_id.hds_in_enable_lwf}")
    
    # Check attendance in Dec 2026
    att = env['hr.attendance'].search([
        ('employee_id', '=', admin.id),
        ('check_in', '>=', '2026-12-01 00:00:00'),
        ('check_in', '<=', '2026-12-31 23:59:59')
    ])
    print(f"Attendance count in Dec 2026: {len(att)}")
    for a in att:
        print(f"  Attendance: in={a.check_in}, out={a.check_out}, worked={a.worked_hours}")
    
    # Check payslips
    slips = env['hr.payslip'].search([
        ('employee_id', '=', admin.id),
        ('date_from', '>=', '2026-12-01'),
        ('date_to', '<=', '2026-12-31')
    ])
    for s in slips:
        print(f"\nSlip ID: {s.id}, Name: {s.name}, Period: {s.date_from} to {s.date_to}, State: {s.state}")
        lines = {l.code: (l.name, l.total) for l in s.line_ids}
        print("All Lines:")
        for code, (name, tot) in lines.items():
            if 'LWF' in code or code in ('BASIC', 'NET', 'GROSS', 'TOTAL_DEDUCTION'):
                print(f"  {code} ({name}): {tot}")
        worked = [(w.work_entry_type_id.code, w.number_of_days, w.number_of_hours) for w in s.worked_days_line_ids]
        print(f"Worked Days: {worked}")
