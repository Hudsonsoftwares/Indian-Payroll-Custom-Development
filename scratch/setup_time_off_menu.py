import sys
sys.path.append('C:/Program Files/Odoo 19.0.20260717/server')
import odoo
from odoo.tools import config
from odoo.modules.registry import Registry

config.parse_config(['-c', 'C:/Program Files/Odoo 19.0.20260717/server/odoo.conf'])

registry = Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    Menu = env['ir.ui.menu']
    ModelData = env['ir.model.data']
    
    menu_root = env.ref('hudson_payroll_base.menu_hr_payroll_root', raise_if_not_found=False)
    print(f"menu_root: {menu_root}")

    # Check or create menu_hr_payroll_time_off_root
    parent_menu_data = ModelData.search([
        ('module', '=', 'hudson_payroll_base'),
        ('name', '=', 'menu_hr_payroll_time_off_root'),
        ('model', '=', 'ir.ui.menu'),
    ])
    
    if parent_menu_data:
        parent_menu = Menu.browse(parent_menu_data.res_id)
        if not parent_menu.exists():
            parent_menu = Menu.create({
                'name': 'Time Off',
                'parent_id': menu_root.id,
                'sequence': 10,
            })
            parent_menu_data.write({'res_id': parent_menu.id})
        else:
            parent_menu.write({
                'name': 'Time Off',
                'parent_id': menu_root.id,
                'sequence': 10,
            })
    else:
        parent_menu = Menu.create({
            'name': 'Time Off',
            'parent_id': menu_root.id,
            'sequence': 10,
        })
        ModelData.create({
            'module': 'hudson_payroll_base',
            'name': 'menu_hr_payroll_time_off_root',
            'model': 'ir.ui.menu',
            'res_id': parent_menu.id,
            'noupdate': False,
        })
    print(f"parent_menu created/found: {parent_menu.id} - {parent_menu.name}")

    # Now link menu_action_hr_payroll_time_off as child of parent_menu
    child_menu = env.ref('hudson_payroll_base.menu_action_hr_payroll_time_off', raise_if_not_found=False)
    if child_menu:
        child_menu.write({
            'name': 'Time Off',
            'parent_id': parent_menu.id,
            'sequence': 10,
            'action': 'ir.actions.act_window,218',
        })
        print(f"child_menu {child_menu.id} linked to parent {parent_menu.id}")

    # Invalidate caches and signal changes
    env.invalidate_all()
    registry.clear_cache()
    registry.signal_changes()
    cr.commit()
    print("ALL COMMITTED SUCCESSFULLY!")
