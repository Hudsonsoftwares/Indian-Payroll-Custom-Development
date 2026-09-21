import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TdsEmployeeDeclarationLine(models.Model):
    """
    TDS Employee Tax Declaration Line Item Model.
    Captures individual investment proofs, Section 10 exemptions, and Chapter VI-A deduction line items.
    Enforces regime compatibility and statutory ceiling calculations.
    """
    _name = 'tds.employee.declaration.line'
    _description = 'Employee Tax Declaration Line Item'
    _order = 'declaration_id, category, id'

    declaration_id = fields.Many2one(
        'tds.employee.declaration',
        string="Declaration Header",
        required=True,
        ondelete='cascade',
        help="Parent declaration header."
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        related='declaration_id.employee_id',
        store=True,
        readonly=True
    )
    financial_year_id = fields.Many2one(
        'tds.financial.year',
        string="Tax Year",
        related='declaration_id.financial_year_id',
        store=True,
        readonly=True
    )
    regime_code = fields.Selection(
        related='declaration_id.regime_code',
        string="Regime Code",
        store=True,
        readonly=True
    )
    declaration_state = fields.Selection(
        related='declaration_id.state',
        string="Declaration State",
        store=True,
        readonly=True
    )
    category = fields.Selection([
        ('80c', 'Section 80C (PPF, ELSS, LIC, Tuition Fee, EPF)'),
        ('80ccd1b', 'Section 80CCD(1B) Additional NPS Contribution'),
        ('80d_self', 'Section 80D Medical Insurance (Self & Family)'),
        ('80d_parents', 'Section 80D Medical Insurance (Parents)'),
        ('80d_preventive', 'Section 80D Preventive Health Checkup'),
        ('80tta', 'Section 80TTA Savings Interest (Non-Senior)'),
        ('80ttb', 'Section 80TTB Savings & FD Interest (Senior Citizen)'),
        ('80dd', 'Section 80DD Dependent Disability'),
        ('80u', 'Section 80U Employee Disability'),
        ('24b', 'Section 24(b) Home Loan Interest (Self-Occupied)'),
        ('80eea', 'Section 80EEA First-time Home Loan Additional Interest'),
        ('80e', 'Section 80E Education Loan Interest'),
        ('80g', 'Section 80G Charitable Donations'),
        ('80gg', 'Section 80GG Rent Paid without HRA'),
        ('hra', 'Section 10(13A) House Rent Exemption (Rent Paid)'),
        ('children_edu', 'Section 10(14) Children Education Allowance'),
        ('hostel', 'Section 10(14) Hostel Expenditure Allowance'),
        ('lta', 'Section 10(5) Leave Travel Assistance (LTA)'),
        ('nps_employee', 'Section 80CCD(1) Employee NPS Contribution'),
        ('80ccd2', 'Employer NPS Contribution — Section 124 (Both Regimes)'),
        ('57iia', 'Section 57(iia) Family Pension Deduction (Both Regimes)'),
        ('80cch', 'Section 80CCH Agniveer Corpus Fund Contribution (Both Regimes)'),
        ('leave_encashment', 'Section 10(10AA) Leave Encashment Exemption'),
        ('vrs', 'Section 10(10C) VRS Compensation Exemption'),
        ('other', 'Other Statutory Exemptions'),
    ], string="Declaration Category", required=True)


    section_code = fields.Char(
        string="Statutory Section Code",
        compute='_compute_section_code',
        store=False,
        help="Automated section code designation."
    )
    description = fields.Char(
        string="Investment Particulars / Description",
        required=True,
        help="Detailed description of investment or claim (e.g. LIC Policy #98765, Rent Paid to Landlord)."
    )
    declared_amount = fields.Monetary(
        string="Declared Amount (₹)",
        currency_field='currency_id',
        required=True,
        default=0.0,
        help="Amount declared by employee."
    )
    is_senior_citizen = fields.Boolean(
        string="Insured Person is Senior Citizen (Age ≥ 60)",
        default=False,
        help="Mark True if the insured person (Self/Spouse or Parents) is a Senior Citizen (Age 60+), unlocking higher Section 80D statutory limits."
    )
    is_severe_disability = fields.Boolean(
        string="Severe Disability (Disability ≥ 80%)",
        default=False,
        help="Mark True if dependent disability is 80% or higher, unlocking higher Section 80DD statutory ceiling of ₹1,25,000."
    )
    decl_80g_category = fields.Selection([
        ('100_no_limit', '100% Deduction (Without Qualifying Limit)'),
        ('50_no_limit', '50% Deduction (Without Qualifying Limit)'),
        ('100_with_limit', '100% Deduction (Subject to Qualifying Limit)'),
        ('50_with_limit', '50% Deduction (Subject to Qualifying Limit)'),
    ], string="80G Deduction Category", help="Statutory category under Section 80G governing deduction percentage and qualifying limits.")

    # Section 10(13A) HRA Eligibility Validation Fields
    own_residential_property_at_workplace = fields.Boolean(
        string="Own Residential Property at Place of Work/Residence",
        default=False,
        help="Section 10(13A) - Mark True if employee owns residential accommodation at the place of work/residence."
    )
    rent_period_from = fields.Date(
        string="Rent Period From",
        help="Section 10(13A) - Start date of the claimed rent period."
    )
    rent_period_to = fields.Date(
        string="Rent Period To",
        help="Section 10(13A) - End date of the claimed rent period."
    )

    verified_amount = fields.Monetary(
        string="Verified Amount (₹)",
        currency_field='currency_id',
        default=0.0,
        help="Amount verified by HR after proof document inspection."
    )

    approved_amount = fields.Monetary(
        string="Approved Statutory Deduction (₹)",
        currency_field='currency_id',
        default=0.0,
        help="Final statutory deduction allowed after ceiling cap and regime validation."
    )
    tax_firm_approved_amount = fields.Monetary(
        string="Tax Firm Approved Amount (₹)",
        currency_field='currency_id',
        default=0.0,
        help="Final deduction amount approved by external Tax Firm, entered manually by HR after proof verification."
    )
    rejected_amount = fields.Monetary(
        string="Rejected Amount (₹)",
        currency_field='currency_id',
        compute='_compute_rejected_amount',
        store=True,
        readonly=False,
        help="Amount rejected by HR during proof document verification."
    )

    @api.depends('declared_amount', 'approved_amount', 'tax_firm_approved_amount', 'declaration_id.state')
    def _compute_rejected_amount(self):
        for line in self:
            if line.declaration_id and line.declaration_id.state in ('proof_under_review', 'proof_verified', 'approved'):
                eff_approved = line.tax_firm_approved_amount or line.approved_amount or 0.0
                line.rejected_amount = max(0.0, (line.declared_amount or 0.0) - eff_approved)
            else:
                line.rejected_amount = 0.0

    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='declaration_id.currency_id',
        readonly=True
    )
    is_regime_permitted = fields.Boolean(
        string="Regime Permitted",
        default=True,
        help="True if deduction category is permitted under the employee's selected tax regime."
    )
    validation_status = fields.Selection([
        ('valid', 'Statutory Valid'),
        ('exceeds_limit', 'Exceeds Statutory Limit (Capped)'),
        ('ineligible_regime', 'Not Permitted Under New Regime'),
        ('pending_proof', 'Pending Document Proof'),
    ], string="Validation Status", default='valid', required=True)

    validation_remarks = fields.Text(
        string="Validation Remarks",
        help="Audit trail explaining statutory capping or regime rejection reasons."
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'tds_declaration_line_ir_attachment_rel',
        'line_id',
        'attachment_id',
        string="Supporting Document Proofs",
        help="Proof receipts attached specifically for this investment line item."
    )

    @api.depends('category')
    def _compute_section_code(self):
        code_map = {
            '80c': 'Sec 80C',
            '80ccd1b': 'Sec 80CCD(1B)',
            '80d_self': 'Sec 80D (Self)',
            '80d_parents': 'Sec 80D (Parents)',
            '80d_preventive': 'Sec 80D (Preventive)',
            '80tta': 'Sec 80TTA',
            '80ttb': 'Sec 80TTB',
            '80dd': 'Sec 80DD',
            '80e': 'Sec 80E',
            '80g': 'Sec 80G',
            '80u': 'Sec 80U',
            '24b': 'Sec 24(b)',
            '80eea': 'Sec 80EEA',
            'hra': 'Sec 10(13A)',
            'children_edu': 'Sec 10(14)',
            'hostel': 'Sec 10(14)',
            'lta': 'Sec 10(5)',
            'nps_employee': 'Sec 80CCD(1)',
            '80ccd2': 'Sec 80CCD(2)',
            '57iia': 'Sec 57(iia)',
            '80cch': 'Sec 80CCH',
            'leave_encashment': 'Sec 10(10AA)',
            'vrs': 'Sec 10(10C)',
            'other': 'Other',
        }
        for line in self:
            line.section_code = code_map.get(line.category, 'General')

    eligible_amount = fields.Monetary(
        string="Eligible Deduction (₹)",
        currency_field='currency_id',
        compute='_compute_deduction_eligibility',
        store=False,
        help="System-calculated allowable statutory deduction computed dynamically on-the-fly."
    )
    excess_amount = fields.Monetary(
        string="Excess / Non-Eligible Amount (₹)",
        currency_field='currency_id',
        compute='_compute_deduction_eligibility',
        store=False,
        help="Informational non-eligible investment portion exceeding statutory deduction limits."
    )

    @api.constrains('category', 'declared_amount', 'approved_amount', 'tax_firm_approved_amount', 'verified_amount', 'decl_80g_category')
    def _check_80g_category(self):
        for line in self:
            if line.category == '80g':
                decl_state = line.declaration_state or (line.declaration_id.state if line.declaration_id else 'draft')
                is_post_proof = decl_state in ('proof_under_review', 'proof_verified', 'approved')
                if is_post_proof:
                    eff_amount = float(line.tax_firm_approved_amount or line.approved_amount or line.verified_amount or line.declared_amount or 0.0)
                else:
                    eff_amount = float(line.declared_amount or 0.0)

                if eff_amount > 0.0 and not line.decl_80g_category:
                    raise ValidationError(_(
                        "Section 80G Deduction Category is mandatory for declaration line '%s' when a donation amount (₹%s) is declared or approved. "
                        "Please select a valid 80G category (100%% No Limit, 50%% No Limit, 100%% With Limit, or 50%% With Limit)."
                    ) % (line.description or 'Section 80G Donation', f"{eff_amount:,.2f}"))

    @api.depends('declared_amount', 'approved_amount', 'tax_firm_approved_amount', 'is_regime_permitted', 'category', 'declaration_id.state', 'regime_code', 'declaration_id.employee_id', 'declaration_id.financial_year_id')
    def _compute_deduction_eligibility(self):
        from ..services.tds.eligibility_rule_engine_service import EligibilityRuleEngineService
        engine = EligibilityRuleEngineService(self.env)
        for line in self:
            eval_d = line.declaration_id.financial_year_id.start_date if (line.declaration_id and line.declaration_id.financial_year_id and line.declaration_id.financial_year_id.start_date) else None
            res = engine.evaluate_eligibility(line, eval_date=eval_d)
            line.eligible_amount = res.eligible_deduction
            line.excess_amount = res.excess_amount

    @property
    def usable_amount(self):
        """
        Statutory usable amount for TDS calculation engines and reconciliation:
        - Planning Phase (state not in ('proof_verified', 'approved')): eligible_amount
        - Adjustment Phase (state in ('proof_verified', 'approved')):
          Reflects the post-proof approved/verified amount capped by statutory eligibility.
          If HR / Tax Firm rejected (Approved = 0), usable_amount is strictly 0.0.
        """
        self._compute_deduction_eligibility()

        res_amt = 0.0
        if self.declaration_id and self.declaration_id.state in ('proof_verified', 'approved'):
            tf_amt = float(self.tax_firm_approved_amount or 0.0)
            appr_amt = float(self.approved_amount or 0.0)
            ver_amt = float(self.verified_amount or 0.0)
            elig_amt = float(self.eligible_amount or 0.0)

            if tf_amt > 0.0:
                target_amt = tf_amt
            elif appr_amt > 0.0:
                target_amt = appr_amt
            elif ver_amt > 0.0:
                target_amt = ver_amt
            else:
                target_amt = 0.0

            res_amt = min(target_amt, elig_amt) if elig_amt > 0.0 else target_amt
        else:
            res_amt = self.eligible_amount if self.eligible_amount is not None else (self.declared_amount or 0.0)

        return res_amt

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'tax_firm_approved_amount' in vals and vals.get('tax_firm_approved_amount') is not False:
                tf_val = float(vals.get('tax_firm_approved_amount') or 0.0)
                if tf_val > 0.0 or 'approved_amount' not in vals:
                    vals['approved_amount'] = tf_val
        lines = super(TdsEmployeeDeclarationLine, self).create(vals_list)
        for line in lines:
            if line.tax_firm_approved_amount:
                _logger.warning("""[TDS_DEBUG_TRACE][OPTION_A_SYNC]
line_id=%s
category=%s
tax_firm_approved_amount=%s
approved_amount_before=0.0
approved_amount_after=%s
declaration_id=%s
declaration_total_approved_amount=%s""",
                    line.id, line.category, line.tax_firm_approved_amount,
                    line.approved_amount,
                    line.declaration_id.id if line.declaration_id else 'N/A',
                    line.declaration_id.total_approved_amount if line.declaration_id else 'N/A'
                )
        return lines

    def write(self, vals):
        sync_tf = 'tax_firm_approved_amount' in vals
        if sync_tf and 'approved_amount' not in vals:
            vals['approved_amount'] = float(vals.get('tax_firm_approved_amount') or 0.0)

        before_dict = {l.id: float(l.approved_amount or 0.0) for l in self}
        res = super(TdsEmployeeDeclarationLine, self).write(vals)

        for line in self:
            if sync_tf or (line.tax_firm_approved_amount > 0.0 and line.approved_amount != line.tax_firm_approved_amount):
                old_appr = before_dict.get(line.id, 0.0)
                if line.approved_amount != line.tax_firm_approved_amount:
                    super(TdsEmployeeDeclarationLine, line).write({'approved_amount': line.tax_firm_approved_amount})
                _logger.warning("""[TDS_DEBUG_TRACE][OPTION_A_SYNC]
line_id=%s
category=%s
tax_firm_approved_amount=%s
approved_amount_before=%s
approved_amount_after=%s
declaration_id=%s
declaration_total_approved_amount=%s""",
                    line.id, line.category, line.tax_firm_approved_amount,
                    old_appr, line.approved_amount,
                    line.declaration_id.id if line.declaration_id else 'N/A',
                    line.declaration_id.total_approved_amount if line.declaration_id else 'N/A'
                )
        return res
