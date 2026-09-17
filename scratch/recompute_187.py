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
    slip = env['hr.payslip'].browse(187)
    
    # Check why EPF was 0.0 when compute_sheet ran
    slip.compute_sheet()
    
    for l in slip.line_ids:
        if 'PF' in l.code or 'EPF' in l.code:
            print(f"  {l.code} ({l.name}): {l.total}")
