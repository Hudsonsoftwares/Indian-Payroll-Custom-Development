# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TdsFinancialYear(models.Model):
    """
    TDS Financial Year Master Model.
    Manages Indian Income Tax Financial Years (e.g. FY 2025-26) and Assessment Years (e.g. AY 2026-27).
    Serves as the root master linking income tax slabs, surcharge slabs, and default company tax years.
    """
    _name = 'tds.financial.year'
    _inherit = ['mail.thread']
    _description = 'TDS Financial Year'
    _order = 'code desc, id desc'

    name = fields.Char(
        string="Financial Year Name",
        required=True,
        help="e.g. FY 2025-26 (AY 2026-27)"
    )
    code = fields.Char(
        string="Financial Year Code",
        required=True,
        help="e.g. 2025-2026"
    )
    assessment_year = fields.Char(
        string="Assessment Year",
        required=True,
        help="e.g. 2026-2027"
    )
    start_date = fields.Date(
        string="Start Date",
        required=True,
        help="Start date of the financial year (e.g. 01/04/2025)"
    )
    end_date = fields.Date(
        string="End Date",
        required=True,
        help="End date of the financial year (e.g. 31/03/2026)"
    )
    is_closed = fields.Boolean(
        string="Closed",
        default=False,
        help="Mark as true once the financial year is officially closed for tax declarations and payroll processing."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Set to false to archive old financial years."
    )
    tax_slab_ids = fields.One2many(
        'tds.tax.slab',
        'financial_year_id',
        string="Income Tax Slabs"
    )
    surcharge_ids = fields.One2many(
        'tds.surcharge',
        'financial_year_id',
        string="Surcharge Slabs"
    )
    is_proof_submission_open = fields.Boolean(
        string="Proof Submission Window Open",
        default=False,
        help="Enable to allow employees to upload investment proof documents for this Financial Year."
    )
    proof_submission_start_date = fields.Date(
        string="Proof Window Start Date",
        help="Date when HR opens December investment proof window."
    )
    proof_submission_end_date = fields.Date(
        string="Proof Window End Date",
        help="Date when December investment proof window closes."
    )
    declaration_cutoff_date = fields.Date(
        string="Declaration Cutoff Date",
        help="Company defined cutoff date for employee investment plan updates."
    )
    tds_recalculation_from_month = fields.Selection([
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
    ], string="Recalculation From Month", compute='_compute_tds_recalculation_from_month', store=True, readonly=False,
       help="Month from which post-proof-verification TDS recalculation starts (dynamically derived from Distribution Months).")

    tds_month_division = fields.Integer(
        string="TDS Month Division",
        default=12,
        required=True,
        help="Number of months to divide annual estimated TDS tax liability across regular monthly pay periods (Default: 12)."
    )

    tds_recalculation_distribution_months = fields.Integer(
        string="Distribution Months",
        default=3,
        required=True,
        help="Number of future payroll months over which recalculated remaining annual TDS liability is distributed (e.g., 3 for Jan, Feb, Mar)."
    )

    @api.depends('tds_recalculation_distribution_months')
    def _compute_tds_recalculation_from_month(self):
        for rec in self:
            dist_m = max(1, min(12, int(rec.tds_recalculation_distribution_months or 3)))
            start_fy_idx = 12 - dist_m + 1
            cal_m = start_fy_idx + 3 if start_fy_idx <= 9 else start_fy_idx - 9
            rec.tds_recalculation_from_month = str(cal_m)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The Financial Year Code must be unique!')
    ]

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date >= rec.end_date:
                raise ValidationError(_("Financial Year Start Date (%s) must be earlier than End Date (%s).") % (
                    rec.start_date, rec.end_date
                ))

    def write(self, vals):
        for rec in self:
            if rec.is_closed and 'is_closed' not in vals:
                raise ValidationError(_("Financial Year '%s' is closed and locked. Reopen the Financial Year to make statutory modifications.") % rec.name)
        return super(TdsFinancialYear, self).write(vals)

    def action_close_financial_year(self):
        for rec in self:
            rec.write({'is_closed': True})
            rec.message_post(body=_("Financial Year %s closed and locked against structural edits.") % rec.name)

    def action_unclose_financial_year(self):
        for rec in self:
            rec.write({'is_closed': False})
            rec.message_post(body=_("Financial Year %s reopened for administrative modifications.") % rec.name)

    def is_declaration_revision_allowed(self, eval_date=None):
        """Returns True if investment declaration updates are allowed for this financial year."""
        self.ensure_one()
        if self.is_closed:
            return False
        eval_date = eval_date or fields.Date.today()
        if self.declaration_cutoff_date:
            return eval_date <= self.declaration_cutoff_date
        return True

    def is_proof_submission_active(self, eval_date=None):
        """Returns True if the proof submission window is active for this financial year."""
        self.ensure_one()
        if self.is_closed:
            return False
        if self.is_proof_submission_open:
            return True
        eval_date = eval_date or fields.Date.today()
        if self.proof_submission_start_date and self.proof_submission_end_date:
            return self.proof_submission_start_date <= eval_date <= self.proof_submission_end_date
        return eval_date.month in (12, 1)  # Default December - January proof submission window


