# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrSalaryAdjustmentWizard(models.TransientModel):
    """
    Wizard to generate multiple salary adjustment records across multiple employees in batch.
    Matches 'New Group Sal. Adjustment' behavior.
    """
    _name = 'hr.salary.adjustment.wizard'
    _description = 'Generate Multiple Salary Adjustments'

    employee_ids = fields.Many2many(
        'hr.employee',
        'hr_salary_adj_wizard_employee_rel',
        'wizard_id',
        'employee_id',
        string='Employees',
        required=True,
        help="Select one or more employees to receive this salary adjustment."
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        related='company_id.country_id',
        store=True,
        readonly=True,
    )
    input_type_id = fields.Many2one(
        'hr.payslip.input.type',
        string='Adjustment Type',
        required=True,
        domain="['|', ('country_id', '=', False), ('country_id', '=', country_id)]",
        help="Other Input Type linked to this adjustment (global and country-specific)."
    )
    amount = fields.Monetary(
        string='Payslip Amount',
        required=True,
        currency_field='currency_id',
        help="Amount to be applied per payslip."
    )
    negative = fields.Boolean(
        string='Negative Value',
        default=False,
        help="If checked, the adjustment will be registered as negative."
    )
    duration = fields.Selection([
        ('one_time', 'One Time'),
        ('limited', 'Limited'),
        ('unlimited', 'Unlimited'),
    ], string='Duration', default='one_time', required=True)

    date_start = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today
    )
    date_end = fields.Date(
        string='End Date',
        help="End Date required for Limited duration adjustments."
    )
    until_amount = fields.Monetary(
        string='Until Amount',
        currency_field='currency_id',
        help="Optional total cap amount."
    )
    note = fields.Char(
        string='Note',
        help="Description or memo for the adjustments."
    )

    @api.onchange('employee_ids')
    def _onchange_employee_ids(self):
        if self.employee_ids and self.employee_ids[0].company_id:
            self.company_id = self.employee_ids[0].company_id

    @api.constrains('date_start', 'date_end', 'duration')
    def _check_dates(self):
        for wiz in self:
            if wiz.duration == 'limited':
                if not wiz.date_end:
                    raise ValidationError(_("End Date is mandatory for Limited duration adjustments."))
                if wiz.date_end < wiz.date_start:
                    raise ValidationError(_("End Date cannot be before Start Date."))

    @api.constrains('amount')
    def _check_amount(self):
        for wiz in self:
            if wiz.amount <= 0.0:
                raise ValidationError(_("Amount must be strictly greater than 0.0."))

    def action_create_adjustments(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_("Please select at least one employee."))

        created_adjustments = self.env['hr.salary.adjustment']
        for emp in self.employee_ids:
            vals = {
                'employee_id': emp.id,
                'company_id': emp.company_id.id or self.company_id.id,
                'input_type_id': self.input_type_id.id,
                'amount': self.amount,
                'negative': self.negative,
                'duration': self.duration,
                'date_start': self.date_start,
                'date_end': self.date_end if self.duration == 'limited' else False,
                'until_amount': self.until_amount,
                'note': self.note,
                'state': 'running',
            }
            created_adjustments |= self.env['hr.salary.adjustment'].create(vals)

        action = {
            'name': _('Salary Adjustments'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.salary.adjustment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_adjustments.ids)],
            'target': 'current',
        }
        if len(created_adjustments) == 1:
            action['res_id'] = created_adjustments.id
            action['view_mode'] = 'form'
        return action
