# -*- coding: utf-8 -*-
from odoo import api, fields, models


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
        compute='_compute_bank_account_id',
        inverse='_inverse_bank_account_id',
        search='_search_bank_account_id',
        store=True,
        help="Employee primary bank account from Personal tab for payroll payment transfers and payment advice"
    )

    @api.depends('bank_account_ids', 'primary_bank_account_id')
    def _compute_bank_account_id(self):
        for emp in self:
            primary = getattr(emp, 'primary_bank_account_id', False)
            if not primary and getattr(emp, 'bank_account_ids', False):
                primary = emp.bank_account_ids[0]
            emp.bank_account_id = primary

    def _inverse_bank_account_id(self):
        for emp in self:
            if emp.bank_account_id and emp.bank_account_id not in emp.bank_account_ids:
                emp.bank_account_ids = [(4, emp.bank_account_id.id)]

    def _search_bank_account_id(self, operator, value):
        return ['|', ('primary_bank_account_id', operator, value), ('bank_account_ids', operator, value)]

    @api.depends('bank_account_ids', 'salary_distribution')
    def _compute_primary_bank_account_id(self):
        for employee in self:
            dist = employee.salary_distribution or {}
            if employee.bank_account_ids:
                try:
                    primary_account = min(
                        employee.bank_account_ids,
                        key=lambda acc: dist.get(str(acc.id), {}).get("sequence", float("inf")) if isinstance(dist, dict) else float("inf"),
                    )
                except Exception:
                    primary_account = employee.bank_account_ids[0]
                employee.primary_bank_account_id = primary_account
            else:
                employee.primary_bank_account_id = False
    pay_by_attendance = fields.Boolean(
        string='Pay by Attendance',
        related='version_id.pay_by_attendance',
        readonly=False,
        help="If enabled, attendance adjustments (overtime / shortage) apply to payslips."
    )
