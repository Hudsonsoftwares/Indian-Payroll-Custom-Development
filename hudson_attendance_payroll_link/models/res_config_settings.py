# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    standard_working_days_per_month = fields.Float(
        related='company_id.standard_working_days_per_month',
        readonly=False,
        string='Standard Working Days per Month'
    )
    standard_hours_per_day = fields.Float(
        related='company_id.standard_hours_per_day',
        readonly=False,
        string='Standard Hours per Day'
    )
    overtime_multiplier = fields.Float(
        related='company_id.overtime_multiplier',
        readonly=False,
        string='Overtime Rate Multiplier'
    )
    pay_overtime = fields.Boolean(
        related='company_id.pay_overtime',
        readonly=False,
        string='Pay Overtime'
    )

