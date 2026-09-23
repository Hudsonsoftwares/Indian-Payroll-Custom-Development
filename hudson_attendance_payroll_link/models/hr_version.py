# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo import api, fields, models

class HrVersion(models.Model):
    _inherit = 'hr.version'

    standard_working_days_per_month = fields.Float(
        string='Standard Working Days per Month',
        compute='_compute_calendar_standards',
        store=True,
        readonly=True,
        help="Stable annual average monthly working days derived from Working Schedule: (working_days_per_week * 52 / 12)."
    )
    standard_hours_per_day = fields.Float(
        string='Standard Hours per Day',
        compute='_compute_calendar_standards',
        store=True,
        readonly=True,
        help="Standard hours per working day derived from Working Schedule."
    )
    salary_calculation_type = fields.Selection([
        ('fixed', 'Fixed Salary (Pro-rated by Attendance)'),
        ('hourly', 'Hourly Rate (Pure Attendance-Based)'),
    ], string='Salary Calculation Type', default='fixed', required=True)
    overtime_multiplier = fields.Float(
        string='Overtime Multiplier',
        default=1.0,
        help="Overtime rate multiplier applied to the standard hourly rate."
    )
    pay_overtime = fields.Boolean(
        string='Pay Overtime',
        default=False,
        help="Enable or disable overtime salary calculations and payouts for this contract."
    )

    hourly_rate = fields.Float(
        string='Computed Hourly Rate',
        compute='_compute_hourly_rate',
        store=True,
        help="Computed standard hourly rate: Monthly Salary / (Working Days * Hours per Day)"
    )
    overtime_hourly_rate = fields.Float(
        string='Computed Overtime Hourly Rate',
        compute='_compute_overtime_hourly_rate',
        store=True,
        help="Computed overtime hourly rate: Standard Hourly Rate * Overtime Multiplier"
    )

    # Writable rate fields with conditional computation
    overtime_rate_per_hour = fields.Float(
        compute='_compute_overtime_rate_per_hour',
        store=True,
        readonly=False,
        string='Overtime Rate (per hour)'
    )
    shortage_deduction_rate_per_hour = fields.Float(
        compute='_compute_shortage_deduction_rate_per_hour',
        store=True,
        readonly=False,
        string='Shortage Deduction Rate (per hour)'
    )

    # Boolean tracking fields for manual overrides
    overtime_rate_manually_set = fields.Boolean(
        string='Overtime Rate Manually Set',
        default=False,
        store=True,
    )
    shortage_rate_manually_set = fields.Boolean(
        string='Shortage Rate Manually Set',
        default=False,
        store=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super(HrVersion, self).default_get(fields_list)
        company = self.env.company
        if 'overtime_multiplier' in fields_list and 'overtime_multiplier' not in res:
            res['overtime_multiplier'] = company.overtime_multiplier or 1.0
        if 'pay_overtime' in fields_list and 'pay_overtime' not in res:
            res['pay_overtime'] = company.pay_overtime or False
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('salary_calculation_type'):
                vals['salary_calculation_type'] = 'fixed'
            wage = vals.get('wage', 0.0)
            
            # Fetch divisor values from vals or default to company-level defaults
            days = vals.get('standard_working_days_per_month')
            if days is None:
                days = self.env.company.standard_working_days_per_month or 26.0
            hours = vals.get('standard_hours_per_day')
            if hours is None:
                hours = self.env.company.standard_hours_per_day or 8.0
            mult = vals.get('overtime_multiplier')
            if mult is None:
                mult = self.env.company.overtime_multiplier or 1.0
                
            divisor = days * hours
            hourly = wage / divisor if divisor else 0.0
            
            # Determine if overtime rate is custom
            if 'overtime_rate_per_hour' in vals and vals.get('overtime_rate_per_hour') != 0.0:
                if abs(vals['overtime_rate_per_hour'] - (hourly * mult)) > 0.01:
                    vals['overtime_rate_manually_set'] = True
            else:
                vals['overtime_rate_per_hour'] = hourly * mult
                vals['overtime_rate_manually_set'] = False

            # Determine if shortage rate is custom
            if 'shortage_deduction_rate_per_hour' in vals and vals.get('shortage_deduction_rate_per_hour') != 0.0:
                if abs(vals['shortage_deduction_rate_per_hour'] - hourly) > 0.01:
                    vals['shortage_rate_manually_set'] = True
            else:
                vals['shortage_deduction_rate_per_hour'] = hourly
                vals['shortage_rate_manually_set'] = False
                
        return super(HrVersion, self).create(vals_list)

    def write(self, vals):
        for rec in self:
            local_vals = vals.copy()
            
            wage = local_vals.get('wage', rec.wage)
            days = local_vals.get('standard_working_days_per_month', rec.standard_working_days_per_month)
            hours = local_vals.get('standard_hours_per_day', rec.standard_hours_per_day)
            mult = local_vals.get('overtime_multiplier', rec.overtime_multiplier)
            
            divisor = days * hours
            computed_hourly = wage / divisor if divisor else 0.0
            
            # Check for manual edits to Overtime Rate
            if 'overtime_rate_per_hour' in local_vals:
                expected_ot = computed_hourly * mult
                if abs(local_vals['overtime_rate_per_hour'] - expected_ot) > 0.01:
                    local_vals['overtime_rate_manually_set'] = True
                else:
                    local_vals['overtime_rate_manually_set'] = False
            elif any(k in local_vals for k in ['wage', 'standard_working_days_per_month', 'standard_hours_per_day', 'overtime_multiplier']):
                # Auto-update if config changes and NOT custom
                if not rec.overtime_rate_manually_set:
                    local_vals['overtime_rate_per_hour'] = computed_hourly * mult

            # Check for manual edits to Shortage Rate
            if 'shortage_deduction_rate_per_hour' in local_vals:
                if abs(local_vals['shortage_deduction_rate_per_hour'] - computed_hourly) > 0.01:
                    local_vals['shortage_rate_manually_set'] = True
                else:
                    local_vals['shortage_rate_manually_set'] = False
            elif any(k in local_vals for k in ['wage', 'standard_working_days_per_month', 'standard_hours_per_day']):
                # Auto-update if config changes and NOT custom
                if not rec.shortage_rate_manually_set:
                    local_vals['shortage_deduction_rate_per_hour'] = computed_hourly
                    
            super(HrVersion, rec).write(local_vals)
        return True

    @api.depends('resource_calendar_id', 'resource_calendar_id.hours_per_day', 'resource_calendar_id.attendance_ids')
    def _compute_calendar_standards(self):
        for rec in self:
            cal = rec.resource_calendar_id
            if cal:
                if cal.hours_per_day:
                    rec.standard_hours_per_day = float(cal.hours_per_day)
                elif cal.attendance_ids:
                    days_dict = {}
                    for att in cal.attendance_ids:
                        span = att.hour_to - att.hour_from
                        days_dict[att.dayofweek] = days_dict.get(att.dayofweek, 0.0) + span
                    rec.standard_hours_per_day = (sum(days_dict.values()) / len(days_dict)) if days_dict else 8.0
                else:
                    rec.standard_hours_per_day = 8.0

                if cal.attendance_ids:
                    working_days_per_week = len(set(cal.attendance_ids.mapped('dayofweek')))
                    rec.standard_working_days_per_month = (working_days_per_week * 52.0) / 12.0
                else:
                    rec.standard_working_days_per_month = 26.0
            else:
                rec.standard_hours_per_day = 8.0
                rec.standard_working_days_per_month = 26.0

    @api.depends('wage', 'standard_working_days_per_month', 'standard_hours_per_day', 'resource_calendar_id')
    def _compute_hourly_rate(self):
        for rec in self:
            divisor = rec.standard_working_days_per_month * rec.standard_hours_per_day
            rec.hourly_rate = rec.wage / divisor if divisor else 0.0

    @api.depends('hourly_rate', 'overtime_multiplier')
    def _compute_overtime_hourly_rate(self):
        for rec in self:
            rec.overtime_hourly_rate = rec.hourly_rate * rec.overtime_multiplier

    @api.depends('overtime_hourly_rate', 'overtime_rate_manually_set')
    def _compute_overtime_rate_per_hour(self):
        for rec in self:
            if not rec.overtime_rate_manually_set:
                rec.overtime_rate_per_hour = rec.overtime_hourly_rate
            else:
                rec.overtime_rate_per_hour = rec.overtime_rate_per_hour or 0.0

    @api.depends('hourly_rate', 'shortage_rate_manually_set')
    def _compute_shortage_deduction_rate_per_hour(self):
        for rec in self:
            if not rec.shortage_rate_manually_set:
                rec.shortage_deduction_rate_per_hour = rec.hourly_rate
            else:
                rec.shortage_deduction_rate_per_hour = rec.shortage_deduction_rate_per_hour or 0.0

    @api.onchange('overtime_rate_per_hour')
    def _onchange_overtime_rate_per_hour(self):
        for rec in self:
            if rec.overtime_hourly_rate and abs(rec.overtime_rate_per_hour - rec.overtime_hourly_rate) > 0.01:
                rec.overtime_rate_manually_set = True

    @api.onchange('shortage_deduction_rate_per_hour')
    def _onchange_shortage_deduction_rate_per_hour(self):
        for rec in self:
            if rec.hourly_rate and abs(rec.shortage_deduction_rate_per_hour - rec.hourly_rate) > 0.01:
                rec.shortage_rate_manually_set = True

    @api.onchange('wage', 'standard_working_days_per_month', 'standard_hours_per_day', 'overtime_multiplier')
    def _onchange_hourly_rate_config(self):
        for rec in self:
            divisor = rec.standard_working_days_per_month * rec.standard_hours_per_day
            computed_hourly = rec.wage / divisor if divisor else 0.0
            rec.hourly_rate = computed_hourly
            rec.overtime_hourly_rate = computed_hourly * rec.overtime_multiplier
            
            if not rec.overtime_rate_manually_set:
                rec.overtime_rate_per_hour = computed_hourly * rec.overtime_multiplier
            if not rec.shortage_rate_manually_set:
                rec.shortage_deduction_rate_per_hour = computed_hourly

    def _get_period_scheduled_hours(self, date_from, date_to):
        """Private helper: Returns total scheduled working hours for the period from resource.calendar."""
        self.ensure_one()
        data = self.env['hr.payslip']._get_attendance_vs_schedule(self, date_from, date_to)
        return data.get('scheduled_hours', 0.0)

    def _get_period_scheduled_days(self, date_from, date_to):
        """Private helper: Returns total scheduled working days for the period from resource.calendar."""
        self.ensure_one()
        data = self.env['hr.payslip']._get_attendance_vs_schedule(self, date_from, date_to)
        return data.get('scheduled_days', 0.0)

    def get_period_shortage_rate(self, date_from, date_to):
        """Public method: Returns hourly shortage rate for the payslip period."""
        self.ensure_one()
        if not self.pay_by_attendance:
            return 0.0
        if not self.salary_calculation_type or self.salary_calculation_type == 'fixed':
            sched_hrs = self._get_period_scheduled_hours(date_from, date_to)
            return (self.wage / sched_hrs) if sched_hrs > 0.0 else 0.0
        return self.shortage_deduction_rate_per_hour or 0.0

    def get_period_day_rate(self, date_from, date_to):
        """Public method: Returns daily rate for the payslip period based on scheduled days."""
        self.ensure_one()
        sched_days = self._get_period_scheduled_days(date_from, date_to)
        if sched_days > 0.0:
            return self.wage / sched_days
        divisor = self.standard_working_days_per_month or 26.0
        return self.wage / divisor if divisor else 0.0

    def get_period_overtime_rate(self, date_from, date_to):
        """Public method: Returns hourly overtime rate for the payslip period."""
        self.ensure_one()
        if not self.pay_by_attendance or not self.pay_overtime:
            return 0.0
        if self.overtime_rate_manually_set:
            return self.overtime_rate_per_hour or 0.0
        if not self.salary_calculation_type or self.salary_calculation_type == 'fixed':
            sched_hrs = self._get_period_scheduled_hours(date_from, date_to)
            base_hourly = (self.wage / sched_hrs) if sched_hrs > 0.0 else 0.0
            return base_hourly * (self.overtime_multiplier or 1.0)
        return self.overtime_rate_per_hour or self.overtime_hourly_rate or 0.0

    def action_reset_to_computed_rates(self):
        for rec in self:
            divisor = rec.standard_working_days_per_month * rec.standard_hours_per_day
            computed_hourly = rec.wage / divisor if divisor else 0.0
            rec.write({
                'overtime_rate_manually_set': False,
                'shortage_rate_manually_set': False,
                'overtime_rate_per_hour': computed_hourly * rec.overtime_multiplier,
                'shortage_deduction_rate_per_hour': computed_hourly,
            })

    @api.model
    def _get_whitelist_fields_from_template(self):
        res = super(HrVersion, self)._get_whitelist_fields_from_template() if hasattr(super(HrVersion, self), '_get_whitelist_fields_from_template') else []
        res.extend([
            'basic_salary', 'hra', 'da', 'travel_allowance', 'meal_allowance',
            'medical_allowance', 'other_allowance', 'fixed_allowance',
            'pay_by_attendance', 'salary_calculation_type',
        ])
        return list(set(res))
