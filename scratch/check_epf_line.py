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
    slip = env['hr.payslip'].browse(388)
    line = slip.line_ids.filtered(lambda l: l.code == 'EPF')
    print("EPF Line on Slip 388:", line.name, line.total, line.amount)
    
    # Check rule for EPF
    rule = line.salary_rule_id
    print("Rule:", rule.code, rule.amount_select, rule.amount_python_compute)
