import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
reg = odoo.modules.registry.Registry('RevisedPayroll')
with reg.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    p = env['hr.payslip'].browse(363)
    print(f"Payslip {p.id}: {p.name}")
    print(f"Contract wage: {p.contract_id.wage}, Employee: {p.employee_id.name}")
    print("\nWorked Days Lines:")
    for wd in p.worked_days_line_ids:
        print(f"  {wd.code} ({wd.name}): days={wd.number_of_days}, hrs={wd.number_of_hours}, amt={wd.amount}")
        
    print("\nSalary Lines:")
    for line in p.line_ids:
        print(f"  [{line.category_id.code}] {line.code} - {line.name}: {line.total} (rate={line.rate}, amt={line.amount}, qty={line.quantity})")
