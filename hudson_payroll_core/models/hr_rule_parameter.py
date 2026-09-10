# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrRuleParameter(models.Model):
    _name = 'hr.rule.parameter'
    _description = 'Rule Parameter'
    _order = 'name'

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True, index=True)
    category = fields.Selection([
        ('rate', 'Statutory Rate / Percentage'),
        ('ceiling', 'Wage Ceiling / Limit'),
        ('admin', 'Admin Charge Rate'),
        ('threshold', 'Threshold / Exemption Limit'),
        ('period', 'Period / Duration Limit'),
        ('eligibility', 'Eligibility Criteria'),
        ('other', 'Other Parameter'),
    ], string="Category", default='rate', required=True)
    description = fields.Text(
        string="Description",
        help="Statutory basis, purpose, or government notification reference."
    )
    parameter_version_ids = fields.One2many(
        'hr.rule.parameter.value',
        'parameter_id',
        string="Parameter Versions"
    )
    current_value = fields.Char(
        string="Current Value",
        compute='_compute_current_value',
        help="Value effective as of today."
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The code of the rule parameter must be unique!')
    ]

    @api.depends('parameter_version_ids', 'parameter_version_ids.date_from', 'parameter_version_ids.parameter_value')
    def _compute_current_value(self):
        today = fields.Date.today()
        for record in self:
            val = record._get_parameter_value(date=today)
            record.current_value = str(val) if val is not False else "No Active Version"

    def _get_parameter_value(self, date=None):
        """Retrieve the parameter string value effective on date."""
        self.ensure_one()
        if not date:
            date = fields.Date.today()
        versions = self.parameter_version_ids.filtered(
            lambda v: v.date_from <= date
        ).sorted(key=lambda v: v.date_from, reverse=True)
        return versions[0].parameter_value if versions else False

    @api.model
    def get_parameter(self, code, date=None, as_decimal=False):
        """
        Generic statutory parameter lookup for all statutory and payroll modules.
        Callers pass the actual code stored on the hr.rule.parameter record.
        """
        param = self.search([('code', '=', code)], limit=1)
        if not param:
            raise ValidationError(f"Statutory parameter '{code}' is not defined in the system.")

        val_str = param._get_parameter_value(date=date)
        if val_str is False:
            raise ValidationError(f"No effective statutory parameter version found for '{code}' on date {date or fields.Date.today()}.")

        try:
            val_float = float(val_str)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid non-numeric value '{val_str}' for parameter '{code}'.")

        if as_decimal and param.category in ('rate', 'admin'):
            return val_float / 100.0
        return val_float


class HrRuleParameterValue(models.Model):
    _name = 'hr.rule.parameter.value'
    _description = 'Rule Parameter Value'
    _order = 'date_from desc'

    parameter_id = fields.Many2one(
        'hr.rule.parameter',
        string="Parameter",
        required=True,
        ondelete='cascade'
    )
    code = fields.Char(related='parameter_id.code', string="Code", readonly=True, store=True)
    date_from = fields.Date(string="Valid From", required=True)
    parameter_value = fields.Char(string="Value", required=True)
    description = fields.Text(
        string="Notification / Notes",
        help="Government Notification Number or Statutory Gazette reference."
    )
