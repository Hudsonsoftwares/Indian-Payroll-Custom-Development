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
    
    print(f"Administrator hds_in_epf_applicable = {admin.hds_in_epf_applicable}")
    print(f"Company hds_in_epf_applicable = {admin.company_id.hds_in_epf_applicable}")
    
    # Check slip 187
    slip = env['hr.payslip'].browse(187)
    
    # Save admin.hds_in_epf_applicable = True in DB
    admin.hds_in_epf_applicable = True
    cr.commit()
    print("Saved admin.hds_in_epf_applicable = True in DB!")
