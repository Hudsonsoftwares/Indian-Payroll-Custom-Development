# -*- coding: utf-8 -*-
import calendar
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DummyInput:
    """Safe fallback for missing inputs or worked day lines in rule formulas."""
    def __init__(self):
        self.amount = 0.0
        self.number_of_days = 0.0
        self.number_of_hours = 0.0
        self.total = 0.0

    def __bool__(self):
        return False

    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        return 0.0


class BrowsableObject:
    """Helper object for safe dot-notation access in salary rule formulas."""
    def __init__(self, dict_data):
        self._dict_data = dict_data

    def get(self, key, default=None):
        return self._dict_data.get(key, default)

    def keys(self):
        return self._dict_data.keys()

    def values(self):
        return self._dict_data.values()

    def items(self):
        return self._dict_data.items()

    def __getattr__(self, name):
        if name in self._dict_data:
            return self._dict_data[name]
        return DummyInput()

    def __getitem__(self, key):
        return self._dict_data.get(key, DummyInput())

    def __contains__(self, key):
        return key in self._dict_data


class CategoryAccumulator:
    """Accumulator for salary rule categories with automatic parent category rollups."""
    def __init__(self):
        self._totals = {}

    def add(self, category, amount):
        curr = category
        while curr:
            code = curr.code
            self._totals[code] = self._totals.get(code, 0.0) + amount
            curr = curr.parent_id

    def __getattr__(self, code):
        return self._totals.get(code, 0.0)

    def __getitem__(self, code):
        return self._totals.get(code, 0.0)

    def get(self, code, default=0.0):
        return self._totals.get(code, default)


class RuleResult:
    """Represents a computed rule result accessible via rules.<CODE>.total in formulas."""
    def __init__(self, amount=0.0, rate=100.0, quantity=1.0):
        self.amount = amount
        self.rate = rate
        self.quantity = quantity
        self.total = quantity * amount * rate / 100.0


class HrPayslip(models.Model):
    """Core Payslip Model for computing and managing individual employee salary sheets."""
    _name = 'hr.payslip'
    _inherit = ['mail.thread']
    _description = 'Pay Slip'
    _order = 'date_to desc, id desc'

    name = fields.Char(string='Payslip Name', required=True)
    number = fields.Char(string='Reference', copy=False, readonly=True, index=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True,
        index=True
    )
    contract_id = fields.Many2one(
        'hr.version',
        string='Contract',
        required=True,
        tracking=True,
        index=True
    )
    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Structure',
        required=True
    )
    date_from = fields.Date(
        string='Date From',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1)
    )
    date_to = fields.Date(
        string='Date To',
        required=True,
        default=lambda self: (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('paid', 'Paid'),
        ('cancel', 'Rejected'),
    ], string='Status', default='draft', readonly=True, copy=False, tracking=True, index=True)

    employee_avatar = fields.Binary(
        related='employee_id.image_128',
        string='Avatar',
        readonly=True
    )
    payment_date = fields.Date(
        string='Payment Date',
        default=fields.Date.context_today
    )
    no_worked_days = fields.Boolean(
        string='No Worked Days',
        default=False,
        help="If checked, the worked days lines will not be computed for this payslip."
    )
    bank_account_id = fields.Many2one(
        'res.partner.bank',
        string='Bank Account',
        compute='_compute_bank_account_id',
        store=True,
        readonly=False
    )
    has_bank_account = fields.Boolean(
        string='Has Bank Account',
        compute='_compute_has_bank_account'
    )
    advice_id = fields.Many2one(
        'hudson.payroll.payment.advice',
        string='Payment Advice',
        readonly=True,
        copy=False,
    )
    effective_advice_id = fields.Many2one(
        'hudson.payroll.payment.advice',
        string='Effective Payment Advice',
        compute='_compute_effective_advice_id',
    )

    @api.depends('advice_id', 'payslip_run_id', 'payslip_run_id.advice_id')
    def _compute_effective_advice_id(self):
        for slip in self:
            slip.effective_advice_id = slip.advice_id or (slip.payslip_run_id and slip.payslip_run_id.advice_id) or False
    total_worked_days = fields.Float(
        string='Worked Days',
        compute='_compute_worked_days_totals',
        store=True
    )
    total_worked_hours = fields.Float(
        string='Worked Hours',
        compute='_compute_worked_days_totals',
        store=True
    )

    line_ids = fields.One2many(
        'hr.payslip.line',
        'slip_id',
        string='Payslip Lines'
    )
    worked_days_line_ids = fields.One2many(
        'hr.payslip.worked.days',
        'payslip_id',
        string='Worked Days Lines',
        copy=True
    )
    input_line_ids = fields.One2many(
        'hr.payslip.input',
        'payslip_id',
        string='Input Lines',
        copy=True
    )
    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Batch / Payrun',
        copy=False,
        ondelete='cascade'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True
    )
    paid = fields.Boolean(
        string='Paid',
        compute='_compute_paid',
        store=True,
        readonly=True,
        copy=False
    )

    @api.depends('state')
    def _compute_paid(self):
        for slip in self:
            slip.paid = (slip.state == 'paid')
    note = fields.Text(string='Note', help="Add a note on the printed payslip.")
    credit_note = fields.Boolean(
        string='Credit Note',
        help="Indicates if this payslip is a refund of another payslip"
    )

    # Basic totals computed for list view and quick overview
    gross_wage = fields.Monetary(
        string='Gross Wage',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    net_wage = fields.Monetary(
        string='Net Wage',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    basic_wage = fields.Monetary(
        string='Basic Wage',
        compute='_compute_basic_wage',
        store=True,
        currency_field='currency_id',
        help="Basic wage computed from salary rule lines or contract basic salary."
    )
    payslip_warning = fields.Char(
        string='Warnings',
        compute='_compute_payslip_warning',
        store=True,
        help="Warnings such as attendance shortage or missing bank account."
    )

    # Backward compatibility aliases
    gross_amount = fields.Monetary(
        string='Gross Amount',
        related='gross_wage',
        store=False,
        currency_field='currency_id',
        help="Alias for gross_wage for backward compatibility."
    )
    net_amount = fields.Monetary(
        string='Net Amount',
        related='net_wage',
        store=False,
        currency_field='currency_id',
        help="Alias for net_wage for backward compatibility."
    )

    # Related Contract Breakdown Fields for Views & Reporting
    contract_wage = fields.Monetary(related='contract_id.wage', string='Contract Wage', currency_field='currency_id', readonly=True)
    contract_basic_salary = fields.Monetary(related='contract_id.basic_salary', string='Contract Basic Salary', currency_field='currency_id', readonly=True)
    contract_hra = fields.Monetary(related='contract_id.hra', string='Contract HRA', currency_field='currency_id', readonly=True)
    contract_da = fields.Monetary(related='contract_id.da', string='Contract DA', currency_field='currency_id', readonly=True)
    contract_fixed_allowance = fields.Monetary(related='contract_id.fixed_allowance', string='Contract Fixed Allowance', currency_field='currency_id', readonly=True)

    # Multi-Stage Dynamic Display Fields
    contract_working_hours = fields.Char(
        string='Working Hours',
        compute='_compute_stage_metrics',
        store=True,
    )
    contract_start_date = fields.Date(
        string='Start Date',
        related='contract_id.date_start',
        readonly=True,
    )
    contract_end_date = fields.Date(
        string='Termination',
        related='contract_id.date_end',
        readonly=True,
    )
    contract_review = fields.Char(
        string='Review',
        compute='_compute_stage_metrics',
        store=True,
    )
    time_off_days = fields.Float(
        string='Time Off (Days)',
        compute='_compute_stage_metrics',
        store=True,
    )
    time_off_summary = fields.Char(
        string='Time Off Type',
        compute='_compute_stage_metrics',
        store=True,
    )
    attendance_expected_hours = fields.Float(
        string='Expected Hours',
        compute='_compute_stage_metrics',
        store=True,
    )
    attendance_shortage_display = fields.Char(
        string='Anomaly / Shortage',
        compute='_compute_stage_metrics',
        store=True,
    )

    @api.depends('contract_id', 'contract_id.resource_calendar_id', 'employee_id.resource_calendar_id',
                 'worked_days_line_ids.number_of_days', 'worked_days_line_ids.number_of_hours', 'worked_days_line_ids.code')
    def _compute_stage_metrics(self):
        for slip in self:
            # 1. Working Hours & Review (Stage 1)
            cal = slip.contract_id.resource_calendar_id or slip.employee_id.resource_calendar_id
            slip.contract_working_hours = cal.name if cal else _("40 hours/week")
            slip.contract_review = _("Confirmed") if (slip.contract_id and getattr(slip.contract_id, 'state', 'draft') in ('open', 'confirmed')) else _("Draft")

            # 2. Time Off (Stage 2)
            leave_lines = slip.worked_days_line_ids.filtered(lambda l: l.code not in ('WORK100', 'SHORTAGE') and l.number_of_days > 0)
            slip.time_off_days = sum(leave_lines.mapped('number_of_days'))
            slip.time_off_summary = ", ".join(leave_lines.mapped('name')) if leave_lines else _("No Time Off")

            # 3. Attendances & Anomalies (Stage 3)
            work_lines = slip.worked_days_line_ids.filtered(lambda l: l.code == 'WORK100')
            shortage_lines = slip.worked_days_line_ids.filtered(lambda l: l.code == 'SHORTAGE' and l.number_of_hours > 0)
            worked_h = sum(work_lines.mapped('number_of_hours')) if work_lines else slip.total_worked_hours
            short_h = sum(shortage_lines.mapped('number_of_hours')) if shortage_lines else 0.0
            slip.attendance_expected_hours = worked_h + short_h
            if short_h > 0:
                slip.attendance_shortage_display = _("Shortage: %s hrs") % round(short_h, 2)
            else:
                slip.attendance_shortage_display = _("Normal")

    def _get_localization_context(self, localdict):
        """Generic extension hook for country payroll localizations.
        Overridden by country modules (e.g. hudson_in_payroll, hudson_ae_payroll)
        to inject statutory calculation engines (EPF, ESIC, PT, TDS, EOSB) into localdict.
        """
        self.ensure_one()
        return localdict

    @api.depends('line_ids.total')
    def _compute_totals(self):
        for slip in self:
            gross = sum(l.total for l in slip.line_ids if l.category_id.code == 'GROSS')
            net = sum(l.total for l in slip.line_ids if l.category_id.code == 'NET')
            slip.gross_wage = gross
            slip.net_wage = net

    @api.depends('line_ids.total', 'line_ids.category_id.code', 'contract_id.basic_salary', 'contract_id.wage')
    def _compute_basic_wage(self):
        for slip in self:
            basic_lines = slip.line_ids.filtered(lambda l: l.category_id.code == 'BASIC' or l.code == 'BASIC')
            if basic_lines:
                slip.basic_wage = sum(basic_lines.mapped('total'))
            elif slip.contract_id:
                slip.basic_wage = slip.contract_id.basic_salary or slip.contract_id.wage or 0.0
            else:
                slip.basic_wage = 0.0

    @api.depends('worked_days_line_ids.number_of_hours', 'worked_days_line_ids.code', 'employee_id.bank_account_id', 'bank_account_id')
    def _compute_payslip_warning(self):
        for slip in self:
            warnings = []
            shortage_lines = slip.worked_days_line_ids.filtered(lambda l: l.code == 'SHORTAGE' and l.number_of_hours > 0)
            if shortage_lines:
                total_shortage = sum(shortage_lines.mapped('number_of_hours'))
                warnings.append(_("Shortage: %s hrs") % round(total_shortage, 2))
            elif hasattr(slip, 'attendance_discrepancy_hours') and slip.attendance_discrepancy_hours < -0.01:
                warnings.append(_("Discrepancy: %s hrs") % round(abs(slip.attendance_discrepancy_hours), 2))
            if not slip.has_bank_account:
                warnings.append(_("No bank account -> Employee"))
            slip.payslip_warning = ", ".join(warnings) if warnings else False

    def action_detach_off_cycle(self):
        """Detach this payslip from the pay run to send it to the Off-Cycle (individual payslip)."""
        runs = self.mapped('payslip_run_id')
        for slip in self:
            slip.payslip_run_id = False
        if runs:
            runs._compute_counts()
            runs._compute_financial_totals()
            runs._compute_milestones()
        return True

    def action_remove_from_run(self):
        """Removes/deletes or detaches an employee payslip from the pay run."""
        for slip in self:
            run = slip.payslip_run_id
            if slip.state in ('draft', 'verify'):
                slip.unlink()
            else:
                slip.payslip_run_id = False
            if run:
                run._compute_counts()
                run._compute_financial_totals()
                run._compute_milestones()
        return True

    @api.constrains('employee_id', 'payslip_run_id')
    def _check_unique_employee_per_run(self):
        for slip in self:
            if slip.payslip_run_id and slip.employee_id:
                duplicate = self.search([
                    ('payslip_run_id', '=', slip.payslip_run_id.id),
                    ('employee_id', '=', slip.employee_id.id),
                    ('id', '!=', slip.id)
                ], limit=1)
                if duplicate:
                    raise UserError(_(
                        "Employee '%(emp)s' already has a payslip in this pay run batch! Duplicate payslips for the same employee are not allowed."
                    ) % {'emp': slip.employee_id.name})

    @api.depends('worked_days_line_ids.number_of_days', 'worked_days_line_ids.number_of_hours')
    def _compute_worked_days_totals(self):
        for slip in self:
            slip.total_worked_days = sum(line.number_of_days for line in slip.worked_days_line_ids)
            slip.total_worked_hours = sum(line.number_of_hours for line in slip.worked_days_line_ids)

    @api.depends('employee_id', 'employee_id.bank_account_id')
    def _compute_bank_account_id(self):
        for slip in self:
            if not slip.bank_account_id and slip.employee_id and slip.employee_id.bank_account_id:
                slip.bank_account_id = slip.employee_id.bank_account_id

    @api.depends('employee_id', 'employee_id.bank_account_id', 'bank_account_id')
    def _compute_has_bank_account(self):
        for slip in self:
            slip.has_bank_account = bool(slip.bank_account_id or (slip.employee_id and slip.employee_id.bank_account_id))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            emp_id = vals.get('employee_id')
            if emp_id:
                emp = self.env['hr.employee'].browse(emp_id)
                if not vals.get('company_id'):
                    vals['company_id'] = emp.company_id.id or self.env.company.id
                if not vals.get('contract_id'):
                    contract = emp.version_id or self.env['hr.version'].search([('employee_id', '=', emp.id)], limit=1, order='id desc')
                    if contract:
                        vals['contract_id'] = contract.id
                if not vals.get('struct_id'):
                    contract_id = vals.get('contract_id')
                    contract = self.env['hr.version'].browse(contract_id) if contract_id else (emp.version_id or False)
                    struct = getattr(contract, 'struct_id', False) if contract else False
                    if not struct and contract and hasattr(contract, 'structure_type_id') and contract.structure_type_id:
                        struct = getattr(contract.structure_type_id, 'default_struct_id', False) or self.env['hr.payroll.structure'].search([
                            ('type_id', '=', contract.structure_type_id.id)
                        ], limit=1)
                    if not struct:
                        struct = self.env['hr.payroll.structure'].search([('code', '=', 'REGULAR')], limit=1) or self.env['hr.payroll.structure'].search([], limit=1)
                    if struct:
                        vals['struct_id'] = struct.id
                if not vals.get('name'):
                    date_from = vals.get('date_from') or fields.Date.today().replace(day=1)
                    date_str = fields.Date.from_string(date_from).strftime('%B %Y') if date_from else ''
                    vals['name'] = _('Salary Slip - %(emp)s - %(period)s') % {
                        'emp': emp.name,
                        'period': date_str
                    }
        slips = super().create(vals_list)
        for slip in slips:
            if not slip.worked_days_line_ids:
                slip._populate_worked_days()
            if not slip.input_line_ids:
                slip._populate_inputs()
        return slips

    @api.onchange('date_from')
    def _onchange_date_from(self):
        if self.date_from:
            last_day = calendar.monthrange(self.date_from.year, self.date_from.month)[1]
            self.date_to = self.date_from.replace(day=last_day)

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        if not self.employee_id:
            return

        self.company_id = self.employee_id.company_id
        if not self.date_from:
            self.date_from = fields.Date.today().replace(day=1)
        if not self.date_to and self.date_from:
            last_day = calendar.monthrange(self.date_from.year, self.date_from.month)[1]
            self.date_to = self.date_from.replace(day=last_day)

        # 1. Automatic Contract Fetch
        contract = False
        if self.employee_id.version_id:
            c = self.employee_id.version_id
            c_start = getattr(c, 'contract_date_start', False) or getattr(c, 'date_start', False)
            c_end = getattr(c, 'contract_date_end', False) or getattr(c, 'date_end', False)
            if (not c_start or c_start <= self.date_to) and (not c_end or c_end >= self.date_from):
                contract = c

        if not contract:
            domain = [('employee_id', '=', self.employee_id.id)]
            if 'contract_date_start' in self.env['hr.version']._fields:
                domain += [
                    '|', ('contract_date_start', '=', False), ('contract_date_start', '<=', self.date_to),
                    '|', ('contract_date_end', '=', False), ('contract_date_end', '>=', self.date_from),
                ]
            contract = self.env['hr.version'].search(domain, limit=1, order='id desc')

        if not contract and self.employee_id.version_id:
            contract = self.employee_id.version_id

        if not contract:
            contract = self.env['hr.version'].search([('employee_id', '=', self.employee_id.id)], limit=1, order='id desc')

        if contract:
            self.contract_id = contract
            # 2. Automatic Structure Fetch from Contract or Structure Type
            struct = getattr(contract, 'struct_id', False)
            if not struct and hasattr(contract, 'structure_type_id') and contract.structure_type_id:
                struct = getattr(contract.structure_type_id, 'default_struct_id', False) or self.env['hr.payroll.structure'].search([
                    ('type_id', '=', contract.structure_type_id.id)
                ], limit=1)
            if not struct:
                struct = self.env['hr.payroll.structure'].search([('code', '=', 'REGULAR')], limit=1) or self.env['hr.payroll.structure'].search([], limit=1)
            self.struct_id = struct

        # Update payslip name
        date_str = self.date_from.strftime('%B %Y') if self.date_from else ''
        self.name = _('Salary Slip - %(emp)s - %(period)s') % {
            'emp': self.employee_id.name,
            'period': date_str
        }

        # Automatically populate worked days and inputs
        self._populate_worked_days()
        self._populate_inputs()

    def compute_sheet(self):
        """Standard method for computing payslip sheet."""
        return self.action_compute_sheet()

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        """Standard method for computing worked days lines.
        Extended by attendance and leave modules (e.g. hudson_attendance_payroll_link).
        """
        res = []
        for contract in contracts:
            total_days = (date_to - date_from).days + 1
            hours_per_day = 8.0
            calendar = contract.resource_calendar_id or contract.employee_id.resource_calendar_id
            if calendar and calendar.hours_per_day:
                hours_per_day = calendar.hours_per_day

            res.append({
                'name': _("Normal Working Days"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': total_days,
                'number_of_hours': total_days * hours_per_day,
                'contract_id': contract.id,
            })
        return res

    def _populate_worked_days(self):
        """Populates standard worked days lines using get_worked_day_lines."""
        self.ensure_one()
        if not self.contract_id:
            return
        if self.no_worked_days:
            self.worked_days_line_ids = [(5, 0, 0)]
            return
        worked_days = self.get_worked_day_lines(self.contract_id, self.date_from, self.date_to)
        self.worked_days_line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in worked_days]

    @api.onchange('no_worked_days')
    def _onchange_no_worked_days(self):
        if self.no_worked_days:
            self.worked_days_line_ids = [(5, 0, 0)]
        elif self.contract_id and self.date_from and self.date_to:
            self._populate_worked_days()

    def _populate_inputs(self):
        """Populates configured external inputs for the structure without wiping existing user amounts."""
        self.ensure_one()
        if not self.struct_id:
            return
        input_types = self.env['hr.payslip.input.type'].search([
            ('input_line_type_ids', 'in', self.struct_id.id)
        ])
        existing_codes = set(self.input_line_ids.mapped('code'))
        new_lines = []
        for itype in input_types:
            if itype.code not in existing_codes:
                new_lines.append((0, 0, {
                    'name': itype.name,
                    'code': itype.code,
                    'input_type_id': itype.id,
                    'contract_id': self.contract_id.id if self.contract_id else False,
                    'sequence': itype.sequence,
                    'amount': 0.0,
                }))
        if new_lines:
            self.input_line_ids = new_lines
        self._sync_salary_adjustments()

    def _sync_salary_adjustments(self):
        """
        Synchronizes active Salary Adjustments (hr.salary.adjustment) to this payslip's Other Inputs.
        - Identifies applicable running adjustments overlapping this payslip period.
        - Idempotently updates or creates hr.payslip.input lines tagged with adjustment_id.
        - Preserves existing manually entered inputs.
        - Cleans up adjustment-linked input lines if the adjustment was cancelled or no longer active.
        """
        self.ensure_one()
        if not self.employee_id or not self.date_from or not self.date_to:
            return

        adj_model = self.env['hr.salary.adjustment']
        active_adjustments = adj_model.search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'running'),
            ('date_start', '<=', self.date_to),
            '|', ('date_end', '=', False), ('date_end', '>=', self.date_from),
        ])

        applicable_adjustments = self.env['hr.salary.adjustment']
        for adj in active_adjustments:
            # For one-time adjustments, ensure not already applied on another finalized payslip
            if adj.duration == 'one_time':
                finalized_slips = adj.payslip_input_ids.mapped('payslip_id').filtered(
                    lambda p: p.id != self.id and p.state in ('done', 'paid')
                )
                if finalized_slips:
                    adj.state = 'done'
                    continue

            # For limited adjustments with until_amount cap, check if limit already met
            if adj.duration == 'limited' and adj.until_amount:
                prior_applied = sum(
                    inp.amount for inp in adj.payslip_input_ids.filtered(
                        lambda i: i.payslip_id.id != self.id and i.payslip_id.state in ('done', 'paid')
                    )
                )
                if abs(prior_applied) >= abs(adj.until_amount):
                    adj.state = 'done'
                    continue

            applicable_adjustments |= adj

        # 1. Update or create inputs for applicable adjustments
        for adj in applicable_adjustments:
            eff_amount = -adj.amount if adj.negative else adj.amount

            # If limited with until_amount cap, cap this period's amount so it doesn't exceed cap
            if adj.duration == 'limited' and adj.until_amount:
                prior_applied = sum(
                    inp.amount for inp in adj.payslip_input_ids.filtered(
                        lambda i: i.payslip_id.id != self.id and i.payslip_id.state in ('done', 'paid')
                    )
                )
                rem_cap = abs(adj.until_amount) - abs(prior_applied)
                if rem_cap > 0 and abs(eff_amount) > rem_cap:
                    eff_amount = -rem_cap if adj.negative else rem_cap

            existing_linked = self.input_line_ids.filtered(lambda l: l.adjustment_id == adj)
            if existing_linked:
                existing_linked.write({
                    'amount': eff_amount,
                    'name': adj.note or adj.input_type_id.name,
                    'code': adj.input_code,
                    'sequence': adj.input_type_id.sequence or 10,
                })
            else:
                # Check for an unlinked input with same code and 0.0 amount that was auto-created by structure defaults
                unlinked_default = self.input_line_ids.filtered(
                    lambda l: not l.adjustment_id and l.code == adj.input_code and l.amount == 0.0
                )
                if unlinked_default:
                    unlinked_default[0].write({
                        'adjustment_id': adj.id,
                        'amount': eff_amount,
                        'name': adj.note or adj.input_type_id.name,
                        'sequence': adj.input_type_id.sequence or 10,
                    })
                else:
                    self.env['hr.payslip.input'].create({
                        'payslip_id': self.id,
                        'adjustment_id': adj.id,
                        'input_type_id': adj.input_type_id.id,
                        'name': adj.note or adj.input_type_id.name,
                        'code': adj.input_code,
                        'amount': eff_amount,
                        'contract_id': self.contract_id.id if self.contract_id else False,
                        'sequence': adj.input_type_id.sequence or 10,
                    })

        # 2. Clean up inputs previously linked to adjustments that are no longer applicable
        stale_linked = self.input_line_ids.filtered(
            lambda l: l.adjustment_id and l.adjustment_id not in applicable_adjustments
        )
        if stale_linked:
            stale_linked.unlink()

    def _get_eval_context(self):
        """Prepares the clean Python safe_eval dictionary context."""
        self.ensure_one()
        
        # Format worked days dict
        worked_days_dict = {}
        for wd in self.worked_days_line_ids:
            worked_days_dict[wd.code] = wd

        # Format inputs dict
        inputs_dict = {}
        for inp in self.input_line_ids:
            inputs_dict[inp.code] = inp

        categories = CategoryAccumulator()
        rules_dict = {}

        return {
            'payslip': self,
            'payslip_record': self,
            'employee': self.employee_id,
            'contract': self.contract_id,
            'worked_days': BrowsableObject(worked_days_dict),
            'inputs': BrowsableObject(inputs_dict),
            'categories': categories,
            'rules': BrowsableObject(rules_dict),
            '_rules_dict': rules_dict,
            'env': self.env,
        }

    def action_compute_sheet(self):
        """Main computation engine for calculating salary rules in topological order."""
        for slip in self:
            slip._sync_salary_adjustments()
            if not slip.struct_id:
                raise UserError(_("Please assign a Salary Structure to payslip %(name)s") % {'name': slip.name})

            rules = slip.struct_id.get_all_rules()
            localdict = slip._get_eval_context()
            localdict = slip._get_localization_context(localdict)
            categories = localdict['categories']
            rules_dict = localdict['_rules_dict']

            lines_vals = []
            for rule in rules:
                if not rule._satisfies_condition(localdict):
                    continue

                amount, rate, qty = rule._compute_rule(localdict)
                total = qty * amount * rate / 100.0

                # Register in localdict for subsequent rules
                rule_res = RuleResult(amount=amount, rate=rate, quantity=qty)
                rules_dict[rule.code] = rule_res
                localdict[rule.code] = total
                categories.add(rule.category_id, total)

                lines_vals.append((0, 0, {
                    'name': rule.name,
                    'code': rule.code,
                    'sequence': rule.sequence,
                    'salary_rule_id': rule.id,
                    'employee_id': slip.employee_id.id,
                    'contract_id': slip.contract_id.id,
                    'amount': amount,
                    'rate': rate,
                    'quantity': qty,
                    'appears_on_payslip': (True if rule.appears_on_payslip == 'always' else False if rule.appears_on_payslip == 'never' else bool(amount)),
                }))

            slip.line_ids = [(5, 0, 0)] + lines_vals
        return True

    def action_payslip_draft(self):
        return self.write({'state': 'draft'})

    def action_payslip_verify(self):
        return self.write({'state': 'verify'})

    def action_payslip_done(self):
        for slip in self:
            if not slip.number:
                slip.number = self.env['ir.sequence'].next_by_code('hr.payslip') or _('New')
            # Check applied salary adjustments
            for inp in slip.input_line_ids.filtered(lambda l: l.adjustment_id):
                adj = inp.adjustment_id
                if adj.duration == 'one_time':
                    adj.state = 'done'
                elif adj.duration == 'limited':
                    # Check if total cap met
                    if adj.until_amount:
                        total_applied = sum(
                            l.amount for l in adj.payslip_input_ids.filtered(
                                lambda i: i.payslip_id.state in ('done', 'paid') or i.payslip_id.id == slip.id
                            )
                        )
                        if abs(total_applied) >= abs(adj.until_amount):
                            adj.state = 'done'
                    # Check if date_end passed
                    if adj.date_end and slip.date_to and slip.date_to >= adj.date_end:
                        adj.state = 'done'
        return self.write({'state': 'done'})

    def action_payslip_paid(self):
        return self.write({'paid': True, 'state': 'paid'})

    def action_open_pay_wizard(self):
        """Opens Payment Advice Wizard for this individual payslip."""
        self.ensure_one()
        return {
            'name': _('Pay'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.run.pay.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payslip_id': self.id,
                'default_payslip_run_id': self.payslip_run_id.id if self.payslip_run_id else False,
                'active_id': self.id,
                'active_model': 'hr.payslip',
            },
        }

    def action_open_payment_advice(self):
        """Opens the related Payment Advice for this payslip."""
        self.ensure_one()
        advice = self.effective_advice_id
        if not advice:
            return False
        return {
            'name': _('Payment Advice'),
            'type': 'ir.actions.act_window',
            'res_model': 'hudson.payroll.payment.advice',
            'view_mode': 'form',
            'res_id': advice.id,
            'target': 'current',
        }

    def action_payslip_send_email(self):
        """Open mail composer to send the payslip to the employee with PDF attached."""
        self.ensure_one()
        template = self.env.ref('hudson_payroll_base.mail_template_payslip', raise_if_not_found=False)
        ctx = {
            'default_model': 'hr.payslip',
            'default_res_ids': [self.id],
            'default_use_template': bool(template),
            'default_template_id': template.id if template else False,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
        }
        emp_partner = (
            getattr(self.employee_id, 'work_contact_id', False)
            or getattr(self.employee_id, 'address_home_id', False)
            or (self.employee_id.user_id and self.employee_id.user_id.partner_id)
        )
        if emp_partner:
            ctx['default_partner_ids'] = [emp_partner.id]
        if self.employee_id.work_email:
            ctx['default_email_to'] = self.employee_id.work_email

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Payslip by Email'),
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'target': 'new',
            'context': ctx,
        }

    def action_print_payslip(self):
        report = self.env.ref('hudson_payroll_base.action_report_payslip', raise_if_not_found=False)
        if report:
            return report.report_action(self)
        return True

    def action_payslip_cancel(self):
        for slip in self:
            for inp in slip.input_line_ids.filtered(lambda l: l.adjustment_id):
                adj = inp.adjustment_id
                if adj.state == 'done':
                    other_done = adj.payslip_input_ids.filtered(
                        lambda i: i.payslip_id.id != slip.id and i.payslip_id.state in ('done', 'paid')
                    )
                    if not other_done:
                        adj.state = 'running'
        return self.write({'state': 'cancel'})

    def refund_sheet(self):
        """Create a reverse/refund credit note payslip."""
        for slip in self:
            copied_slip = slip.copy({
                'credit_note': True,
                'name': _('Refund: ') + slip.name,
                'state': 'draft',
            })
            copied_slip.compute_sheet()
            for line in copied_slip.line_ids:
                line.amount = -line.amount
        return True
