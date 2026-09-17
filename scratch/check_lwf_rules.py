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
    rule_er = env['hr.salary.rule'].search([('code', '=', 'LWF_ER')])
    rule_ee = env['hr.salary.rule'].search([('code', '=', 'LWF_EE')])
    print("Rule LWF_ER:")
    for r in rule_er:
        print(f"  ID: {r.id}, Name: {r.name}, Appears on payslip: {r.appears_on_payslip}, Active: {r.active}, Amount type: {r.amount_select}, Python code: {r.amount_python_compute}")
    print("Rule LWF_EE:")
    for r in rule_ee:
        print(f"  ID: {r.id}, Name: {r.name}, Appears on payslip: {r.appears_on_payslip}, Active: {r.active}, Amount type: {r.amount_select}, Python code: {r.amount_python_compute}")
