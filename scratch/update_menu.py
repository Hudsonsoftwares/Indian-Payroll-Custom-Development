import sys
sys.path.append('C:/Program Files/Odoo 19.0.20260717/server')
import odoo
from odoo.tools import config
from odoo.modules.registry import Registry

config.parse_config(['-c', 'C:/Program Files/Odoo 19.0.20260717/server/odoo.conf'])

registry = Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    Menu = env['ir.ui.menu'].with_context(active_test=False)
    
    menu_root = Menu.browse(178) # env.ref('hudson_payroll_base.menu_hr_payroll_root')
    menu_work_entries = Menu.browse(473) # env.ref('hudson_payroll_base.menu_hr_payroll_work_entries')
    menu_time_off = Menu.browse(475) # env.ref('hudson_payroll_base.menu_action_hr_payroll_time_off')
    menu_work_entry_action = Menu.browse(474) # env.ref('hudson_payroll_base.menu_action_hr_work_entry')

    print(f"menu_root: {menu_root} (name={menu_root.name})")
    print(f"menu_work_entries (now Time Off parent): {menu_work_entries} (active={menu_work_entries.active})")
    print(f"menu_time_off (child): {menu_time_off} (active={menu_time_off.active})")
    print(f"menu_work_entry_action: {menu_work_entry_action}")

    # 1. Make menu_work_entries active, named 'Time Off', under menu_root
    menu_work_entries.write({
        'name': 'Time Off',
        'parent_id': menu_root.id,
        'sequence': 10,
        'active': True,
        'action': False,
    })
    print("Updated menu_work_entries (473) as parent Time Off")

    # 2. Make menu_time_off child of menu_work_entries (473)
    menu_time_off.write({
        'name': 'Time Off',
        'parent_id': menu_work_entries.id,
        'sequence': 10,
        'active': True,
    })
    print("Updated menu_time_off (475) as child of Time Off (473)")

    # 3. Ensure work entry action is inactive so it doesn't show up
    if menu_work_entry_action.exists():
        menu_work_entry_action.write({'active': False})
        print("Deactivated menu_action_hr_work_entry (474)")

    env.invalidate_all()
    registry.clear_cache()
    registry.signal_changes()
    cr.commit()
    print("SUCCESSFULLY COMMITTED!")
