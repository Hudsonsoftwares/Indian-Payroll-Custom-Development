# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    input_type_id = fields.Many2one(
        'hr.payslip.input.type',
        string='Input Type',
        help='Select the salary input type to auto-fill description and code'
    )

    @api.onchange('input_type_id')
    def _onchange_input_type_id(self):
        if self.input_type_id:
            self.name = self.input_type_id.name
            self.code = self.input_type_id.code
