import os
import sys

# Add Odoo server path to sys.path
server_path = r"C:\Program Files\Odoo 19.0.20260717\server"
if server_path not in sys.path:
    sys.path.insert(0, server_path)

import odoo
from odoo import api, fields
from odoo.tools import config

from odoo.modules.registry import Registry

config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
registry = Registry('RevisedPayroll')

card_types_to_test = [
    'total_payroll_cost',
    'total_net_pay',
    'active_employee_count',
    'missing_pan',
    'missing_bank',
    'pending_declarations',
    'attendance_exceptions',
    'final_settlements_due',
    'new_joiners',
    'pending_actions',
    'epf_status',
    'esic_status',
    'lwf_status',
    'readiness_status',
    'old_regime',
    'new_regime',
    'aadhaar_health',
    'contact_health',
    'tds_this_month',
    'pt_liability',
]

with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    dash_model = env['hds.payroll.dashboard']
    dash = dash_model.search([], limit=1)
    dash_id = dash.id if dash else None
    
    print(f"Testing dash_id={dash_id}")
    
    for ctype in card_types_to_test:
        try:
            res = dash_model.get_card_details(dashboard_id=dash_id, card_type=ctype)
            print(f"SUCCESS: {ctype:22} | Title: {res['title'][:30]:30} | Rows: {len(res['rows']):3} | Cols: {len(res['columns'])}")
        except Exception as e:
            print(f"FAILED:  {ctype:22} | Error: {e}")
