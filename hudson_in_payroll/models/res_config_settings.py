# -*- coding: utf-8 -*-
import re
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hds_in_epf_applicable = fields.Boolean(
        related='company_id.hds_in_epf_applicable',
        readonly=False,
        string="EPF Applicable"
    )
    hds_in_epf_employer_id = fields.Char(
        related='company_id.hds_in_epf_employer_id',
        readonly=False,
        string="EPF Employer ID"
    )
    hds_in_eps_applicable = fields.Boolean(
        related='company_id.hds_in_eps_applicable',
        readonly=False,
        string="EPS Applicable"
    )
    hds_in_edli_applicable = fields.Boolean(
        related='company_id.hds_in_edli_applicable',
        readonly=False,
        string="EDLI Applicable"
    )
    hds_in_edli_registration_number = fields.Char(
        related='company_id.hds_in_edli_registration_number',
        readonly=False,
        string="EDLI Registration Number"
    )
    hds_in_enable_statutory_audit = fields.Boolean(
        related='company_id.hds_in_enable_statutory_audit',
        readonly=False,
        string="Enable Statutory Audit Logging"
    )

    # ESIC Company Configuration Related Fields
    hds_in_esic_applicable = fields.Boolean(
        related='company_id.hds_in_esic_applicable',
        readonly=False,
        string="Enable ESIC"
    )
    hds_in_esic_employer_code = fields.Char(
        related='company_id.hds_in_esic_employer_code',
        readonly=False,
        string="ESIC Employer Code"
    )
    hds_in_esic_registration_no = fields.Char(
        related='company_id.hds_in_esic_registration_no',
        readonly=False,
        string="ESIC Registration Number"
    )
    hds_in_esic_branch_office = fields.Char(
        related='company_id.hds_in_esic_branch_office',
        readonly=False,
        string="ESIC Branch Office"
    )

    # LWF Company Configuration Related Fields
    hds_in_enable_lwf = fields.Boolean(
        related='company_id.hds_in_enable_lwf',
        readonly=False,
        string="Enable Labour Welfare Fund (LWF)"
    )
    hds_in_lwf_registration_no = fields.Char(
        related='company_id.hds_in_lwf_registration_no',
        readonly=False,
        string="LWF Registration Number"
    )

    # Gratuity Company Configuration Related Fields
    hds_in_enable_gratuity = fields.Boolean(
        related='company_id.hds_in_enable_gratuity',
        readonly=False,
        string="Enable Gratuity"
    )
    hds_in_gratuity_registration_no = fields.Char(
        related='company_id.hds_in_gratuity_registration_no',
        readonly=False,
        string="Gratuity Registration Number"
    )

    # Leave Encashment Company Configuration Related Fields
    hds_in_enable_leave_encashment = fields.Boolean(
        related='company_id.hds_in_enable_leave_encashment',
        readonly=False,
        string="Enable Leave Encashment"
    )
    hds_in_leave_encashment_registration_no = fields.Char(
        related='company_id.hds_in_leave_encashment_registration_no',
        readonly=False,
        string="Leave Encashment Policy Number"
    )

    # Professional Tax (PT) Company Configuration Related Fields
    hds_in_enable_professional_tax = fields.Boolean(
        related='company_id.hds_in_enable_professional_tax',
        readonly=False,
        string="Enable Professional Tax"
    )
    hds_in_professional_tax_registration_no = fields.Char(
        related='company_id.hds_in_professional_tax_registration_no',
        readonly=False,
        string="Professional Tax Registration Number"
    )

    # Tax Deducted at Source (TDS) Company Configuration Related Fields
    hds_in_tds_applicable = fields.Boolean(
        related='company_id.hds_in_tds_applicable',
        readonly=False,
        string="Enable TDS"
    )
    hds_in_tan = fields.Char(
        related='company_id.hds_in_tan',
        readonly=False,
        string="TAN"
    )
    hds_in_default_tax_regime = fields.Selection(
        related='company_id.hds_in_default_tax_regime',
        readonly=False,
        string="Default Tax Regime"
    )
    hds_in_default_tax_year = fields.Many2one(
        related='company_id.hds_in_default_tax_year',
        readonly=False,
        string="Default Tax Year"
    )
    tds_month_division = fields.Integer(
        related='hds_in_default_tax_year.tds_month_division',
        readonly=False,
        string="TDS Month Division",
        help="Number of months to divide annual estimated TDS tax liability across regular monthly pay periods."
    )


    # Payroll Structure & Bonus Management Settings
    hds_in_regular_struct_id = fields.Many2one(
        related='company_id.hds_in_regular_struct_id',
        readonly=False,
        string="Regular Payroll Structure"
    )
    hds_in_bonus_struct_id = fields.Many2one(
        related='company_id.hds_in_bonus_struct_id',
        readonly=False,
        string="Bonus Payroll Structure"
    )
    # Retention Bonus Settings
    hds_in_retention_min_service_months = fields.Integer(
        related='company_id.hds_in_retention_min_service_months',
        readonly=False,
        string="Retention Bonus Min Service (Months)"
    )
    hds_in_retention_exclude_notice_period = fields.Boolean(
        related='company_id.hds_in_retention_exclude_notice_period',
        readonly=False,
        string="Exclude Notice Period from Bonus"
    )
    hds_in_bonus_apply_tds = fields.Boolean(
        related='company_id.hds_in_bonus_apply_tds',
        readonly=False,
        string="Apply TDS on Bonus"
    )
    hds_in_bonus_apply_pf = fields.Boolean(
        related='company_id.hds_in_bonus_apply_pf',
        readonly=False,
        string="Apply PF"
    )
    hds_in_bonus_apply_esi = fields.Boolean(
        related='company_id.hds_in_bonus_apply_esi',
        readonly=False,
        string="Apply ESI"
    )
    hds_in_bonus_apply_pt = fields.Boolean(
        related='company_id.hds_in_bonus_apply_pt',
        readonly=False,
        string="Apply Professional Tax"
    )

    # Notice Pay Settlement Configuration Related Fields
    contract_expiration_notice_period = fields.Integer(
        related='company_id.contract_expiration_notice_period',
        readonly=False,
        string="Notice Period Length"
    )
    hds_in_enable_notice_pay_settlement = fields.Boolean(
        related='company_id.hds_in_enable_notice_pay_settlement',
        readonly=False,
        string="Enable Notice Pay Settlement"
    )
    hds_in_notice_period_unit = fields.Selection(
        related='company_id.hds_in_notice_period_unit',
        readonly=False,
        string="Notice Period Unit"
    )

    hds_in_is_india_company = fields.Boolean(
        string="Is India Company",
        compute='_compute_hds_in_is_india_company'
    )

    @api.depends('company_id', 'company_id.country_id')
    def _compute_hds_in_is_india_company(self):
        for record in self:
            country = record.company_id.country_id
            record.hds_in_is_india_company = bool(
                country and country.code == 'IN'
            )

    def set_values(self):
        tan_pattern = re.compile(r'^[A-Z]{4}[0-9]{5}[A-Z]{1}$')
        for record in self:
            if record.hds_in_tds_applicable:
                tan = (record.hds_in_tan or '').strip().upper()
                if not tan:
                    raise ValidationError(_(
                        "TAN (Tax Deduction and Collection Account Number) is mandatory when TDS is enabled."
                    ))
                if not tan_pattern.match(tan):
                    raise ValidationError(_(
                        "Invalid TAN format '%s'. TAN must be 10 characters long with 4 uppercase letters, 5 digits, and 1 letter (e.g. ABCD12345E)."
                    ) % record.hds_in_tan)
                if not record.hds_in_default_tax_regime:
                    raise ValidationError(_(
                        "Default Tax Regime is mandatory when TDS is enabled."
                    ))
                record.hds_in_tan = tan
        super().set_values()
