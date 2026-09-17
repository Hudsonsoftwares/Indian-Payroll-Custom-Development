# -*- coding: utf-8 -*-
from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def load_menus(self, debug):
        """
        Dynamically hides the Labour Welfare Fund (LWF) menu under Indian Statutory
        when LWF is not enabled for the user's current company.
        """
        menus = super().load_menus(debug)
        try:
            company = self.env.company
        except Exception:
            company = False

        if company and hasattr(company, 'hds_in_enable_lwf') and not company.hds_in_enable_lwf:
            lwf_menu = self.env.ref('hudson_in_payroll.menu_lwf_state_rate', raise_if_not_found=False)
            if lwf_menu and lwf_menu.id in menus:
                menus = dict(menus)
                parent_menu = lwf_menu.parent_id
                if parent_menu and parent_menu.id in menus:
                    p_dict = dict(menus[parent_menu.id])
                    p_dict['children'] = [c for c in p_dict.get('children', []) if c != lwf_menu.id]
                    menus[parent_menu.id] = p_dict
                menus.pop(lwf_menu.id, None)
        return menus
