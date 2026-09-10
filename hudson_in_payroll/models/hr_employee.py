# -*- coding: utf-8 -*-
import re
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    previous_lta_history_ids = fields.One2many(
        'tds.lta.previous.employer',
        'employee_id',
        string="Previous Employer LTA History",
        help="Historical LTA usage records under previous employers to verify carry-forward entitlement."
    )
    house_property_loss_ids = fields.One2many(
        'tds.house.property.loss.carryforward',
        'employee_id',
        string="House Property Loss Carry-Forward (71B)",
        help="Unabsorbed House Property losses carried forward under Section 71B for inter-year set-off."
    )

    # EPF / UAN Information
    hds_in_epf_applicable = fields.Boolean(
        string="EPF Applicable",
        default=True,
        help="Enable EPF statutory deductions for this employee."
    )
    hds_in_uan = fields.Char(
        string="UAN (Universal Account Number)",
        help="12-digit EPFO Universal Account Number."
    )
    hds_in_pf_member_id = fields.Char(
        string="PF Member ID / Member Code",
        help="Establishment Member ID (e.g. MH/BAN/0012345/000/0000123)."
    )
    hds_in_pf_joining_date = fields.Date(
        string="Date of Joining PF",
        help="Date employee first enrolled in Provident Fund."
    )
    hds_in_existing_epf_member = fields.Boolean(
        string="Existing EPF Member",
        default=True,
        help="Check if employee had a prior EPF account before joining this company."
    )
    hds_in_is_international_worker = fields.Boolean(
        string="International Worker",
        default=False,
        help="Check if employee is classified as an International Worker under EPFO rules."
    )

    # EPS (Pension) Information
    hds_in_eps_applicable = fields.Boolean(
        string="EPS Applicable",
        default=True,
        help="Enable EPS statutory pension allocation (8.33%)."
    )
    hds_in_existing_eps_member = fields.Boolean(
        string="Existing EPS Member",
        default=True,
        help="Check if employee was enrolled in EPS scheme prior to 01-Sep-2014 or current joining."
    )
    hds_in_higher_pension = fields.Boolean(
        string="Opted for Higher Pension Scheme",
        default=False,
        help="Check if employee opted for higher pension scheme under SC judgment guidelines."
    )
    hds_in_pf_contribution_basis = fields.Selection([
        ('statutory_ceiling', 'Statutory Ceiling (₹15,000 Cap)'),
        ('actual_pf_wage', 'Actual PF Wage (Uncapped)'),
        ('statutory_restricted', 'Statutory Restricted (Legacy Cap)'),
        ('actual_basic', 'Actual Basic Pay (Legacy Uncapped)'),
    ], string="PF Contribution Basis", default='statutory_ceiling', required=True)

    # VPF (Voluntary Provident Fund)
    hds_in_vpf_type = fields.Selection([
        ('none', 'None'),
        ('percent', 'Percentage of Basic Pay'),
        ('fixed', 'Fixed Monthly Amount'),
    ], string="VPF Contribution Type", default='none', required=True)

    hds_in_vpf_percent = fields.Float(
        string="VPF Percentage (%)",
        help="Additional VPF percentage contributed by employee."
    )
    hds_in_vpf_amount = fields.Float(
        string="VPF Fixed Amount (₹)",
        help="Additional VPF fixed amount contributed by employee."
    )

    # ESIC Information
    hds_in_esic_applicable = fields.Boolean(
        string="ESIC Applicable",
        default=False,
        help="Enable Employees' State Insurance (ESIC) statutory compliance for this employee."
    )
    hds_in_esic_ip_number = fields.Char(
        string="ESIC IP Number",
        help="17-digit ESIC Insured Person (IP) Number."
    )
    hds_in_esic_joining_date = fields.Date(
        string="Date of Joining ESIC",
        help="Date of enrollment into ESIC."
    )
    hds_in_esic_exit_date = fields.Date(
        string="Date of Exit ESIC",
        help="Date of exit from ESIC scheme."
    )
    hds_in_esic_ip_status = fields.Selection([
        ('active', 'Active'),
        ('exempt', 'Exempt'),
        ('resigned', 'Resigned'),
        ('disabled', 'Disabled'),
    ], string="Insured Person Status", default='active', help="Current ESIC Insured Person (IP) compliance status.")

    hds_in_is_pwd = fields.Boolean(
        string="Person with Disability (PWD)",
        default=False,
        help="Indicates that the employee is eligible for the statutory ESIC PWD wage ceiling limit."
    )

    hds_in_esic_contribution_basis = fields.Char(
        string="Contribution Basis",
        readonly=True,
        default="Gross Wages (Statutory)",
        help="ESIC contribution basis is calculated on gross wages per statutory rules."
    )
    hds_in_esic_contribution_period = fields.Char(
        string="Contribution Period",
        compute='_compute_esic_contribution_period',
        store=True,
        readonly=True,
        help="Half-yearly ESIC statutory contribution period derived automatically from joining date or current date."
    )
    hds_in_esic_dispensary = fields.Char(
        string="ESIC Dispensary",
        help="Nominated ESIC Dispensary / Medical Benefit Hospital."
    )
    hds_in_esic_exit_reason = fields.Selection([
        ('wage_exceeded', 'Salary Exceeded Limit'),
        ('resigned', 'Resigned'),
        ('death', 'Death'),
        ('retired', 'Retired'),
        ('other', 'Other'),
    ], string="Reason for Exit ESIC", help="Reason for exit from ESIC coverage.")

    # Labour Welfare Fund (LWF) Information
    hds_in_lwf_applicable = fields.Boolean(
        string="LWF Applicable",
        default=True,
        help="Enable Labour Welfare Fund (LWF) statutory deductions for this employee."
    )
    hds_in_lwf_number = fields.Char(
        string="LWF Employee / Registration Number",
        help="Labour Welfare Fund Registration or Employee Number."
    )

    # Professional Tax (PT) Information
    hds_in_pt_applicable = fields.Boolean(
        string="Professional Tax (PT) Applicable",
        default=True,
        help="Enable Professional Tax (PT) statutory deduction for this employee based on state slab rules."
    )

    @api.constrains('hds_in_epf_applicable', 'hds_in_uan')
    def _check_hds_in_uan_format(self):
        for emp in self:
            if emp.hds_in_epf_applicable and emp.hds_in_uan:
                uan_clean = emp.hds_in_uan.strip()
                if not uan_clean.isdigit():
                    raise ValidationError(_("EPF UAN must contain digits only. Invalid value: '%s'") % emp.hds_in_uan)
                if len(uan_clean) != 12:
                    raise ValidationError(_("EPF UAN must be exactly 12 digits. Provided length: %d digits.") % len(uan_clean))
                duplicate = self.search([
                    ('id', '!=', emp.id),
                    ('hds_in_uan', '=', uan_clean)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("EPF UAN '%s' is already registered for employee '%s'. Duplicate UANs are prohibited.") % (uan_clean, duplicate.name))

    hds_in_employer_cost_monthly = fields.Monetary(
        string="Employer Cost (Monthly)",
        compute='_compute_hds_in_employer_cost',
        currency_field='currency_id',
        store=True,
        readonly=True,
        help="Monthly Employer Cost to Company (CTC) synced directly from active contract."
    )
    hds_in_employer_cost_annual = fields.Monetary(
        string="Employer Cost (Annual)",
        compute='_compute_hds_in_employer_cost',
        currency_field='currency_id',
        store=True,
        readonly=True,
        help="Annual Employer Cost to Company (CTC) synced directly from active contract."
    )

    hds_in_statutory_audit_count = fields.Integer(
        string="Statutory Audits Count",
        compute='_compute_hds_in_statutory_audit_count'
    )

    @api.depends('hds_in_esic_joining_date', 'hds_in_esic_applicable')
    def _compute_esic_contribution_period(self):
        today = fields.Date.today()
        for emp in self:
            if not emp.hds_in_esic_applicable:
                emp.hds_in_esic_contribution_period = False
                continue
            ref_date = emp.hds_in_esic_joining_date or today
            year = ref_date.year
            month = ref_date.month
            if 4 <= month <= 9:
                emp.hds_in_esic_contribution_period = f"April {year} – September {year}"
            elif month >= 10:
                emp.hds_in_esic_contribution_period = f"October {year} – March {year + 1}"
            else:
                emp.hds_in_esic_contribution_period = f"October {year - 1} – March {year}"

    def _evaluate_default_esic_applicable(self, gross_wage=None, eval_date=None):
        """
        Evaluates ESIC applicability based on statutory contribution period bounds and period-start wage.
        Enforces Regulation 31 continuity: Gross wage on first day of Contribution Period defines coverage.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company or not company.hds_in_esic_applicable:
            return False

        from ..services.esic.contribution_period_service import ESICContributionPeriodService
        period_service = ESICContributionPeriodService(self.env)
        return period_service.is_covered_for_contribution_period(self, eval_date=eval_date, current_wage=gross_wage)

    @api.onchange('hds_in_is_pwd', 'company_id')
    def _onchange_esic_default_triggers(self):
        """Triggered on employee form when PWD status or company changes."""
        for emp in self:
            emp.hds_in_esic_applicable = emp._evaluate_default_esic_applicable()

    @api.constrains('hds_in_esic_applicable', 'hds_in_esic_ip_number')
    def _check_esic_ip_number(self):
        for emp in self:
            if emp.hds_in_esic_applicable and emp.hds_in_esic_ip_number:
                ip_clean = emp.hds_in_esic_ip_number.strip()
                if not ip_clean.isdigit():
                    raise ValidationError(_("ESIC IP Number must contain digits only. Invalid value: '%s'") % emp.hds_in_esic_ip_number)
                if len(ip_clean) != 17:
                    raise ValidationError(_("ESIC IP Number must be exactly 17 digits. Provided length: %d digits.") % len(ip_clean))
                duplicate = self.search([
                    ('id', '!=', emp.id),
                    ('hds_in_esic_ip_number', '=', ip_clean)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("ESIC IP Number '%s' is already registered for employee '%s'. Duplicate IP numbers are not allowed.") % (ip_clean, duplicate.name))

    def _compute_hds_in_employer_cost(self):
        for emp in self:
            contracts = self.env['hr.version'].search([('employee_id', '=', emp.id)])
            active_contract = contracts.sorted(lambda c: c.date_start or fields.Date.today(), reverse=True)[0] if contracts else False
            monthly_cost = active_contract.hds_in_employer_cost_monthly if active_contract else 0.0
            emp.hds_in_employer_cost_monthly = monthly_cost
            emp.hds_in_employer_cost_annual = monthly_cost * 12.0

    def _compute_hds_in_statutory_audit_count(self):
        for emp in self:
            emp.hds_in_statutory_audit_count = self.env['hds.in.payroll.audit'].search_count([
                ('employee_id', '=', emp.id)
            ])

    def action_view_statutory_audits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Statutory Audit Logs'),
            'res_model': 'hds.in.payroll.audit',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_open_tax_declaration_dashboard(self):
        """
        Smart Button Action on Employee Profile ('Tax Declarations').
        Opens the Employee Self-Service Tax Declaration Dashboard for active Financial Year.
        Auto-resolves/creates tds.employee.declaration record for (employee_id, financial_year_id).
        """
        self.ensure_one()
        today = fields.Date.today()
        fy = self.company_id.hds_in_default_tax_year or self.env['tds.financial.year'].search([
            ('start_date', '<=', today),
            ('end_date', '>=', today),
            ('active', '=', True),
            ('is_closed', '=', False)
        ], limit=1)

        if not fy:
            raise ValidationError(_("No active Financial Year configuration exists. Please contact HR to set up the Financial Year."))

        decl = self.env['tds.employee.declaration'].sudo().search([
            ('employee_id', '=', self.id),
            ('financial_year_id', '=', fy.id)
        ], limit=1)

        if not decl:
            decl = self.env['tds.employee.declaration'].sudo().create({
                'employee_id': self.id,
                'financial_year_id': fy.id,
                'state': 'draft',
            })

        # Also ensure regime choice and income declaration records exist
        inc_decl = self.env['tds.employee.income.declaration'].sudo().search([
            ('employee_id', '=', self.id),
            ('financial_year_id', '=', fy.id)
        ], limit=1)
        if not inc_decl:
            self.env['tds.employee.income.declaration'].sudo().create({
                'employee_id': self.id,
                'financial_year_id': fy.id,
            })

        view_id = self.env.ref('hudson_in_payroll.tds_employee_declaration_view_dashboard_form', raise_if_not_found=False)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Employee Tax Declaration Dashboard'),
            'res_model': 'tds.employee.declaration',
            'res_id': decl.id,
            'view_mode': 'form',
            'views': [(view_id.id if view_id else False, 'form')],
            'target': 'current',
        }

    # =========================================================================
    # INCOME TAX (TDS) PROFILE FIELDS
    # =========================================================================
    hds_in_pan = fields.Char(
        string="PAN Number",
        help="10-character Permanent Account Number (e.g. ABCDE1234F)."
    )
    hds_in_aadhaar = fields.Char(
        string="Aadhaar Number",
        help="12-digit Aadhaar Card Number."
    )
    hds_in_tds_applicable = fields.Boolean(
        string="TDS Applicable",
        default=True,
        help="Enable Indian Income Tax (TDS) withholding computation for this employee."
    )
    hds_in_residential_status = fields.Selection([
        ('ror', 'Resident & Ordinarily Resident (ROR)'),
        ('rnor', 'Resident but Not Ordinarily Resident (RNOR)'),
        ('nre', 'Non-Resident Indian (NRI)'),
    ], string="Residential Status", default='ror', required=True, help="Income Tax Act residential compliance status.")

    resident_status = fields.Selection([
        ('resident', 'Resident'),
        ('non_resident', 'Non-Resident'),
    ], string="Income Tax Resident Status", compute='_compute_resident_status', store=True,
       help="Income Tax residential status computed automatically from Residential Status (ROR/RNOR -> Resident, NRE -> Non-Resident).")

    @api.depends('hds_in_residential_status')
    def _compute_resident_status(self):
        for emp in self:
            if emp.hds_in_residential_status in ('ror', 'rnor'):
                emp.resident_status = 'resident'
            elif emp.hds_in_residential_status == 'nre':
                emp.resident_status = 'non_resident'
            else:
                emp.resident_status = 'resident'

    # Previous Employer Income & TDS (For Mid-Year Joiners)
    hds_in_prev_taxable_gross = fields.Monetary(
        string="Previous Employer Taxable Salary (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False,
        help="Gross taxable salary earned from previous employer during current financial year."
    )
    hds_in_prev_tds_deducted = fields.Monetary(
        string="Previous Employer TDS Deducted (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False,
        help="Total TDS tax deducted by previous employer during current financial year."
    )
    hds_in_prev_pt_deducted = fields.Monetary(
        string="Previous Employer PT Deducted (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False,
        help="Professional Tax deducted by previous employer during current financial year."
    )
    hds_in_prev_employer_pf = fields.Monetary(
        string="Previous Employer EPF (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False,
        help="Employer EPF contribution at previous employer during current financial year."
    )
    hds_in_prev_employer_nps = fields.Monetary(
        string="Previous Employer NPS (₹)",
        currency_field='currency_id',
        default=0.0,
        help="Employer NPS contribution at previous employer during current financial year."
    )

    # Tax Regime History One2many
    hds_in_tax_regime_history_ids = fields.One2many(
        'tds.employee.tax.regime',
        'employee_id',
        string="Tax Regime History",
        help="Financial Year specific Tax Regime selections for this employee."
    )

    @api.constrains('hds_in_pan')
    def _check_hds_in_pan_format(self):
        pan_regex = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')
        for emp in self:
            if emp.hds_in_pan:
                pan_clean = emp.hds_in_pan.strip().upper()
                if not pan_regex.match(pan_clean):
                    raise ValidationError(_(
                        "Invalid PAN Number format: '%s'. "
                        "PAN must be exactly 10 characters formatted as 5 uppercase letters, 4 digits, and 1 uppercase letter (e.g. ABCDE1234F)."
                    ) % emp.hds_in_pan)
                duplicate = self.search([
                    ('id', '!=', emp.id),
                    ('hds_in_pan', '=', pan_clean)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        "PAN Number '%s' is already registered for employee '%s'. Duplicate PAN numbers are prohibited."
                    ) % (pan_clean, duplicate.name))

    @api.constrains('hds_in_aadhaar')
    def _check_hds_in_aadhaar_format(self):
        for emp in self:
            if emp.hds_in_aadhaar:
                aadhaar_clean = emp.hds_in_aadhaar.strip()
                if not aadhaar_clean.isdigit() or len(aadhaar_clean) != 12:
                    raise ValidationError(_(
                        "Invalid Aadhaar Number: '%s'. Aadhaar must contain exactly 12 digits."
                    ) % emp.hds_in_aadhaar)

    hds_in_tax_regime_count = fields.Integer(
        string="Tax Regime Selections Count",
        compute='_compute_hds_in_tax_regime_count'
    )

    def _compute_hds_in_tax_regime_count(self):
        for emp in self:
            emp.hds_in_tax_regime_count = self.env['tds.employee.tax.regime'].search_count([
                ('employee_id', '=', emp.id)
            ])

    def action_view_tax_regimes(self):
        """
        Smart Button Action on Employee Profile ('Tax Regimes').
        Auto-resolves current active Financial Year and opens/creates the tds.employee.tax.regime
        record for (employee_id, financial_year_id), defaulting to system default regime if new.
        """
        self.ensure_one()
        today = fields.Date.today()
        fy = self.company_id.hds_in_default_tax_year or self.env['tds.financial.year'].search([
            ('start_date', '<=', today),
            ('end_date', '>=', today),
            ('active', '=', True),
            ('is_closed', '=', False)
        ], limit=1)

        if not fy:
            raise ValidationError(_("No active Financial Year configuration exists. Please configure the default Tax Year in settings."))

        reg_records = self.env['tds.employee.tax.regime'].sudo().search([
            ('employee_id', '=', self.id),
        ])

        active_reg_record = reg_records.filtered(lambda r: r.financial_year_id == fy)

        if not active_reg_record:
            default_regime = self.env['tds.tax.regime'].search([('is_default', '=', True)], limit=1) or self.env['tds.tax.regime'].search([], limit=1)
            active_reg_record = self.env['tds.employee.tax.regime'].sudo().create({
                'employee_id': self.id,
                'financial_year_id': fy.id,
                'regime_id': default_regime.id if default_regime else False,
            })
            reg_records = self.env['tds.employee.tax.regime'].sudo().search([
                ('employee_id', '=', self.id),
            ])

        if len(reg_records) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Financial Year Tax Selection'),
                'res_model': 'tds.employee.tax.regime',
                'res_id': active_reg_record.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {
                    'default_employee_id': self.id,
                    'default_financial_year_id': fy.id,
                }
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Financial Year Tax Selections'),
                'res_model': 'tds.employee.tax.regime',
                'view_mode': 'list,form',
                'domain': [('employee_id', '=', self.id)],
                'target': 'current',
                'context': {
                    'default_employee_id': self.id,
                    'default_financial_year_id': fy.id,
                }
            }

    hds_in_current_fy_id = fields.Many2one(
        'tds.financial.year',
        string="Financial Year",
        compute='_compute_current_fy_regime',
        store=False,
        help="Automatically resolved active Financial Year for current date."
    )
    hds_in_current_tax_regime_id = fields.Many2one(
        'tds.tax.regime',
        string="Selected Tax Regime",
        compute='_compute_current_fy_regime',
        inverse='_inverse_current_tax_regime',
        store=False,
        help="Employee selected Tax Regime for the current Financial Year."
    )
    hds_in_is_new_tax_regime = fields.Boolean(
        string="Is New Tax Regime",
        compute='_compute_current_fy_regime',
        store=False,
        help="Boolean indicator true if employee has selected New Tax Regime for current FY."
    )

    @api.depends_context('company')
    def _compute_current_fy_regime(self):
        today = fields.Date.today()
        default_fy_fallback = self.env['tds.financial.year'].sudo().search([
            ('start_date', '<=', today),
            ('end_date', '>=', today),
            ('active', '=', True),
            ('is_closed', '=', False)
        ], limit=1)

        valid_emp_ids = [e.id for e in self if e.id]
        fy_map = {}
        reg_map = {}

        if valid_emp_ids:
            for emp in self:
                company = emp.company_id or self.env.company
                fy_map[emp.id] = company.hds_in_default_tax_year or default_fy_fallback

            all_fys = list(set(f.id for f in fy_map.values() if f))
            if all_fys:
                all_regs = self.env['tds.employee.tax.regime'].sudo().search([
                    ('employee_id', 'in', valid_emp_ids),
                    ('financial_year_id', 'in', all_fys)
                ])
                for r in all_regs:
                    reg_map[(r.employee_id.id, r.financial_year_id.id)] = r

        for emp in self:
            fy = fy_map.get(emp.id) if emp.id else False
            emp.hds_in_current_fy_id = fy
            if fy and emp.id:
                rec = reg_map.get((emp.id, fy.id))
                reg_id = rec.regime_id if rec else False
                emp.hds_in_current_tax_regime_id = reg_id
                emp.hds_in_is_new_tax_regime = (reg_id.code == 'new') if reg_id else False
            else:
                emp.hds_in_current_tax_regime_id = False
                emp.hds_in_is_new_tax_regime = False

    def _inverse_current_tax_regime(self):
        today = fields.Date.today()
        default_fy_fallback = self.env['tds.financial.year'].sudo().search([
            ('start_date', '<=', today),
            ('end_date', '>=', today),
            ('active', '=', True),
            ('is_closed', '=', False)
        ], limit=1)

        for emp in self:
            company = emp.company_id or self.env.company
            fy = company.hds_in_default_tax_year or default_fy_fallback
            if not fy:
                raise ValidationError(_("No active Financial Year configuration exists. Please configure Default Tax Year under Payroll Settings or generate the active Financial Year using the Roll-Over Wizard."))

            if emp.hds_in_current_tax_regime_id and emp.id:
                rec = self.env['tds.employee.tax.regime'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('financial_year_id', '=', fy.id)
                ], limit=1)
                if rec:
                    rec.sudo().write({'regime_id': emp.hds_in_current_tax_regime_id.id})
                else:
                    self.env['tds.employee.tax.regime'].sudo().create({
                        'employee_id': emp.id,
                        'financial_year_id': fy.id,
                        'regime_id': emp.hds_in_current_tax_regime_id.id,
                    })

                # Also sync tax declaration header if it exists
                decl = self.env['tds.employee.declaration'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('financial_year_id', '=', fy.id)
                ], limit=1)
                if decl:
                    decl.sudo().write({'tax_regime_id': emp.hds_in_current_tax_regime_id.id})


    # Section 3: Income Declaration Helper Fields (Mapped to tds.employee.income.declaration)
    hds_in_savings_bank_interest = fields.Monetary(
        string="Savings Account Interest (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False,
        help="Annual interest earned on savings bank accounts."
    )
    hds_in_fixed_deposit_interest = fields.Monetary(
        string="Fixed Deposit Interest (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False,
        help="Annual interest earned on term deposits."
    )
    hds_in_dividend_income = fields.Monetary(
        string="Dividend Income (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False,
        help="Annual taxable dividend income."
    )
    hds_in_other_sources_income = fields.Monetary(
        string="Other Miscellaneous Income (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False,
        help="Other taxable income."
    )
    hds_in_total_other_sources_income = fields.Monetary(
        string="Total Other Sources Income (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        store=False
    )
    hds_in_annual_let_out_rent = fields.Monetary(
        string="Gross Annual Rent (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False
    )
    hds_in_municipal_taxes_paid = fields.Monetary(
        string="Municipal Taxes Paid (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False
    )
    hds_in_let_out_interest_paid = fields.Monetary(
        string="Housing Loan Interest (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        inverse='_inverse_current_income_decl',
        store=False
    )
    hds_in_net_house_property_income_loss = fields.Monetary(
        string="Net Property Income / Loss (₹)",
        currency_field='currency_id',
        compute='_compute_current_income_decl',
        store=False
    )

    def _compute_current_income_decl(self):
        today = fields.Date.today()
        default_fy_fallback = self.env['tds.financial.year'].sudo().search([
            ('start_date', '<=', today),
            ('end_date', '>=', today),
            ('active', '=', True),
            ('is_closed', '=', False)
        ], limit=1)

        valid_emp_ids = [e.id for e in self if e.id]
        fy_map = {}
        decl_map = {}

        if valid_emp_ids:
            for emp in self:
                company = emp.company_id or self.env.company
                fy_map[emp.id] = company.hds_in_default_tax_year or default_fy_fallback

            all_fys = list(set(f.id for f in fy_map.values() if f))
            if all_fys:
                all_decls = self.env['tds.employee.income.declaration'].sudo().search([
                    ('employee_id', 'in', valid_emp_ids),
                    ('financial_year_id', 'in', all_fys)
                ])
                for d in all_decls:
                    decl_map[(d.employee_id.id, d.financial_year_id.id)] = d

        for emp in self:
            fy = fy_map.get(emp.id) if emp.id else False
            if fy and emp.id:
                decl = decl_map.get((emp.id, fy.id))
                if decl:
                    emp.hds_in_savings_bank_interest = decl.savings_bank_interest
                    emp.hds_in_fixed_deposit_interest = decl.fixed_deposit_interest
                    emp.hds_in_dividend_income = decl.dividend_income
                    emp.hds_in_other_sources_income = decl.other_sources_income
                    emp.hds_in_total_other_sources_income = decl.total_other_sources_income
                    emp.hds_in_annual_let_out_rent = decl.annual_let_out_rent
                    emp.hds_in_municipal_taxes_paid = decl.municipal_taxes_paid
                    emp.hds_in_let_out_interest_paid = decl.let_out_interest_paid
                    emp.hds_in_net_house_property_income_loss = decl.net_house_property_income_loss
                    emp.hds_in_prev_taxable_gross = decl.prev_employer_taxable_gross
                    emp.hds_in_prev_tds_deducted = decl.prev_employer_tds
                    emp.hds_in_prev_pt_deducted = decl.prev_employer_pt
                    emp.hds_in_prev_employer_pf = decl.prev_employer_pf
                else:
                    emp.hds_in_savings_bank_interest = 0.0
                    emp.hds_in_fixed_deposit_interest = 0.0
                    emp.hds_in_dividend_income = 0.0
                    emp.hds_in_other_sources_income = 0.0
                    emp.hds_in_total_other_sources_income = 0.0
                    emp.hds_in_annual_let_out_rent = 0.0
                    emp.hds_in_municipal_taxes_paid = 0.0
                    emp.hds_in_let_out_interest_paid = 0.0
                    emp.hds_in_net_house_property_income_loss = 0.0
                    emp.hds_in_prev_taxable_gross = 0.0
                    emp.hds_in_prev_tds_deducted = 0.0
                    emp.hds_in_prev_pt_deducted = 0.0
                    emp.hds_in_prev_employer_pf = 0.0
            else:
                emp.hds_in_savings_bank_interest = 0.0
                emp.hds_in_fixed_deposit_interest = 0.0
                emp.hds_in_dividend_income = 0.0
                emp.hds_in_other_sources_income = 0.0
                emp.hds_in_total_other_sources_income = 0.0
                emp.hds_in_annual_let_out_rent = 0.0
                emp.hds_in_municipal_taxes_paid = 0.0
                emp.hds_in_let_out_interest_paid = 0.0
                emp.hds_in_net_house_property_income_loss = 0.0
                emp.hds_in_prev_taxable_gross = 0.0
                emp.hds_in_prev_tds_deducted = 0.0
                emp.hds_in_prev_pt_deducted = 0.0
                emp.hds_in_prev_employer_pf = 0.0

    def _inverse_current_income_decl(self):
        today = fields.Date.today()
        fy = self.env['tds.financial.year'].sudo().search([
            ('start_date', '<=', today),
            ('end_date', '>=', today),
            ('active', '=', True),
            ('is_closed', '=', False)
        ], limit=1)

        if not fy:
            return

        income_fields_map = {
            'hds_in_savings_bank_interest': 'savings_bank_interest',
            'hds_in_fixed_deposit_interest': 'fixed_deposit_interest',
            'hds_in_dividend_income': 'dividend_income',
            'hds_in_other_sources_income': 'other_sources_income',
            'hds_in_annual_let_out_rent': 'annual_let_out_rent',
            'hds_in_municipal_taxes_paid': 'municipal_taxes_paid',
            'hds_in_let_out_interest_paid': 'let_out_interest_paid',
            'hds_in_prev_taxable_gross': 'prev_employer_taxable_gross',
            'hds_in_prev_tds_deducted': 'prev_employer_tds',
            'hds_in_prev_pt_deducted': 'prev_employer_pt',
            'hds_in_prev_employer_pf': 'prev_employer_pf',
        }

        for emp in self:
            if emp.id:
                decl = self.env['tds.employee.income.declaration'].sudo().search([
                    ('employee_id', '=', emp.id),
                    ('financial_year_id', '=', fy.id)
                ], limit=1)
                if not decl:
                    # Create empty income declaration shell if absent
                    decl = self.env['tds.employee.income.declaration'].sudo().create({
                        'employee_id': emp.id,
                        'financial_year_id': fy.id,
                    })

                vals = {}
                for emp_f, decl_f in income_fields_map.items():
                    val = getattr(emp, emp_f, None)
                    decl_val = float(getattr(decl, decl_f, 0.0) or 0.0)
                    if val is not False and val is not None:
                        float_val = float(val or 0.0)
                        if float_val > 0.0 and abs(float_val - decl_val) > 0.001:
                            vals[decl_f] = float_val
                if vals:
                    decl.sudo().write(vals)

    # -------------------------------------------------------------------------
    # SECTION 4: DEDUCTION DECLARATION HELPER FIELDS (Old Regime Only)
    # -------------------------------------------------------------------------
    # Group A: Investments (Chapter VI-A / Section 80C)
    hds_in_decl_80c_ppf = fields.Monetary(string="PPF Contribution (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_elss = fields.Monetary(string="ELSS Mutual Funds (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_epf = fields.Monetary(string="Voluntary EPF (VPF) (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_lic = fields.Monetary(string="Life Insurance Premium (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_nsc = fields.Monetary(string="National Savings Certificate (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_ssy = fields.Monetary(string="Sukanya Samriddhi Yojana (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_fd = fields.Monetary(string="Tax Saving FD (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_tuition = fields.Monetary(string="Children Tuition Fees (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_housing_principal = fields.Monetary(string="Housing Loan Principal (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_other = fields.Monetary(string="Other 80C Investments (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80c_total = fields.Monetary(string="Total Declared Section 80C (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', store=False)

    # Group B: National Pension Scheme (Section 80CCD(1B))
    hds_in_decl_80ccd1b_nps = fields.Monetary(string="Employee NPS Contribution 80CCD(1B) (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)

    # Group C: Medical Insurance (Section 80D)
    hds_in_decl_80d_self = fields.Monetary(string="Medical Insurance (Self/Family) (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80d_parents = fields.Monetary(string="Medical Insurance (Parents) (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80d_parents_is_senior = fields.Boolean(string="Parents are Senior Citizens (Age ≥ 60 years)", compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False, help="Check if parents are Senior Citizens (Age 60+), unlocking higher ₹50,000 Section 80D ceiling.")
    hds_in_decl_80d_preventive = fields.Monetary(string="Preventive Health Check-up (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)


    # Group D: House Rent Allowance (HRA)
    hds_in_decl_hra_annual_rent = fields.Monetary(string="Annual Rent Paid (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_hra_landlord_name = fields.Char(string="Landlord Name", compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_hra_landlord_pan = fields.Char(string="Landlord PAN", compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_hra_is_metro = fields.Boolean(string="Accommodation in Metro City", compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_hra_own_residential_property_at_workplace = fields.Boolean(string="Own Property at Workplace", compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_hra_rent_period_from = fields.Date(string="Rent Period From", compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_hra_rent_period_to = fields.Date(string="Rent Period To", compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)

    # Group E: Home Loan Interest (Section 24(b))
    hds_in_decl_24b_self_interest = fields.Monetary(string="Self-Occupied Home Loan Interest (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)

    # Group F: Savings Interest (Section 80TTA / 80TTB)
    hds_in_decl_80tta_interest = fields.Monetary(string="Savings Interest 80TTA (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80ttb_interest = fields.Monetary(string="Senior Citizen Interest 80TTB (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)

    # Group G: Disability Deductions (Section 80DD)
    hds_in_decl_80dd_amount = fields.Monetary(string="Dependent Disability 80DD (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)
    hds_in_decl_80dd_is_severe = fields.Boolean(string="Severe Disability (Disability ≥ 80%)", compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False, help="Check if dependent disability is 80% or higher, unlocking ₹1,25,000 Section 80DD ceiling.")


    # Group H: Other Eligible Deductions
    hds_in_decl_other_amount = fields.Monetary(string="Other Eligible Deductions (₹)", currency_field='currency_id', compute='_compute_current_deduction_decl', inverse='_inverse_current_deduction_decl', store=False)

    # -------------------------------------------------------------------------
    # CATEGORY C: NEW REGIME & BOTH REGIMES SUPPORTED DEDUCTIONS
    # -------------------------------------------------------------------------
    hds_in_decl_80ccd2_employer_nps = fields.Monetary(
        string="Employer NPS Contribution 80CCD(2) (₹)",
        currency_field='currency_id',
        compute='_compute_current_deduction_decl',
        inverse='_inverse_current_deduction_decl',
        store=False,
        help="Employer contribution under Section 80CCD(2) (up to 14%/10% of Basic + DA, permitted under BOTH Old and New Regimes)."
    )
    hds_in_decl_57iia_family_pension = fields.Monetary(
        string="Family Pension Deduction 57(iia) (₹)",
        currency_field='currency_id',
        compute='_compute_current_deduction_decl',
        inverse='_inverse_current_deduction_decl',
        store=False,
        help="Family Pension deduction under Section 57(iia) (permitted under BOTH Old and New Regimes)."
    )
    hds_in_decl_80cch_agniveer = fields.Monetary(
        string="Agniveer Corpus Fund 80CCH (₹)",
        currency_field='currency_id',
        compute='_compute_current_deduction_decl',
        inverse='_inverse_current_deduction_decl',
        store=False,
        help="Agniveer Corpus Fund deduction under Section 80CCH (permitted under BOTH Old and New Regimes)."
    )

    # Section 6: Supporting Proof Documents
    hds_in_tax_attachment_ids = fields.Many2many(
        'ir.attachment',
        'hr_employee_tax_ir_attachment_rel',
        'employee_id',
        'attachment_id',
        string="Tax Supporting Proof Documents",
        help="Upload LIC receipts, PPF statements, rent receipts, medical insurance receipts, and home loan certificates."
    )

    def _compute_current_deduction_decl(self):
        today = fields.Date.today()
        fy = self.env['tds.financial.year'].search([
            ('start_date', '<=', today),
            ('end_date', '>=', today),
            ('active', '=', True),
            ('is_closed', '=', False)
        ], limit=1)

        for emp in self:
            # Default zero values
            emp.hds_in_decl_80c_ppf = 0.0
            emp.hds_in_decl_80c_elss = 0.0
            emp.hds_in_decl_80c_epf = 0.0
            emp.hds_in_decl_80c_lic = 0.0
            emp.hds_in_decl_80c_nsc = 0.0
            emp.hds_in_decl_80c_ssy = 0.0
            emp.hds_in_decl_80c_fd = 0.0
            emp.hds_in_decl_80c_tuition = 0.0
            emp.hds_in_decl_80c_housing_principal = 0.0
            emp.hds_in_decl_80c_other = 0.0
            emp.hds_in_decl_80c_total = 0.0
            emp.hds_in_decl_80ccd1b_nps = 0.0
            emp.hds_in_decl_80d_self = 0.0
            emp.hds_in_decl_80d_parents = 0.0
            emp.hds_in_decl_80d_parents_is_senior = False
            emp.hds_in_decl_80d_preventive = 0.0

            emp.hds_in_decl_hra_annual_rent = 0.0
            emp.hds_in_decl_hra_landlord_name = False
            emp.hds_in_decl_hra_landlord_pan = False
            emp.hds_in_decl_hra_is_metro = False
            emp.hds_in_decl_24b_self_interest = 0.0
            emp.hds_in_decl_80tta_interest = 0.0
            emp.hds_in_decl_80ttb_interest = 0.0
            emp.hds_in_decl_80dd_amount = 0.0
            emp.hds_in_decl_80dd_is_severe = False
            emp.hds_in_decl_other_amount = 0.0

            emp.hds_in_decl_80ccd2_employer_nps = 0.0
            emp.hds_in_decl_57iia_family_pension = 0.0
            emp.hds_in_decl_80cch_agniveer = 0.0

            if fy and emp.id:
                decl = self.env['tds.employee.declaration'].search([
                    ('employee_id', '=', emp.id),
                    ('financial_year_id', '=', fy.id)
                ], limit=1)
                if decl:
                    for line in decl.declaration_line_ids:
                        cat = line.category
                        amt = line.declared_amount
                        desc = (line.description or '').lower()
                        if cat == '80c':
                            if desc in ['section 80c', 'section 80c (ppf, elss, lic, tuition fee, epf)', '80c investments', 'section 80c investment']:
                                continue
                            if 'ppf' in desc or 'public provident' in desc: emp.hds_in_decl_80c_ppf += amt
                            elif 'elss' in desc or 'mutual fund' in desc: emp.hds_in_decl_80c_elss += amt
                            elif 'vpf' in desc or 'voluntary epf' in desc or 'voluntary pf' in desc or ('epf' in desc and 'ppf' not in desc): emp.hds_in_decl_80c_epf += amt
                            elif 'lic' in desc or 'life insurance' in desc or 'life premium' in desc: emp.hds_in_decl_80c_lic += amt
                            elif 'nsc' in desc or 'national savings' in desc: emp.hds_in_decl_80c_nsc += amt
                            elif 'sukanya' in desc or 'ssy' in desc: emp.hds_in_decl_80c_ssy += amt
                            elif 'fixed deposit' in desc or 'tax saving fd' in desc or ' 5 year' in desc or ' 5-year' in desc or desc == 'fd' or desc.endswith(' fd'): emp.hds_in_decl_80c_fd += amt
                            elif 'tuition' in desc or 'school fee' in desc or 'children tuition' in desc: emp.hds_in_decl_80c_tuition += amt
                            elif 'housing' in desc or 'principal' in desc or 'home loan principal' in desc: emp.hds_in_decl_80c_housing_principal += amt
                            elif 'other 80c' in desc or 'other investment' in desc or 'other specified' in desc: emp.hds_in_decl_80c_other += amt
                            else: emp.hds_in_decl_80c_other += amt
                        elif cat == '80ccd1b': emp.hds_in_decl_80ccd1b_nps += amt
                        elif cat == '80d_self': emp.hds_in_decl_80d_self += amt
                        elif cat == '80d_parents':
                            emp.hds_in_decl_80d_parents += amt
                            if line.is_senior_citizen:
                                emp.hds_in_decl_80d_parents_is_senior = True

                        elif cat == '80d_preventive': emp.hds_in_decl_80d_preventive += amt
                        elif cat == 'hra':
                            emp.hds_in_decl_hra_annual_rent += amt
                            landlord_name = getattr(line.declaration_id, 'decl_hra_landlord_name', False) or getattr(line, 'landlord_name', False)
                            landlord_pan = getattr(line.declaration_id, 'decl_hra_landlord_pan', False) or getattr(line, 'landlord_pan', False)
                            is_metro = getattr(line.declaration_id, 'decl_hra_is_metro', False) or getattr(line, 'is_metro', False)
                            own_prop = getattr(line.declaration_id, 'decl_hra_own_residential_property_at_workplace', False) or getattr(line, 'own_residential_property_at_workplace', False)
                            r_from = getattr(line.declaration_id, 'decl_hra_rent_period_from', False) or getattr(line, 'rent_period_from', False)
                            r_to = getattr(line.declaration_id, 'decl_hra_rent_period_to', False) or getattr(line, 'rent_period_to', False)
                            if landlord_name: emp.hds_in_decl_hra_landlord_name = landlord_name
                            if landlord_pan: emp.hds_in_decl_hra_landlord_pan = landlord_pan
                            emp.hds_in_decl_hra_is_metro = is_metro
                            emp.hds_in_decl_hra_own_residential_property_at_workplace = own_prop
                            emp.hds_in_decl_hra_rent_period_from = r_from
                            emp.hds_in_decl_hra_rent_period_to = r_to
                        elif cat == '24b': emp.hds_in_decl_24b_self_interest += amt
                        elif cat == '80tta': emp.hds_in_decl_80tta_interest += amt
                        elif cat == '80ttb': emp.hds_in_decl_80ttb_interest += amt
                        elif cat == '80dd':
                            emp.hds_in_decl_80dd_amount += amt
                            if line.is_severe_disability:
                                emp.hds_in_decl_80dd_is_severe = True

                        elif cat == 'other': emp.hds_in_decl_other_amount += amt
                        elif cat == '80ccd2': emp.hds_in_decl_80ccd2_employer_nps += amt
                        elif cat == '57iia': emp.hds_in_decl_57iia_family_pension += amt
                        elif cat == '80cch': emp.hds_in_decl_80cch_agniveer += amt

                # Also check direct declaration fields if present
                if decl:
                    if not emp.hds_in_decl_hra_annual_rent and decl.decl_hra_annual_rent:
                        emp.hds_in_decl_hra_annual_rent = decl.decl_hra_annual_rent
                    if decl.decl_hra_landlord_name: emp.hds_in_decl_hra_landlord_name = decl.decl_hra_landlord_name
                    if decl.decl_hra_landlord_pan: emp.hds_in_decl_hra_landlord_pan = decl.decl_hra_landlord_pan
                    emp.hds_in_decl_hra_is_metro = bool(decl.decl_hra_is_metro)
                    emp.hds_in_decl_hra_own_residential_property_at_workplace = bool(decl.decl_hra_own_residential_property_at_workplace)
                    emp.hds_in_decl_hra_rent_period_from = decl.decl_hra_rent_period_from
                    emp.hds_in_decl_hra_rent_period_to = decl.decl_hra_rent_period_to

            emp.hds_in_decl_80c_total = (
                emp.hds_in_decl_80c_ppf + emp.hds_in_decl_80c_elss + emp.hds_in_decl_80c_epf +
                emp.hds_in_decl_80c_lic + emp.hds_in_decl_80c_nsc + emp.hds_in_decl_80c_ssy +
                emp.hds_in_decl_80c_fd + emp.hds_in_decl_80c_tuition +
                emp.hds_in_decl_80c_housing_principal + emp.hds_in_decl_80c_other
            )

    def _inverse_current_deduction_decl(self):
        today = fields.Date.today()
        fy = self.env['tds.financial.year'].search([
            ('start_date', '<=', today),
            ('end_date', '>=', today),
            ('active', '=', True),
            ('is_closed', '=', False)
        ], limit=1)

        if not fy:
            return


        for emp in self:
            if not emp.id:
                continue
            decl = self.env['tds.employee.declaration'].sudo().search([
                ('employee_id', '=', emp.id),
                ('financial_year_id', '=', fy.id)
            ], limit=1)
            if not decl:
                decl = self.env['tds.employee.declaration'].sudo().create({
                    'employee_id': emp.id,
                    'financial_year_id': fy.id,
                })

            lines_data = []

            # Category C items (Available under BOTH Regimes)
            if emp.hds_in_decl_80ccd2_employer_nps > 0:
                lines_data.append((0, 0, {'category': '80ccd2', 'description': 'Employer NPS Contribution 80CCD(2)', 'declared_amount': emp.hds_in_decl_80ccd2_employer_nps}))
            if emp.hds_in_decl_57iia_family_pension > 0:
                lines_data.append((0, 0, {'category': '57iia', 'description': 'Family Pension Deduction 57(iia)', 'declared_amount': emp.hds_in_decl_57iia_family_pension}))
            if emp.hds_in_decl_80cch_agniveer > 0:
                lines_data.append((0, 0, {'category': '80cch', 'description': 'Agniveer Corpus Fund 80CCH', 'declared_amount': emp.hds_in_decl_80cch_agniveer}))

            # If Old Tax Regime, append Category B Old Regime items
            if decl.regime_code != 'new' and not emp.hds_in_is_new_tax_regime:
                c_items = [
                    ('PPF Contribution', emp.hds_in_decl_80c_ppf),
                    ('ELSS Mutual Funds', emp.hds_in_decl_80c_elss),
                    ('Voluntary EPF (VPF)', emp.hds_in_decl_80c_epf),
                    ('LIC Premium', emp.hds_in_decl_80c_lic),
                    ('NSC Certificate', emp.hds_in_decl_80c_nsc),
                    ('Sukanya Samriddhi Yojana', emp.hds_in_decl_80c_ssy),
                    ('Tax Saving FD', emp.hds_in_decl_80c_fd),
                    ('Children Tuition Fees', emp.hds_in_decl_80c_tuition),
                    ('Housing Loan Principal Repayment', emp.hds_in_decl_80c_housing_principal),
                    ('Other 80C Investments', emp.hds_in_decl_80c_other),
                ]
                for desc, val in c_items:
                    if val > 0:
                        lines_data.append((0, 0, {'category': '80c', 'description': desc, 'declared_amount': val}))

                if emp.hds_in_decl_80ccd1b_nps > 0:
                    lines_data.append((0, 0, {'category': '80ccd1b', 'description': 'Employee Voluntary NPS 80CCD(1B)', 'declared_amount': emp.hds_in_decl_80ccd1b_nps}))
                if emp.hds_in_decl_80d_self > 0:
                    lines_data.append((0, 0, {'category': '80d_self', 'description': 'Medical Insurance Self/Family', 'declared_amount': emp.hds_in_decl_80d_self}))
                if emp.hds_in_decl_80d_parents > 0:
                    lines_data.append((0, 0, {
                        'category': '80d_parents',
                        'description': 'Medical Insurance Parents',
                        'declared_amount': emp.hds_in_decl_80d_parents,
                        'is_senior_citizen': emp.hds_in_decl_80d_parents_is_senior,
                    }))

                if emp.hds_in_decl_80d_preventive > 0:
                    lines_data.append((0, 0, {'category': '80d_preventive', 'description': 'Preventive Health Checkup', 'declared_amount': emp.hds_in_decl_80d_preventive}))

                if emp.hds_in_decl_hra_annual_rent > 0:
                    lines_data.append((0, 0, {
                        'category': 'hra',
                        'description': 'House Rent Allowance Claim',
                        'declared_amount': emp.hds_in_decl_hra_annual_rent,
                        'landlord_name': emp.hds_in_decl_hra_landlord_name,
                        'landlord_pan': emp.hds_in_decl_hra_landlord_pan,
                        'is_metro': emp.hds_in_decl_hra_is_metro,
                    }))

                if emp.hds_in_decl_24b_self_interest > 0:
                    lines_data.append((0, 0, {'category': '24b', 'description': 'Self-Occupied Housing Loan Interest 24(b)', 'declared_amount': emp.hds_in_decl_24b_self_interest}))
                if emp.hds_in_decl_80tta_interest > 0:
                    lines_data.append((0, 0, {'category': '80tta', 'description': 'Savings Interest Deduction 80TTA', 'declared_amount': emp.hds_in_decl_80tta_interest}))
                if emp.hds_in_decl_80ttb_interest > 0:
                    lines_data.append((0, 0, {'category': '80ttb', 'description': 'Senior Citizen Deposit Interest 80TTB', 'declared_amount': emp.hds_in_decl_80ttb_interest}))
                if emp.hds_in_decl_80dd_amount > 0:
                    lines_data.append((0, 0, {
                        'category': '80dd',
                        'description': 'Dependent Disability 80DD',
                        'declared_amount': emp.hds_in_decl_80dd_amount,
                        'is_severe_disability': emp.hds_in_decl_80dd_is_severe,
                    }))

                if emp.hds_in_decl_other_amount > 0:
                    lines_data.append((0, 0, {'category': 'other', 'description': 'Other Statutory Deduction', 'declared_amount': emp.hds_in_decl_other_amount}))

            # Reset old lines and update declaration
            decl.declaration_line_ids.unlink()
            if lines_data:
                decl.write({'declaration_line_ids': lines_data})
            decl.action_validate_declaration_rules()



    def _compute_hds_in_tax_regime_count(self):
        for emp in self:
            emp.hds_in_tax_regime_count = self.env['tds.employee.tax.regime'].search_count([
                ('employee_id', '=', emp.id)
            ])

    def action_view_tax_regimes(self):

        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Financial Year Tax Selections'),
            'res_model': 'tds.employee.tax.regime',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_view_home_loans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Housing Loan & Section 80EEA Eligibility'),
            'res_model': 'tds.employee.home.loan',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
