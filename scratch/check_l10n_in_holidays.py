import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
reg = odoo.modules.registry.Registry('RevisedPayroll')
with reg.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env['ir.ui.menu'].search([('name', 'ilike', 'Optional%')])
    for m in menu:
        print("Menu ID:", m.id, "Name:", m.name, "Action:", m.action)
        if m.action and m.action._name == 'ir.actions.act_window':
            print("  Res Model:", m.action.res_model)
            print("  Views:", m.action.views)

    # Let's see how l10n_in_hr_holidays works:
    if 'l10n_in.hr.leave.optional.holiday' in env:
        opt_model = env['l10n_in.hr.leave.optional.holiday']
        print("\nModel l10n_in.hr.leave.optional.holiday exists!")
        print("Fields:", list(opt_model._fields.keys()))
        records = opt_model.search([])
        print("Count:", len(records))
        for r in records[:10]:
            print(f"  ID: {r.id}, Name: {r.name}, Date: {r.date}")
