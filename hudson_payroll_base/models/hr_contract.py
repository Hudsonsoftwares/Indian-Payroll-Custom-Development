# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContract(models.Model):
    """Extension of employee contract (hr.version in Odoo 19) to link salary structures and pay frequencies."""
    _inherit = 'hr.version'

    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Salary Structure',
        help="Default salary structure applied to this employee contract"
    )
    structure_type_id = fields.Many2one(
        'hr.payroll.structure.type',
        string='Structure Type',
        help="Category defining pay rules and statutory defaults"
    )
    schedule_pay = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi-annually', 'Semi-annually'),
        ('annually', 'Annually'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-weekly'),
        ('bi-monthly', 'Bi-monthly'),
    ], string='Scheduled Pay', default='monthly', index=True)

    # Salary Breakdown Components
    basic_salary = fields.Monetary(string='Basic Salary', tracking=True)
    hra = fields.Monetary(string='House Rent Allowance', tracking=True, help="House Rent Allowance")
    da = fields.Monetary(string='Dearness Allowance', tracking=True, help="Dearness Allowance")
    standard_allowance = fields.Monetary(string='Standard Allowance', tracking=True)
    performance_bonus = fields.Monetary(string='Performance Bonus', tracking=True)
    lta_allowance = fields.Monetary(string='Leave Travel Allowance', tracking=True, help="Monthly Leave Travel Allowance (LTA)")
    travel_allowance = fields.Monetary(string='Travel Allowance')
    meal_allowance = fields.Monetary(string='Meal Allowance')
    medical_allowance = fields.Monetary(string='Medical Allowance')
    other_allowance = fields.Monetary(string='Other Allowance')
    fixed_allowance = fields.Monetary(string='Fixed Allowance', tracking=True)
    pay_by_attendance = fields.Boolean(
        string='Pay by Attendance',
        default=True,
        tracking=True,
        help="If enabled, attendance adjustments (overtime / shortage) apply to payslips."
    )

    # Breakdown Percentages
    basic_salary_percent = fields.Float(string='Basic %', compute='_compute_breakdown_percentages', digits=(16, 2))
    hra_percent = fields.Float(string='HRA %', compute='_compute_breakdown_percentages', digits=(16, 2))
    da_percent = fields.Float(string='DA %', compute='_compute_breakdown_percentages', digits=(16, 2))
    standard_allowance_percent = fields.Float(string='Standard Allowance %', compute='_compute_breakdown_percentages', digits=(16, 2))
    performance_bonus_percent = fields.Float(string='Performance Bonus %', compute='_compute_breakdown_percentages', digits=(16, 2))
    lta_percent = fields.Float(string='LTA %', compute='_compute_breakdown_percentages', digits=(16, 2))
    travel_allowance_percent = fields.Float(string='Travel %', compute='_compute_breakdown_percentages', digits=(16, 2))
    meal_allowance_percent = fields.Float(string='Meal %', compute='_compute_breakdown_percentages', digits=(16, 2))
    medical_allowance_percent = fields.Float(string='Medical %', compute='_compute_breakdown_percentages', digits=(16, 2))
    other_allowance_percent = fields.Float(string='Other %', compute='_compute_breakdown_percentages', digits=(16, 2))
    fixed_allowance_percent = fields.Float(string='Fixed %', compute='_compute_breakdown_percentages', digits=(16, 2))

    # Breakdown Totals & Validation
    breakdown_total = fields.Monetary(string='Total Breakdown', compute='_compute_breakdown_totals')
    breakdown_diff = fields.Monetary(string='Difference', compute='_compute_breakdown_totals')
    breakdown_is_equal = fields.Boolean(string='Is Valid Breakdown', compute='_compute_breakdown_totals')

    # Country & Localization Flags
    company_country_code = fields.Char(
        string="Company Country Code",
        related='company_id.country_id.code',
        readonly=True,
        store=True
    )
    country_code = fields.Char(
        string="Country Code",
        compute='_compute_country_code',
        store=True,
        readonly=True
    )
    is_india_localization = fields.Boolean(
        string="Is India Localization",
        compute='_compute_country_code',
        store=True
    )
    is_uae_localization = fields.Boolean(
        string="Is UAE Localization",
        compute='_compute_country_code',
        store=True
    )

    @api.depends('company_id.country_id.code', 'structure_type_id.country_id.code')
    def _compute_country_code(self):
        for rec in self:
            code = (
                (rec.structure_type_id.country_id and rec.structure_type_id.country_id.code)
                or (rec.company_id and rec.company_id.country_id and rec.company_id.country_id.code)
                or (self.env.company.country_id and self.env.company.country_id.code)
                or ''
            )
            rec.country_code = code.upper() if code else ''
            rec.is_india_localization = (rec.country_code == 'IN')
            rec.is_uae_localization = (rec.country_code == 'AE')

    @api.depends('wage', 'basic_salary', 'hra', 'da', 'standard_allowance', 'performance_bonus', 'lta_allowance',
                 'travel_allowance', 'meal_allowance', 'medical_allowance', 'other_allowance', 'fixed_allowance')
    def _compute_breakdown_percentages(self):
        for rec in self:
            total = rec.wage or 0.0
            if total > 0.0:
                rec.basic_salary_percent = ((rec.basic_salary or 0.0) / total) * 100.0
                rec.hra_percent = ((rec.hra or 0.0) / total) * 100.0
                rec.da_percent = ((rec.da or 0.0) / total) * 100.0
                rec.standard_allowance_percent = ((rec.standard_allowance or 0.0) / total) * 100.0
                rec.performance_bonus_percent = ((rec.performance_bonus or 0.0) / total) * 100.0
                rec.lta_percent = ((rec.lta_allowance or 0.0) / total) * 100.0
                rec.travel_allowance_percent = ((rec.travel_allowance or 0.0) / total) * 100.0
                rec.meal_allowance_percent = ((rec.meal_allowance or 0.0) / total) * 100.0
                rec.medical_allowance_percent = ((rec.medical_allowance or 0.0) / total) * 100.0
                rec.other_allowance_percent = ((rec.other_allowance or 0.0) / total) * 100.0
                rec.fixed_allowance_percent = ((rec.fixed_allowance or 0.0) / total) * 100.0
            else:
                rec.basic_salary_percent = 0.0
                rec.hra_percent = 0.0
                rec.da_percent = 0.0
                rec.standard_allowance_percent = 0.0
                rec.performance_bonus_percent = 0.0
                rec.lta_percent = 0.0
                rec.travel_allowance_percent = 0.0
                rec.meal_allowance_percent = 0.0
                rec.medical_allowance_percent = 0.0
                rec.other_allowance_percent = 0.0
                rec.fixed_allowance_percent = 0.0

    @api.depends('wage', 'basic_salary', 'hra', 'da', 'standard_allowance', 'performance_bonus', 'lta_allowance',
                 'travel_allowance', 'meal_allowance', 'medical_allowance', 'other_allowance', 'fixed_allowance')
    def _compute_breakdown_totals(self):
        for rec in self:
            parts = (
                (rec.basic_salary or 0.0) +
                (rec.hra or 0.0) +
                (rec.da or 0.0) +
                (rec.standard_allowance or 0.0) +
                (rec.performance_bonus or 0.0) +
                (rec.lta_allowance or 0.0) +
                (rec.travel_allowance or 0.0) +
                (rec.meal_allowance or 0.0) +
                (rec.medical_allowance or 0.0) +
                (rec.other_allowance or 0.0) +
                (rec.fixed_allowance or 0.0)
            )
            rec.breakdown_total = parts
            rec.breakdown_diff = (rec.wage or 0.0) - parts
            rec.breakdown_is_equal = abs(rec.breakdown_diff) < 0.01

    @api.onchange('structure_type_id')
    def _onchange_structure_type_id(self):
        if self.structure_type_id:
            default_struct = self.structure_type_id.default_struct_id or self.env['hr.payroll.structure'].search([
                ('type_id', '=', self.structure_type_id.id)
            ], limit=1)
            if default_struct:
                self.struct_id = default_struct
            if self.structure_type_id.schedule_pay:
                self.schedule_pay = self.structure_type_id.schedule_pay
