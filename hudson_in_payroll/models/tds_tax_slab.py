# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TdsTaxSlab(models.Model):
    """
    TDS Income Tax Slab Master Model.
    Stores structured, range-based Income Tax Slabs per Financial Year and Tax Regime.
    Supports effective-dating and non-overlapping income range validation.
    """
    _name = 'tds.tax.slab'
    _description = 'TDS Income Tax Slab'
    _order = 'financial_year_id desc, regime_code, sequence, income_from'

    name = fields.Char(
        string="Slab Title",
        compute='_compute_name',
        store=True,
        help="Automated slab display title."
    )
    financial_year_id = fields.Many2one(
        'tds.financial.year',
        string="Financial Year",
        required=True,
        ondelete='cascade',
        help="Financial year for which this income slab is applicable."
    )
    regime_id = fields.Many2one(
        'tds.tax.regime',
        string="Tax Regime Master",
        help="Optional reference to tds.tax.regime model."
    )
    regime_code = fields.Selection(
        selection=[
            ('new', 'New Regime'),
            ('old', 'Old Regime'),
        ],
        string="Tax Regime",
        required=True,
        default='new',
        help="Tax Regime ('new' for Section 115BAC, 'old' for Old Regime)."
    )
    income_from = fields.Float(
        string="Income From (₹)",
        required=True,
        default=0.0,
        help="Lower threshold limit of taxable annual income in Rupees (inclusive)."
    )
    income_to = fields.Float(
        string="Income To (₹)",
        default=0.0,
        help="Upper limit of taxable annual income in Rupees. Set to 0.0 or leave blank for open-ended top slab."
    )
    rate = fields.Float(
        string="Tax Rate (%)",
        required=True,
        default=0.0,
        help="Income tax rate percentage applied to income falling within this slab range."
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of slab evaluation."
    )
    date_from = fields.Date(
        string="Effective From",
        help="Optional start date of validity for this slab."
    )
    date_to = fields.Date(
        string="Effective To",
        help="Optional end date of validity for this slab."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Set to false to archive obsolete slabs."
    )

    @api.depends('financial_year_id.name', 'regime_code', 'income_from', 'income_to', 'rate')
    def _compute_name(self):
        for rec in self:
            fy_str = rec.financial_year_id.name if rec.financial_year_id else 'FY'
            reg_str = 'New Regime' if rec.regime_code == 'new' else 'Old Regime'
            to_str = f"₹{rec.income_to:,.0f}" if rec.income_to > 0 else "Above"
            rec.name = f"{fy_str} ({reg_str}): ₹{rec.income_from:,.0f} - {to_str} @ {rec.rate}%"

    @api.constrains('income_from', 'income_to')
    def _check_income_bounds(self):
        for rec in self:
            if rec.income_to > 0 and rec.income_from >= rec.income_to:
                raise ValidationError(_(
                    "Income From (₹%s) must be strictly less than Income To (₹%s) for slab '%s'."
                ) % (rec.income_from, rec.income_to, rec.name))

    @api.constrains('financial_year_id', 'regime_code', 'income_from', 'income_to', 'active')
    def _check_overlapping_slabs(self):
        """
        Validates that income tax slabs for the same Financial Year and Tax Regime do not have overlapping ranges.
        """
        for rec in self:
            if not rec.active or not rec.financial_year_id:
                continue

            domain = [
                ('id', '!=', rec.id),
                ('active', '=', True),
                ('financial_year_id', '=', rec.financial_year_id.id),
                ('regime_code', '=', rec.regime_code),
            ]
            other_slabs = self.search(domain)
            for other in other_slabs:
                rec_max = rec.income_to if rec.income_to > 0 else float('inf')
                other_max = other.income_to if other.income_to > 0 else float('inf')

                # Check range overlap: max(A_start, B_start) < min(A_end, B_end)
                overlap_start = max(rec.income_from, other.income_from)
                overlap_end = min(rec_max, other_max)

                if overlap_start < overlap_end:
                    raise ValidationError(_(
                        "Overlapping Income Tax Slab detected for %s (%s)! "
                        "Slab ₹%s - ₹%s overlaps with existing slab ₹%s - ₹%s."
                    ) % (
                        rec.financial_year_id.name,
                        'New Regime' if rec.regime_code == 'new' else 'Old Regime',
                        f"{rec.income_from:,.0f}", f"{rec.income_to:,.0f}" if rec.income_to > 0 else "Above",
                        f"{other.income_from:,.0f}", f"{other.income_to:,.0f}" if other.income_to > 0 else "Above",
                    ))
