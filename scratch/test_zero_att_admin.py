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
    
    # Check Dec attendances
    att = env['hr.attendance'].search([
        ('employee_id', '=', admin.id),
        ('check_in', '>=', '2026-12-01 00:00:00'),
        ('check_in', '<=', '2026-12-31 23:59:59')
    ])
    print(f"Deleting {len(att)} attendances in Dec 2026 for Administrator...")
    att.unlink()
    
    # Recompute slip 187
    slip = env['hr.payslip'].browse(187)
    slip.compute_sheet()
    
    print("\n--- After 0 attendance in Dec 2026 ---")
    for l in slip.line_ids:
        if 'LWF' in l.code or l.code in ('BASIC', 'NET', 'GROSS'):
            print(f"  {l.code} ({l.name}): total={l.total}")
    for w in slip.worked_days_line_ids:
        print(f"  WorkedDay: {w.code} ({w.name}): days={w.number_of_days}, hours={w.number_of_hours}")
    
    # cr.commit() so changes are saved in DB
    cr.commit()
    print("Committed successfully!")
