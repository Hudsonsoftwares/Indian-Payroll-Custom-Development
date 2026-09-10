# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FinalSettlement(models.Model):
    _name = 'final.settlement'
    _description = 'Employee Final Settlement'
    _order = 'name desc, id desc'

    name = fields.Char(
        string="Settlement Number",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New')
    )
    
    # Employee Information
    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        index=True,
        help="Select the exiting employee for final settlement."
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Company responsible for this final settlement."
    )
    department_id = fields.Many2one(
        'hr.department',
        string="Department",
        related='employee_id.department_id',
        store=True,
        readonly=True
    )
    job_id = fields.Many2one(
        'hr.job',
        string="Job Position",
        related='employee_id.job_id',
        store=True,
        readonly=True
    )

    # Exit Information
    resignation_id = fields.Many2one(
        'hr.resignation',
        string="Linked Resignation Request",
        domain="[('employee_id', '=', employee_id)]",
        help="Optional linked resignation record from the resignation workflow."
    )
    last_working_day = fields.Date(
        string="Last Working Day",
        required=True,
        default=fields.Date.today,
        help="Employee's final working day in the organization."
    )
    settlement_date = fields.Date(
        string="Settlement Date",
        required=True,
        default=fields.Date.today,
        help="Target processing date for final settlement calculation and payment."
    )
    exit_reason = fields.Selection([
        ('resignation', 'Resignation'),
        ('retirement', 'Retirement'),
        ('termination', 'Termination'),
        ('death', 'Death in Service'),
        ('contract_end', 'Contract Completion'),
        ('other', 'Other'),
    ], string="Exit Reason", default='resignation', required=True)

    # Payroll Information
    payslip_id = fields.Many2one(
        'hr.payslip',
        string="Final Settlement Payslip",
        readonly=True,
        copy=False,
        help="Linked final settlement payslip sheet."
    )

    # Currency & Settlement Breakdown Lines
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='company_id.currency_id',
        store=True,
        readonly=True
    )
    line_ids = fields.One2many(
        'final.settlement.line',
        'settlement_id',
        string="Settlement Breakdown Lines",
        copy=True
    )

    # Settlement Financial Totals
    total_earnings = fields.Monetary(
        string="Total Earnings",
        currency_field='currency_id',
        compute='_compute_settlement_totals',
        store=True
    )
    total_deductions = fields.Monetary(
        string="Total Deductions",
        currency_field='currency_id',
        compute='_compute_settlement_totals',
        store=True
    )
    net_settlement_amount = fields.Monetary(
        string="Net Settlement Amount",
        currency_field='currency_id',
        compute='_compute_settlement_totals',
        store=True
    )

    @api.depends('line_ids', 'line_ids.amount', 'line_ids.line_type', 'line_ids.settlement_id')
    def _compute_settlement_totals(self):
        for record in self:
            earnings = sum(record.line_ids.filtered(lambda l: l.line_type == 'earning').mapped('amount'))
            deductions = sum(record.line_ids.filtered(lambda l: l.line_type == 'deduction').mapped('amount'))
            record.total_earnings = earnings
            record.total_deductions = deductions
            record.net_settlement_amount = earnings - deductions

    # Workflow Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft', required=True, copy=False, index=True)

    # Notes & Remarks
    notes = fields.Text(string="Notes & Remarks")

    def action_compute_settlement(self):
        """Compute or recompute settlement breakdown lines via FinalSettlementCalculationService."""
        res_info = None
        for record in self:
            if record.state in ('approved', 'paid'):
                raise ValidationError(_("Cannot recompute a settlement in Approved or Paid state."))
            from ..services.final_settlement_calculation_service import FinalSettlementCalculationService
            service = FinalSettlementCalculationService(self.env)
            res_info = service.compute_settlement(record)

        if len(self) == 1 and res_info:
            msg = _(
                "Final settlement breakdown computed successfully. Processed %s component lines (Net Amount: %s)."
            ) % (res_info.get('processed_lines', 0), res_info.get('net_amount', 0.0))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Settlement Computed"),
                    'message': msg,
                    'sticky': False,
                    'type': 'success',
                }
            }
        return True

    @api.constrains('resignation_id', 'state')
    def _check_unique_resignation_settlement(self):
        for record in self:
            if record.resignation_id and record.state != 'cancel':
                domain = [
                    ('resignation_id', '=', record.resignation_id.id),
                    ('state', '!=', 'cancel'),
                    ('id', '!=', record.id)
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(_(
                        "An active Final Settlement record already exists for Resignation Request '%s'. "
                        "Duplicate settlements are not allowed."
                    ) % record.resignation_id.name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('final.settlement') or _('New')
        return super(FinalSettlement, self).create(vals_list)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            if getattr(self.employee_id, 'departure_date', None):
                self.last_working_day = self.employee_id.departure_date
            res = self.env['hr.resignation'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', '!=', 'cancel')
            ], order='id desc', limit=1)
            if res:
                self.resignation_id = res.id
                if getattr(res, 'approved_revealing_date', None):
                    self.last_working_day = res.approved_revealing_date
                elif getattr(res, 'expected_revealing_date', None):
                    self.last_working_day = res.expected_revealing_date

    @api.onchange('resignation_id')
    def _onchange_resignation_id(self):
        if self.resignation_id:
            if self.resignation_id.employee_id:
                self.employee_id = self.resignation_id.employee_id.id
            if getattr(self.resignation_id, 'approved_revealing_date', None):
                self.last_working_day = self.resignation_id.approved_revealing_date
            elif getattr(self.resignation_id, 'expected_revealing_date', None):
                self.last_working_day = self.resignation_id.expected_revealing_date
