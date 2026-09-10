# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    standard_working_days_per_month = fields.Float(
        string='Standard Working Days per Month',
        default=26.0,
        help="Standard working days per month used as a default for contract rate calculations."
    )
    standard_hours_per_day = fields.Float(
        string='Standard Hours per Day',
        default=8.0,
        help="Standard working hours per day used as a default for contract rate calculations."
    )
    overtime_multiplier = fields.Float(
        string='Overtime Rate Multiplier',
        default=1.0,
        help="Default overtime hourly rate multiplier (e.g. 1.5 for 1.5x of hourly rate)."
    )
    pay_overtime = fields.Boolean(
        string='Pay Overtime',
        default=False,
        help="Enable or disable overtime salary calculations and payouts."
    )

