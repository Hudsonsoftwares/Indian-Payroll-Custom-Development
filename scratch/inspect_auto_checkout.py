import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    company_fields = [f for f in env['res.company']._fields if 'auto' in f or 'check' in f or 'tolerance' in f]
    print('res.company fields:', company_fields)
    
    comp = env['res.company'].search([], limit=1)
    for f in company_fields:
        print(f"  {f}: {getattr(comp, f, None)}")

    att_fields = [f for f in env['hr.attendance']._fields if 'auto' in f or 'check' in f]
    print('hr.attendance fields:', att_fields)

    crons = env['ir.cron'].search([('model_id.model', 'in', ['hr.attendance', 'res.company', 'hr.employee'])])
    print('Crons:')
    for c in crons:
        print(f"  - {c.name} (active={c.active}): code={c.code}")

    # Also inspect res.config.settings for attendance
    config_fields = [f for f in env['res.config.settings']._fields if 'auto' in f or 'tolerance' in f]
    print('res.config.settings fields:', config_fields)
