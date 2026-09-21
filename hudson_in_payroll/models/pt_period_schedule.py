# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

MONTH_SELECTION = [
    ('1', 'January'),
    ('2', 'February'),
    ('3', 'March'),
    ('4', 'April'),
    ('5', 'May'),
    ('6', 'June'),
    ('7', 'July'),
    ('8', 'August'),
    ('9', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
]


class PtPeriodSchedule(models.Model):
    """
    Master Configuration Model for Professional Tax Period Schedules.
    Single Source of Truth for Professional Tax deduction timing, statutory aggregation windows,
    and period resolution. Decoupled from salary range tax amount slabs (pt.state.slab).
    """
    _name = 'pt.period.schedule'
    _description = 'Professional Tax Period Schedule'
    _order = 'state_id, periodicity, window_start_month, date_from desc, id desc'

    name = fields.Char(
        string="Schedule Name",
        compute="_compute_name",
        store=True,
        help="Automated descriptive name summarizing state, periodicity, aggregation window, and deduction strategy."
    )
    state_id = fields.Many2one(
        'res.country.state',
        string="State",
        required=True,
        domain="[('country_id.code', '=', 'IN')]",
        help="Applicable Indian State for this Professional Tax period schedule."
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company Scope",
        default=lambda self: self.env.company,
        help="Optional company-specific override. Leave blank for global state default."
    )
    periodicity = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('half_yearly', 'Half-Yearly'),
        ('annual', 'Annual'),
    ], string="Periodicity", default='monthly', required=True,
        help="Statutory periodicity for Professional Tax calculation and reporting.")

    window_start_month = fields.Selection(
        MONTH_SELECTION,
        string="Window Start Month",
        required=False,
        help="Calendar month when statutory wage aggregation window starts (e.g. 4 for April in H1, 10 for October in H2)."
    )
    window_end_month = fields.Selection(
        MONTH_SELECTION,
        string="Window End Month",
        required=False,
        help="Calendar month when statutory wage aggregation window ends (e.g. 9 for September in H1, 3 for March in H2)."
    )

    deduction_strategy = fields.Selection([
        ('every_payroll', 'Every Payroll (Monthly)'),
        ('end_of_period', 'End of Period'),
        ('beginning_of_period', 'Beginning of Period'),
        ('specific_month', 'Specific Month'),
    ], string="Deduction Strategy", default='end_of_period', required=True,
        help="Strategy determining when Professional Tax is deducted from payslips during the period.")

    non_monthly_deduction_strategy = fields.Selection([
        ('end_of_period', 'End of Period'),
        ('beginning_of_period', 'Beginning of Period'),
        ('specific_month', 'Specific Month'),
    ], string="Deduction Strategy", compute="_compute_non_monthly_deduction_strategy", inverse="_inverse_non_monthly_deduction_strategy",
        help="Strategy determining when Professional Tax is deducted for quarterly/half-yearly schedules.")

    distribution_method = fields.Selection([
        ('full_amount', 'Full Amount'),
        ('equal_distribution', 'Equal Distribution'),
    ], string="Distribution Method", default='full_amount', required=True,
        help="Distribution method for Professional Tax recovery across payrolls.")

    deduction_month = fields.Selection(
        MONTH_SELECTION,
        string="Deduction Month",
        required=False,
        help="Calendar month in which deduction occurs when Deduction Strategy is set to 'End of Period' or 'Specific Month'."
    )

    min_service_days = fields.Integer(
        string="Minimum Service Days",
        default=0,
        help="Minimum appointment/service days in the period window required for PT liability (e.g. 60 for Kerala)."
    )

    date_from = fields.Date(
        string="Effective From",
        required=False,
        help="Start date from which this period schedule configuration is effective."
    )
    date_to = fields.Date(
        string="Effective To",
        help="Optional end date until which this period schedule configuration is effective."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Archiving flag to disable historical schedules."
    )
    remarks = fields.Text(
        string="Remarks / Statutory References",
        help="Government act reference, gazette reference, or statutory notes."
    )

    @api.depends('deduction_strategy')
    def _compute_non_monthly_deduction_strategy(self):
        for rec in self:
            rec.non_monthly_deduction_strategy = (
                rec.deduction_strategy
                if rec.deduction_strategy in ('end_of_period', 'beginning_of_period', 'specific_month')
                else 'end_of_period'
            )

    def _inverse_non_monthly_deduction_strategy(self):
        for rec in self:
            if rec.non_monthly_deduction_strategy:
                rec.deduction_strategy = rec.non_monthly_deduction_strategy

    @api.onchange('non_monthly_deduction_strategy')
    def _onchange_non_monthly_deduction_strategy(self):
        if self.non_monthly_deduction_strategy:
            self.deduction_strategy = self.non_monthly_deduction_strategy
            self._onchange_deduction_strategy()

    @api.onchange('periodicity')
    def _onchange_periodicity(self):
        if self.periodicity == 'monthly':
            self.window_start_month = False
            self.window_end_month = False
            self.deduction_month = False
            self.deduction_strategy = 'every_payroll'
            self.distribution_method = 'full_amount'
        elif self.periodicity == 'half_yearly':
            self.window_start_month = '4'
            self.window_end_month = '9'
            self.deduction_strategy = 'end_of_period'
            self.non_monthly_deduction_strategy = 'end_of_period'
            self.distribution_method = 'full_amount'
            self.deduction_month = '9'
        elif self.periodicity == 'quarterly':
            self.window_start_month = '4'
            self.window_end_month = '6'
            self.deduction_strategy = 'end_of_period'
            self.non_monthly_deduction_strategy = 'end_of_period'
            self.distribution_method = 'full_amount'
            self.deduction_month = '6'
        elif self.periodicity == 'annual':
            self.window_start_month = '4'
            self.window_end_month = '3'
            self.deduction_strategy = 'end_of_period'
            self.non_monthly_deduction_strategy = 'end_of_period'
            self.distribution_method = 'full_amount'
            self.deduction_month = '3'

    @api.onchange('window_start_month')
    def _onchange_window_start_month(self):
        if not self.window_start_month:
            return
        start_m = int(self.window_start_month)
        if self.periodicity == 'half_yearly':
            self.window_end_month = str((start_m + 5 - 1) % 12 + 1)
        elif self.periodicity == 'quarterly':
            self.window_end_month = str((start_m + 2 - 1) % 12 + 1)
        elif self.periodicity == 'annual':
            self.window_end_month = str((start_m + 11 - 1) % 12 + 1)
        if self.deduction_strategy == 'end_of_period':
            self.deduction_month = self.window_end_month
        elif self.deduction_strategy == 'beginning_of_period':
            self.deduction_month = self.window_start_month

    @api.onchange('window_end_month', 'deduction_strategy', 'non_monthly_deduction_strategy')
    def _onchange_deduction_strategy(self):
        if self.periodicity == 'monthly':
            self.window_start_month = False
            self.window_end_month = False
            self.deduction_month = False
            self.deduction_strategy = 'every_payroll'
            self.distribution_method = 'full_amount'
            return
        if self.non_monthly_deduction_strategy and self.deduction_strategy != self.non_monthly_deduction_strategy:
            self.deduction_strategy = self.non_monthly_deduction_strategy
        if self.periodicity in ('quarterly', 'half_yearly', 'annual') and self.deduction_strategy == 'every_payroll':
            self.deduction_strategy = 'end_of_period'
            self.non_monthly_deduction_strategy = 'end_of_period'
            self.distribution_method = 'full_amount'
            if self.window_end_month:
                self.deduction_month = self.window_end_month
            return
        if self.deduction_strategy == 'end_of_period':
            self.distribution_method = 'full_amount'
            if self.window_end_month:
                self.deduction_month = self.window_end_month
        elif self.deduction_strategy == 'beginning_of_period':
            self.distribution_method = 'full_amount'
            if self.window_start_month:
                self.deduction_month = self.window_start_month
        elif self.deduction_strategy == 'specific_month':
            self.distribution_method = 'full_amount'
            if not self.deduction_month and self.window_end_month:
                self.deduction_month = self.window_end_month

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('non_monthly_deduction_strategy') and not vals.get('deduction_strategy'):
                vals['deduction_strategy'] = vals['non_monthly_deduction_strategy']
            periodicity = vals.get('periodicity', 'monthly')
            strat = vals.get('deduction_strategy')
            if periodicity == 'monthly':
                vals['distribution_method'] = 'full_amount'
                vals['window_start_month'] = False
                vals['window_end_month'] = False
                vals['deduction_month'] = False
                vals['deduction_strategy'] = 'every_payroll'
            elif periodicity in ('quarterly', 'half_yearly', 'annual'):
                if not strat:
                    vals['deduction_strategy'] = 'end_of_period'
                    strat = 'end_of_period'
                vals.setdefault('distribution_method', 'full_amount')
                if strat == 'end_of_period' and vals.get('window_end_month'):
                    vals['deduction_month'] = vals['window_end_month']
                elif strat == 'beginning_of_period' and vals.get('window_start_month'):
                    vals['deduction_month'] = vals['window_start_month']
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('non_monthly_deduction_strategy'):
            vals['deduction_strategy'] = vals['non_monthly_deduction_strategy']
        if 'window_end_month' in vals or 'deduction_strategy' in vals or 'window_start_month' in vals or 'periodicity' in vals:
            for rec in self:
                periodicity = vals.get('periodicity', rec.periodicity)
                strat = vals.get('deduction_strategy', rec.deduction_strategy)
                if periodicity == 'monthly':
                    vals['distribution_method'] = 'full_amount'
                    vals['window_start_month'] = False
                    vals['window_end_month'] = False
                    vals['deduction_month'] = False
                    vals['deduction_strategy'] = 'every_payroll'
                elif periodicity in ('quarterly', 'half_yearly', 'annual'):
                    if strat == 'every_payroll':
                        vals['deduction_strategy'] = 'end_of_period'
                    vals['distribution_method'] = 'full_amount'
                    eff_strat = vals.get('deduction_strategy', strat)
                    if eff_strat == 'end_of_period':
                        w_end = vals.get('window_end_month', rec.window_end_month)
                        if w_end:
                            vals['deduction_month'] = w_end
                    elif eff_strat == 'beginning_of_period':
                        w_start = vals.get('window_start_month', rec.window_start_month)
                        if w_start:
                            vals['deduction_month'] = w_start
        return super().write(vals)

    @api.depends('state_id', 'periodicity', 'window_start_month', 'window_end_month', 'deduction_strategy', 'deduction_month')
    def _compute_name(self):
        month_dict = dict(MONTH_SELECTION)
        strat_dict = dict([
            ('every_payroll', 'Every Payroll'),
            ('end_of_period', 'End of Period'),
            ('beginning_of_period', 'Beginning of Period'),
            ('specific_month', 'Specific Month'),
        ])
        for rec in self:
            st_name = rec.state_id.name if rec.state_id else 'Global'
            per_name = (rec.periodicity or 'monthly').replace('_', '-').title()
            start_m = month_dict.get(rec.window_start_month, '')
            end_m = month_dict.get(rec.window_end_month, '')
            ded_m = month_dict.get(rec.deduction_month, '')
            if rec.deduction_strategy == 'specific_month' and ded_m:
                strat = f"Specific Month ({ded_m})"
            else:
                strat = strat_dict.get(rec.deduction_strategy, '')

            if rec.periodicity == 'monthly':
                rec.name = f"{st_name} Monthly - {strat}"
            elif start_m and end_m:
                rec.name = f"{st_name} {per_name} ({start_m}–{end_m}) - {strat}"
            else:
                rec.name = f"{st_name} {per_name} - {strat}"

    @api.constrains('periodicity', 'window_start_month', 'window_end_month', 'deduction_strategy', 'deduction_month', 'distribution_method')
    def _check_periodicity_configuration(self):
        for rec in self:
            if rec.periodicity == 'monthly':
                continue
            if rec.periodicity in ('quarterly', 'half_yearly', 'annual'):
                if rec.deduction_strategy == 'every_payroll':
                    raise ValidationError(_(
                        "For %s periodicity, 'Every Payroll' (Equal Contribution) is not allowed. "
                        "Professional Tax must be deducted in full at End of Period, Beginning of Period, or a Specific Month."
                    ) % (rec.periodicity or '').replace('_', '-').title())
                if rec.distribution_method == 'equal_distribution':
                    raise ValidationError(_(
                        "For %s periodicity, 'Equal Distribution' is not permitted. Distribution Method must be Full Amount."
                    ) % (rec.periodicity or '').replace('_', '-').title())
            if rec.periodicity == 'half_yearly':
                if not rec.window_start_month or not rec.window_end_month:
                    raise ValidationError(_("Window Start Month and Window End Month are required for Half-Yearly periodicity."))
            elif rec.periodicity in ('quarterly', 'annual'):
                if not rec.window_start_month or not rec.window_end_month:
                    raise ValidationError(_("Window Start Month and Window End Month are required for %s periodicity.") % rec.periodicity.title())
            if rec.deduction_strategy == 'specific_month' and not rec.deduction_month:
                raise ValidationError(_("Deduction Month is required when Deduction Strategy is set to Specific Month."))

    @api.constrains('date_from', 'date_to')
    def _check_effective_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Effective From date (%s) cannot be later than Effective To date (%s).") % (rec.date_from, rec.date_to))
