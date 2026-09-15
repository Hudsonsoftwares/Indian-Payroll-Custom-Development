# -*- coding: utf-8 -*-
import re
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _auto_init(self):
        self._ensure_hds_in_columns()
        return super()._auto_init()

    @api.model
    def _ensure_hds_in_columns(self):
        """Ensures all hds_in fields on res_company exist in PostgreSQL to prevent UndefinedColumn errors."""
        if getattr(self.env.registry, '_hds_in_company_cols_synced', False):
            return
        columns_to_ensure = [
            ('hds_in_is_india_company', 'BOOLEAN'),
            ('hds_in_epf_applicable', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_epf_employer_id', 'VARCHAR'),
            ('hds_in_eps_applicable', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_edli_applicable', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_edli_registration_number', 'VARCHAR'),
            ('hds_in_enable_statutory_audit', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_esic_applicable', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_esic_employer_code', 'VARCHAR'),
            ('hds_in_esic_registration_no', 'VARCHAR'),
            ('hds_in_esic_branch_office', 'VARCHAR'),
            ('hds_in_enable_lwf', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_lwf_registration_no', 'VARCHAR'),
            ('hds_in_enable_gratuity', 'BOOLEAN DEFAULT FALSE'),
            ('hds_in_gratuity_registration_no', 'VARCHAR'),
            ('hds_in_enable_professional_tax', 'BOOLEAN DEFAULT FALSE'),
            ('hds_in_professional_tax_registration_no', 'VARCHAR'),
            ('hds_in_tds_applicable', 'BOOLEAN DEFAULT FALSE'),
            ('hds_in_tan', 'VARCHAR(10)'),
            ('hds_in_default_tax_regime', 'VARCHAR'),
            ('hds_in_default_tax_year', 'INTEGER'),
            ('hds_in_enable_leave_encashment', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_leave_encashment_registration_no', 'VARCHAR'),
            ('hds_in_enable_notice_pay_settlement', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_notice_period_unit', "VARCHAR DEFAULT 'days'"),
            ('hds_in_regular_struct_id', 'INTEGER'),
            ('hds_in_bonus_struct_id', 'INTEGER'),
            ('hds_in_retention_min_service_months', 'INTEGER DEFAULT 12'),
            ('hds_in_retention_exclude_notice_period', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_bonus_apply_tds', 'BOOLEAN DEFAULT TRUE'),
            ('hds_in_bonus_apply_pf', 'BOOLEAN DEFAULT FALSE'),
            ('hds_in_bonus_apply_esi', 'BOOLEAN DEFAULT FALSE'),
            ('hds_in_bonus_apply_pt', 'BOOLEAN DEFAULT FALSE'),
        ]
        try:
            for col, col_def in columns_to_ensure:
                self.env.cr.execute(f"ALTER TABLE res_company ADD COLUMN IF NOT EXISTS {col} {col_def};")
            self.env.registry._hds_in_company_cols_synced = True
        except Exception:
            pass

    def fetch(self, field_names=None):
        if not getattr(self.env.registry, '_hds_in_company_cols_synced', False):
            self._ensure_hds_in_columns()
        return super().fetch(field_names=field_names)

    hds_in_is_india_company = fields.Boolean(
        string="Is India Company",
        compute='_compute_hds_in_is_india_company',
        store=True,
        help="Technical flag indicating whether company country is India (IN)."
    )

    @api.depends('country_id', 'country_id.code')
    def _compute_hds_in_is_india_company(self):
        for company in self:
            company.hds_in_is_india_company = bool(
                company.country_id and company.country_id.code == 'IN'
            )

    hds_in_epf_applicable = fields.Boolean(
        string="EPF Applicable",
        default=True,
        help="Enable Employee Provident Fund (EPF) calculations."
    )
    hds_in_epf_employer_id = fields.Char(
        string="EPF Employer ID",
        help="Employer Establishment Code for EPF."
    )
    hds_in_eps_applicable = fields.Boolean(
        string="EPS Applicable",
        help="Enable Employee Pension Scheme (EPS) calculations."
    )
    hds_in_edli_applicable = fields.Boolean(
        string="EDLI Applicable",
        help="Enable Employee Deposit Linked Insurance (EDLI) calculations."
    )
    hds_in_edli_registration_number = fields.Char(
        string="EDLI Registration Number",
        help="Registration/Policy Number for EDLI."
    )
    hds_in_enable_statutory_audit = fields.Boolean(
        string="Enable Statutory Calculation Audit Logging",
        default=True,
        help="Record detailed calculation input/output/parameter audit logs for statutory compliance."
    )

    # ESIC Company Configuration Fields
    hds_in_esic_applicable = fields.Boolean(
        string="Enable ESIC",
        default=True,
        help="Enable Employee State Insurance (ESIC) statutory compliance for this company."
    )
    hds_in_esic_employer_code = fields.Char(
        string="ESIC Employer Code",
        help="Enter the Employer Code allotted by the Employees' State Insurance Corporation."
    )
    hds_in_esic_registration_no = fields.Char(
        string="ESIC Registration Number",
        help="Enter the ESIC Registration Number of the company."
    )
    hds_in_esic_branch_office = fields.Char(
        string="ESIC Branch Office",
        help="Optional. Specify the ESIC Branch/Sub Office associated with this employer."
    )

    # LWF Company Configuration Fields
    hds_in_enable_lwf = fields.Boolean(
        string="Enable Labour Welfare Fund (LWF)",
        default=True,
        help="Enable Labour Welfare Fund (LWF) statutory compliance for this company."
    )
    hds_in_lwf_registration_no = fields.Char(
        string="LWF Registration Number",
        help="Statutory Registration / Establishment Code under Labour Welfare Fund Act."
    )

    # Gratuity Company Configuration Fields
    hds_in_enable_gratuity = fields.Boolean(
        string="Enable Gratuity",
        default=False,
        help="Determines whether the company is covered under the Payment of Gratuity Act."
    )
    hds_in_gratuity_registration_no = fields.Char(
        string="Gratuity Registration Number",
        help="Stores the company's gratuity registration/reference number for statutory records."
    )

    # Professional Tax (PT) Company Configuration Fields
    hds_in_enable_professional_tax = fields.Boolean(
        string="Enable Professional Tax",
        default=False,
        help="Determines whether the company is liable to deduct Professional Tax."
    )
    hds_in_professional_tax_registration_no = fields.Char(
        string="Professional Tax Registration Number",
        help="Stores the company's Professional Tax Registration Number (PTRC/PTEC or equivalent, depending on the state)."
    )

    # Tax Deducted at Source (TDS) Company Configuration Fields
    hds_in_tds_applicable = fields.Boolean(
        string="Enable TDS",
        default=False,
        help="Master switch to enable or disable Tax Deducted at Source (TDS) for the company. When disabled, TDS services skip all tax calculations."
    )
    hds_in_tan = fields.Char(
        string="TAN",
        size=10,
        help="Tax Deduction and Collection Account Number allotted by the Income Tax Department (10 characters, e.g. ABCD12345E)."
    )
    hds_in_default_tax_regime = fields.Selection(
        selection=[
            ('new', 'New Regime'),
            ('old', 'Old Regime'),
        ],
        string="Default Tax Regime",
        default='new',
        help="Determines the default tax regime assigned to newly created employees."
    )
    hds_in_default_tax_year = fields.Many2one(
        'tds.financial.year',
        string="Default Tax Year",
        help="Stores the company's active/default tax year for TDS calculations."
    )

    # Leave Encashment Company Configuration Fields
    hds_in_enable_leave_encashment = fields.Boolean(
        string="Enable Leave Encashment",
        default=True,
        help="Enable Leave Encashment statutory and policy calculations for this company."
    )
    hds_in_leave_encashment_registration_no = fields.Char(
        string="Leave Encashment Policy Number",
        help="Optional registration or policy reference for Leave Encashment."
    )

    # Notice Pay Company Configuration Fields
    hds_in_enable_notice_pay_settlement = fields.Boolean(
        string="Enable Notice Pay Settlement",
        default=True,
        help="When enabled, Notice Pay earnings or shortfall recovery will be calculated in Final Settlement."
    )
    hds_in_notice_period_unit = fields.Selection([
        ('days', 'Days'),
        ('months', 'Months'),
    ], string="Notice Period Unit", default='days', required=True,
       help="Unit for company contract expiration notice period (Days or Calendar Months).")

    def compute_notice_period_end_date(self, start_date, notice_period_val=None, unit=None):
        """
        Calculates the notice period end date based on start_date, notice_period_val, and unit ('days' or 'months')
        using calendar-month semantics for Months.
        """
        if not start_date:
            return False
        val = notice_period_val if notice_period_val is not None else getattr(self, 'contract_expiration_notice_period', 0)
        u = unit or getattr(self, 'hds_in_notice_period_unit', 'days') or 'days'
        s_date = fields.Date.from_string(start_date)

        if u == 'months':
            from dateutil.relativedelta import relativedelta
            return s_date + relativedelta(months=int(val or 0))
        else:
            from datetime import timedelta
            return s_date + timedelta(days=int(val or 0))

    # Payroll & Bonus Management Configuration Fields
    hds_in_regular_struct_id = fields.Many2one(
        'hr.payroll.structure',
        string="Regular Payroll Structure",
        help="Default Salary Structure used for regular monthly payroll processing."
    )
    hds_in_bonus_struct_id = fields.Many2one(
        'hr.payroll.structure',
        string="Bonus Payroll Structure",
        help="Default Salary Structure used for separate bonus payroll processing."
    )
    hds_in_retention_min_service_months = fields.Integer(
        string="Retention Bonus Min Service (Months)",
        default=12,
        help="Minimum months of service required for Retention Bonus eligibility."
    )
    hds_in_retention_exclude_notice_period = fields.Boolean(
        string="Exclude Notice Period from Retention Bonus",
        default=True,
        help="If checked, employees currently serving notice period will not be eligible for Retention Bonus."
    )
    hds_in_bonus_apply_tds = fields.Boolean(
        string="Apply TDS on Bonus",
        default=True,
        help="If checked, Tax Deducted at Source (TDS) applies to bonuses (Performance & Retention Bonus)."
    )
    hds_in_bonus_apply_pf = fields.Boolean(
        string="Apply PF on Bonus",
        default=False,
        help="If checked, Provident Fund (PF) rule applies to Bonus Payroll."
    )
    hds_in_bonus_apply_esi = fields.Boolean(
        string="Apply ESI on Bonus",
        default=False,
        help="If checked, Employee State Insurance (ESI) rule applies to Bonus Payroll."
    )
    hds_in_bonus_apply_pt = fields.Boolean(
        string="Apply Professional Tax on Bonus",
        default=False,
        help="If checked, Professional Tax (PT) rule applies to Bonus Payroll."
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('hds_in_tan'):
                vals['hds_in_tan'] = vals['hds_in_tan'].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('hds_in_tan'):
            vals['hds_in_tan'] = vals['hds_in_tan'].strip().upper()
        return super().write(vals)
