# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployeeType(models.Model):
    """Classification of employee types for payroll and pay run filtering."""
    _name = 'hr.employee.type'
    _description = 'Employee Type'
    _order = 'sequence, name'

    name = fields.Char(string='Employee Type', required=True, translate=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _default_employee_type_id(self):
        return self.env['hr.employee.type'].search([('code', '=', 'EMP')], limit=1)

    employee_type_id = fields.Many2one(
        'hr.employee.type',
        string='Employee Type',
        default=_default_employee_type_id,
        help="Type of employee (e.g. Permanent, Executive, Intern, Student)"
    )
    bank_account_id = fields.Many2one(
        'res.partner.bank',
        string='Bank Account Number',
        help="Employee bank account for payroll payment transfers and payment advice"
    )
    pay_by_attendance = fields.Boolean(
        string='Pay by Attendance',
        related='version_id.pay_by_attendance',
        readonly=False,
        help="If enabled, attendance adjustments (overtime / shortage) apply to payslips."
    )
