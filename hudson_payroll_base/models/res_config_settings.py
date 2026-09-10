# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    """Extend company to store default payroll configuration settings."""
    _inherit = 'res.company'

    ytd_reset_date = fields.Selection([
        ('01-01', '1st of January (Calendar Year)'),
        ('04-01', '1st of April (Fiscal Year)'),
        ('07-01', '1st of July'),
        ('10-01', '1st of October'),
    ], string='YTD Reset Date', default='01-01',
       help="Date when Year-To-Date (YTD) accumulator totals reset to zero.")

    send_payslips = fields.Selection([
        ('draft', 'When Draft'),
        ('confirmed', 'When Confirmed'),
        ('paid', 'When Paid'),
        ('manual', 'Manual Only'),
    ], string='Send Payslips to Employees', default='confirmed',
       help="Define when payslips are printed and sent to employees.")

    deferred_time_off = fields.Boolean(
        string='Deferred Time Off',
        default=False,
        help="Postpone time off after payslip validation."
    )
    deferred_time_off_responsible_id = fields.Many2one(
        'res.users',
        string='Deferred Time Off Responsible',
        help="Responsible user for managing deferred time off."
    )
    payrun_accounting = fields.Boolean(
        string='Batch Accounting Entries',
        default=False,
        help="Create consolidated journal entries upon pay run confirmation."
    )

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            if company.country_id:
                structures = self.env['hr.payroll.structure'].search([
                    ('company_id', '=', company.id),
                    ('country_id', '=', False)
                ])
                if structures:
                    structures.write({'country_id': company.country_id.id})
        return companies

    def write(self, vals):
        res = super().write(vals)
        if 'country_id' in vals and vals['country_id']:
            for company in self:
                structures = self.env['hr.payroll.structure'].search([
                    ('company_id', '=', company.id)
                ])
                if structures:
                    structures.write({'country_id': vals['country_id']})
        return res


class ResConfigSettings(models.TransientModel):
    """Payroll Configuration Settings."""
    _inherit = 'res.config.settings'

    # Notice period fields are inherited from res.company via base hr module:
    # contract_expiration_notice_period
    # work_permit_expiration_notice_period

    ytd_reset_date = fields.Selection(
        related='company_id.ytd_reset_date',
        readonly=False,
        string='YTD Reset Date'
    )
    send_payslips = fields.Selection(
        related='company_id.send_payslips',
        readonly=False,
        string='Send Payslips to Employees'
    )
    deferred_time_off = fields.Boolean(
        related='company_id.deferred_time_off',
        readonly=False,
        string='Deferred Time Off'
    )
    deferred_time_off_responsible_id = fields.Many2one(
        'res.users',
        related='company_id.deferred_time_off_responsible_id',
        readonly=False,
        string='Responsible'
    )
    payrun_accounting = fields.Boolean(
        related='company_id.payrun_accounting',
        readonly=False,
        string='Batch Journal Entries'
    )
    module_account = fields.Boolean(
        string='Payroll Accounting',
        help='Post payroll slips and salary journal entries in accounting.'
    )
    module_hr_attendance = fields.Boolean(
        string='Biometric / Attendance Integration',
        help='Integrate attendance records and worked days with payslip computation.'
    )
