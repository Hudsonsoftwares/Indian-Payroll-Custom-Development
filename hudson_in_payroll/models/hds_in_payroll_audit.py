# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HdsInPayrollAudit(models.Model):
    """
    Statutory Payroll Calculation Audit Storage Model.
    Stores immutable calculation snapshots for Indian Statutory Compliance.
    """
    _name = 'hds.in.payroll.audit'
    _description = 'Statutory Payroll Calculation Audit Log'
    _order = 'calculation_date desc, id desc'
    _rec_name = 'display_name'

    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        readonly=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        index=True,
        readonly=True
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        string="Payslip",
        ondelete='cascade',
        index=True,
        readonly=True
    )
    statutory_module = fields.Selection([
        ('epf', 'Employee Provident Fund (EPF)'),
        ('esic', 'Employees State Insurance (ESIC)'),
        ('pt', 'Professional Tax (PT)'),
        ('lwf', 'Labour Welfare Fund (LWF)'),
        ('bonus', 'Statutory Bonus'),
        ('gratuity', 'Gratuity'),
        ('leave_encashment', 'Leave Encashment'),
        ('tds', 'Income Tax (TDS)'),
        ('revision', 'Salary Revision'),
    ], string="Statutory Module", required=True, index=True, readonly=True)

    calculation_type = fields.Char(
        string="Calculation Type",
        default="statutory_compute",
        readonly=True
    )
    rule_code = fields.Char(
        string="Rule Code",
        required=True,
        index=True,
        readonly=True
    )
    calculation_date = fields.Date(
        string="Calculation Date",
        required=True,
        index=True,
        default=fields.Date.today,
        readonly=True
    )

    inputs_json = fields.Text(
        string="Inputs (JSON)",
        help="Formatted JSON payload containing all input variables.",
        readonly=True
    )
    outputs_json = fields.Text(
        string="Outputs (JSON)",
        help="Formatted JSON payload containing all output calculation results.",
        readonly=True
    )
    parameters_json = fields.Text(
        string="Applied Parameters (JSON)",
        help="Formatted JSON payload containing all date-effective rule parameters used.",
        readonly=True
    )

    messages = fields.Text(string="Audit Messages", readonly=True)
    warnings = fields.Text(string="Warnings", readonly=True)
    exception_trace = fields.Text(string="Exception Stack Trace", readonly=True)
    execution_time_ms = fields.Float(string="Execution Time (ms)", digits=(16, 3), readonly=True)
    version = fields.Char(string="Engine Version", default="19.0.1.0.0", readonly=True)

    status = fields.Selection([
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ], string="Status", required=True, default='success', index=True, readonly=True)

    display_name = fields.Char(string="Title", compute='_compute_display_name', store=True)

    @api.depends('statutory_module', 'rule_code', 'employee_id', 'calculation_date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.statutory_module.upper() if rec.statutory_module else ''}] {rec.rule_code or ''} - {rec.employee_id.name or ''} ({rec.calculation_date or ''})"
