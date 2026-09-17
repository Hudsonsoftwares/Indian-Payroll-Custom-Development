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
    print("=== RECENT PAYSLIPS ===")
    slips = env['hr.payslip'].search([], order='write_date desc, id desc', limit=5)
    for s in slips:
        print(f"Payslip: {s.number or s.name} (ID: {s.id}), Employee: {s.employee_id.name} (ID: {s.employee_id.id}), Contract: {s.contract_id.name} (ID: {s.contract_id.id}), State: {s.state}, WriteDate: {s.write_date}")
        for l in s.line_ids:
            if 'FIXED' in l.code or 'allowance' in l.name.lower() or 'EARN' in l.category_id.code:
                print(f"   Line: {l.code} - {l.name}: total={l.total}, appears={l.salary_rule_id.appears_on_payslip}, cat={l.category_id.code}")

    print("\n=== CONTRACTS (hr.version) ===")
    contracts = env['hr.version'].search([], order='write_date desc, id desc', limit=10)
    for c in contracts:
        print(f"Contract ID: {c.id}, Name: {c.name}, Emp: {c.employee_id.name}, wage: {c.wage}, fixed_allowance: {getattr(c, 'fixed_allowance', 'N/A')}, state: {getattr(c, 'state', 'N/A')}, WriteDate: {c.write_date}")

    print("\n=== EMPLOYEES ===")
    employees = env['hr.employee'].search([], order='write_date desc, id desc', limit=5)
    for e in employees:
        print(f"Emp ID: {e.id}, Name: {e.name}, fixed_allowance: {getattr(e, 'fixed_allowance', 'N/A')}")
