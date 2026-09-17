import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
reg = odoo.modules.registry.Registry('RevisedPayroll')
with reg.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT imd.module, imd.name, imd.model 
        FROM ir_model_data imd 
        WHERE imd.name LIKE '%optional%'
    """)
    print("ir_model_data matches for optional:")
    for row in cr.fetchall():
        print(" ", row)

    print("\nCheck resource.calendar.leaves views and fields in standard:")
    rcl = env['resource.calendar.leaves']
    for k, v in rcl._fields.items():
        print(f"  {k}: {v.type} ({type(v)})")
