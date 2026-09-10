# -*- coding: utf-8 -*-
from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        help="Analytic account associated with this salary rule"
    )
    account_tax_id = fields.Many2one(
        'account.tax',
        string='Tax',
        help="Tax account associated with this salary rule"
    )
    account_debit_id = fields.Many2one(
        'account.account',
        string='Debit Account',
        help="Debit account for salary expenses"
    )
    account_credit_id = fields.Many2one(
        'account.account',
        string='Credit Account',
        help="Credit account for salary payable / liabilities"
    )
