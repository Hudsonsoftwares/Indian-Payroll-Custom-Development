# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployeeType(models.Model):
    _name = 'hr.employee.type'
    _description = 'Employee Type'
    _order = 'sequence, name'

    name = fields.Char(string='Employee Type', required=True, translate=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    employee_type_id = fields.Many2one(
        'hr.employee.type',
        string='Employee Type',
        help="Classification of employee (e.g. Employee, Executive, Intern, Student)"
    )
    bank_account_id = fields.Many2one(
        'res.partner.bank',
        string='Bank Account Number',
        help="Employee bank account for payroll payment transfers"
    )
