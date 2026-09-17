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
    slips = env['hr.payslip'].search([
        ('date_from', '>=', '2026-12-01'),
        ('date_to', '<=', '2026-12-31')
    ], order='write_date desc, id desc')
    print(f"Total Dec 2026 payslips: {len(slips)}")
    for s in slips:
        emp = s.employee_id
        lwf_lines = [(l.code, l.total) for l in s.line_ids if 'LWF' in l.code]
        net = [(l.code, l.total) for l in s.line_ids if l.code == 'NET']
        print(f"Slip {s.id}: {s.name} | Emp: {emp.name} (LWF App: {emp.hds_in_lwf_applicable}, State: {emp.company_id.state_id.name if emp.company_id.state_id else 'None'}) | State: {s.state} | WriteDate: {s.write_date}")
        print(f"   LWF Lines: {lwf_lines} | NET: {net}")
