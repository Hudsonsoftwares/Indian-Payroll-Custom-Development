# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrSalaryAdjustment(models.Model):
    """
    Employee-specific recurring or one-time payroll adjustment.
    Provides an Other Input to payroll; Salary Rules determine how that input impacts Net Salary.
    """
    _name = 'hr.salary.adjustment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Salary Adjustment'
    _order = 'priority desc, date_start desc, id desc'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
        readonly=True
    )
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Very High'),
    ], string='Priority', default='0', tracking=True)

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True,
        index=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True
    )
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        related='company_id.country_id',
        store=True,
        readonly=True,
        help="Country of company. Allows both global (country-independent) and country-specific input types."
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )
    contract_id = fields.Many2one(
        'hr.version',
        string='Contract',
        compute='_compute_contract_id',
        store=True,
        readonly=False,
        help="Contract to which this adjustment applies."
    )
    input_type_id = fields.Many2one(
        'hr.payslip.input.type',
        string='Type',
        required=True,
        tracking=True,
        index=True,
        domain="['|', ('country_id', '=', False), ('country_id', '=', country_id)]",
        help="Other Input Type linked to this adjustment (supports global and country-specific types)."
    )
    input_code = fields.Char(
        string='Input Code',
        related='input_type_id.code',
        store=True,
        readonly=True,
        index=True
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help="Adjustment amount applied per payslip period."
    )
    negative = fields.Boolean(
        string='Negative Value',
        default=False,
        tracking=True,
        help="If checked, the adjustment passes a negative value to the payslip input."
    )
    duration = fields.Selection([
        ('one_time', 'One Time'),
        ('limited', 'Limited'),
        ('unlimited', 'Unlimited'),
    ], string='Duration', default='one_time', required=True, tracking=True)

    date_start = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    date_end = fields.Date(
        string='End Date',
        tracking=True,
        help="Final date of applicability for limited adjustments."
    )
    until_amount = fields.Monetary(
        string='Until',
        currency_field='currency_id',
        tracking=True,
        help="Maximum cumulative amount limit or target cap for this adjustment."
    )
    beneficiary_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Beneficiary Bank Account',
        compute='_compute_beneficiary_bank',
        store=True,
        readonly=False,
        help="Bank account of the beneficiary for this adjustment (e.g. child support, loan creditor)."
    )
    note = fields.Char(
        string='Note',
        tracking=True,
        help="Short description or reason for the adjustment."
    )
    state = fields.Selection([
        ('running', 'Running'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='running', required=True, tracking=True, index=True)

    payslip_input_ids = fields.One2many(
        'hr.payslip.input',
        'adjustment_id',
        string='Applied Payslip Inputs',
        readonly=True
    )
    applied_count = fields.Integer(
        string='Applied Payslips Count',
        compute='_compute_applied_count'
    )

    @api.depends('employee_id', 'input_type_id', 'date_start')
    def _compute_name(self):
        for rec in self:
            emp = rec.employee_id.name or _('Employee')
            type_name = rec.input_type_id.name or _('Adjustment')
            date_str = rec.date_start.strftime('%b %Y') if rec.date_start else ''
            rec.name = f"{emp} - {type_name} ({date_str})" if date_str else f"{emp} - {type_name}"

    @api.depends('employee_id', 'company_id')
    def _compute_contract_id(self):
        for rec in self:
            if rec.employee_id:
                contract = rec.employee_id.version_id
                if not contract:
                    contract = self.env['hr.version'].search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('company_id', '=', rec.company_id.id),
                    ], limit=1, order='id desc')
                rec.contract_id = contract
            else:
                rec.contract_id = False

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            if self.employee_id.company_id:
                self.company_id = self.employee_id.company_id
            if self.employee_id.bank_account_id:
                self.beneficiary_bank_id = self.employee_id.bank_account_id

    @api.depends('employee_id')
    def _compute_beneficiary_bank(self):
        for rec in self:
            if rec.employee_id and rec.employee_id.bank_account_id:
                rec.beneficiary_bank_id = rec.employee_id.bank_account_id
            elif not rec.beneficiary_bank_id:
                rec.beneficiary_bank_id = False

    @api.depends('payslip_input_ids')
    def _compute_applied_count(self):
        for rec in self:
            rec.applied_count = len(rec.payslip_input_ids.mapped('payslip_id'))

    @api.constrains('date_start', 'date_end', 'duration')
    def _check_dates(self):
        for rec in self:
            if rec.duration == 'limited':
                if not rec.date_end:
                    raise ValidationError(_("End Date is mandatory for Limited duration adjustments."))
                if rec.date_end < rec.date_start:
                    raise ValidationError(_("End Date cannot be before Start Date."))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0.0:
                raise ValidationError(_("Adjustment amount must be strictly greater than 0.0."))

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_running(self):
        self.write({'state': 'running'})

    def action_view_payslips(self):
        self.ensure_one()
        payslips = self.payslip_input_ids.mapped('payslip_id')
        action = {
            'name': _('Applied Payslips - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payslips.ids)],
            'target': 'current',
        }
        if len(payslips) == 1:
            action['res_id'] = payslips.id
            action['view_mode'] = 'form'
        return action
