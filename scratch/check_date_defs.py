import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']
    # Let's inspect what contract_date_start and date_start are on hr.employee
    print("contract_date_start field:", Employee._fields.get('contract_date_start'))
    print("date_start field:", Employee._fields.get('date_start'))
    print("first_contract_date field:", Employee._fields.get('first_contract_date'))
    print("date_version field:", Employee._fields.get('date_version'))
