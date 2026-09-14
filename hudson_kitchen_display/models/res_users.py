from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    kitchen_screen_access = fields.Boolean(
        string='Kitchen Screen Access',
        help='Lets this user open the kitchen/preparation screens even if they '
             'are not a full Point of Sale user/manager - e.g. a kitchen-only login.')
