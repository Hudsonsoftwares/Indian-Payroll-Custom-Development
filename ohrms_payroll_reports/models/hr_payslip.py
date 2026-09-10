# -*- coding: utf-8 -*-
from odoo import fields, models

class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    date_from = fields.Date(related='slip_id.date_from', string='Date From', store=True)
    date_to = fields.Date(related='slip_id.date_to', string='Date To', store=True)


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked.days'

    employee_id = fields.Many2one('hr.employee', related='contract_id.employee_id', string='Employee', store=True)
    date_from = fields.Date(related='payslip_id.date_from', string='Date From', store=True)
    date_to = fields.Date(related='payslip_id.date_to', string='Date To', store=True)


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    employee_id = fields.Many2one('hr.employee', related='contract_id.employee_id', string='Employee', store=True)
