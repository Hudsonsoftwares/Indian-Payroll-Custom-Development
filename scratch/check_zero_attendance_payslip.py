import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID
import datetime

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
reg = odoo.modules.registry.Registry('RevisedPayroll')
with reg.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Look for existing payslips
    payslips = env['hr.payslip'].search([], order='id desc', limit=5)
    print("Found payslips:", len(payslips))
    for p in payslips:
        print(f"Payslip {p.id}: {p.name}, Emp: {p.employee_id.name}, Date: {p.date_from} to {p.date_to}, Net: {p.net_wage}")
        for line in p.line_ids:
            if line.code in ['BASIC', 'GROSS', 'NET', 'UNPAID', 'LOP', 'PF', 'ESIC', 'PT', 'TDS', 'SHORTAGE']:
                print(f"    {line.code}: {line.total}")

    # Let's inspect hr.payslip fields and how worked_days are created
    p = payslips[0] if payslips else None
    if p:
        print("\nWorked days on payslip", p.id)
        for wd in p.worked_days_line_ids:
            print(f"  {wd.code}: days={wd.number_of_days}, hrs={wd.number_of_hours}, amt={wd.amount}")
