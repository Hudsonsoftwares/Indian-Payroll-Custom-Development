# -*- coding: utf-8 -*-
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    """Batch processing of multiple payslips for a given pay cycle with Department & Payment Advice support."""
    _name = 'hr.payslip.run'
    _inherit = ['mail.thread']
    _description = 'Payslip Batches / Pay Runs'
    _order = 'date_end desc, id desc'

    name = fields.Char(string='Batch Name', required=True, tracking=True)
    number = fields.Char(string='Reference', copy=False, readonly=True)
    date_start = fields.Date(
        string='Date From',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1)
    )
    date_end = fields.Date(
        string='Date To',
        required=True,
        default=lambda self: (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('close', 'Done'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft', tracking=True)
    active_stage = fields.Selection([
        ('employees', 'Employees'),
        ('time', 'Time'),
        ('attendances', 'Attendances'),
        ('payslips', 'Payslips'),
    ], string='Active Stage', default='employees', required=True)

    # Scoping & Filtering
    department_ids = fields.Many2many(
        'hr.department',
        'hr_payslip_run_department_rel',
        'run_id',
        'department_id',
        string='Departments',
        help="Filter pay run by department(s). Leave empty to process all departments."
    )
    employee_type_ids = fields.Many2many(
        'hr.employee.type',
        'hr_payslip_run_employee_type_rel',
        'run_id',
        'type_id',
        string='Employee Types',
        help="Filter pay run by employee types. Leave empty for all types."
    )
    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Salary Structure',
        help="Specific salary structure override. Leave empty to use employee contract structure."
    )

    # Payment Advice Link
    advice_id = fields.Many2one(
        'hudson.payroll.payment.advice',
        string='Payment Advice',
        copy=False,
        ondelete='set null'
    )
    advice_count = fields.Integer(
        string='Payment Advice Count',
        compute='_compute_advice_count'
    )

    slip_ids = fields.One2many(
        'hr.payslip',
        'payslip_run_id',
        string='Payslips'
    )
    payslip_count = fields.Integer(
        string='Payslip Count',
        compute='_compute_counts'
    )
    employee_count = fields.Integer(
        string='Eligible Employees',
        compute='_compute_counts'
    )
    department_count = fields.Integer(
        string='Departments Count',
        compute='_compute_counts'
    )
    department_names = fields.Char(
        string='Department Scoping',
        compute='_compute_counts'
    )

    dep_summary_ids = fields.One2many(
        'hr.payslip.run.dep.summary',
        'payslip_run_id',
        string='Department Summaries'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    # Progress Milestones & Attendance Anomaly Detection
    has_attendance_shortage = fields.Boolean(
        string='Has Attendance Shortage',
        compute='_compute_milestones',
        store=True,
    )
    attendance_shortage_hours = fields.Float(
        string='Attendance Shortage Hours',
        compute='_compute_milestones',
        store=True,
    )
    milestone_employees = fields.Boolean(
        string='Milestone: Employees',
        compute='_compute_milestones',
        store=True,
    )
    milestone_time = fields.Boolean(
        string='Milestone: Time',
        compute='_compute_milestones',
        store=True,
    )
    milestone_attendances = fields.Boolean(
        string='Milestone: Attendances',
        compute='_compute_milestones',
        store=True,
    )
    milestone_payslips = fields.Boolean(
        string='Milestone: Payslips',
        compute='_compute_milestones',
        store=True,
    )
    is_fully_achieved = fields.Boolean(
        string='Is Fully Achieved',
        compute='_compute_milestones',
        store=True,
        help="True only when all milestones are completed, all payslips are done/paid, and batch is closed/confirmed without attendance shortages."
    )
    period_summary_str = fields.Char(
        string='Period Summary',
        compute='_compute_period_summary_str',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True
    )
    employer_cost_total = fields.Monetary(
        string='Employer Cost',
        compute='_compute_financial_totals',
        currency_field='currency_id',
        store=True
    )
    gross_wage_total = fields.Monetary(
        string='Gross',
        compute='_compute_financial_totals',
        currency_field='currency_id',
        store=True
    )
    net_wage_total = fields.Monetary(
        string='Net',
        compute='_compute_financial_totals',
        currency_field='currency_id',
        store=True
    )
    has_done_slips = fields.Boolean(
        string='Has Done Slips',
        compute='_compute_slips_status',
    )
    slips_all_done = fields.Boolean(
        string='All Payslips Done',
        compute='_compute_slips_status',
    )
    show_payment_advice_btn = fields.Boolean(
        string='Show Payment Advice Button',
        compute='_compute_slips_status',
    )
    stepper_html = fields.Html(
        string='Progress Stepper',
        compute='_compute_stepper_html',
        sanitize=False,
    )

    @api.depends('slip_ids.state', 'state', 'active_stage')
    def _compute_slips_status(self):
        for run in self:
            has_done = any(s.state in ('done', 'paid') for s in run.slip_ids)
            all_done = bool(run.slip_ids) and all(s.state in ('done', 'paid') for s in run.slip_ids)
            run.has_done_slips = has_done
            run.slips_all_done = all_done
            run.show_payment_advice_btn = (has_done or run.state in ('confirmed', 'close')) and run.state != 'paid'

    @api.depends('slip_ids.gross_wage', 'slip_ids.net_wage', 'slip_ids.line_ids.total')
    def _compute_financial_totals(self):
        for run in self:
            gross = sum(run.slip_ids.mapped('gross_wage'))
            net = sum(run.slip_ids.mapped('net_wage'))
            comp = sum(
                sum(l.total for l in slip.line_ids if l.category_id.code == 'COMP')
                for slip in run.slip_ids
            )
            run.gross_wage_total = gross
            run.net_wage_total = net
            run.employer_cost_total = (gross + comp) if comp > 0 else (gross if gross > 0 else net)

    @api.depends('milestone_employees', 'milestone_time', 'milestone_attendances', 'milestone_payslips', 'has_attendance_shortage', 'active_stage', 'state')
    def _compute_stepper_html(self):
        for run in self:
            if run.state == 'paid':
                # Paid state: all circles & connectors turn rose/orchid with checkmark on Payslips (Matching Screenshot)
                c_rose = '#c084fc'
                arr_emp = '<div style="height: 13px;"></div>'
                arr_time = '<div style="height: 13px;"></div>'
                arr_att = '<div style="height: 13px;"></div>'
                arr_pay = f'<i class="fa fa-chevron-down" style="color: {c_rose}; font-size: 11px; margin-bottom: 2px;"></i>'

                emp_circle = f'<div style="width: 18px; height: 18px; border-radius: 50%; background-color: {c_rose};"></div>'
                time_circle = f'<div style="width: 18px; height: 18px; border-radius: 50%; background-color: {c_rose};"></div>'
                att_circle = f'<div style="width: 18px; height: 18px; border-radius: 50%; background-color: {c_rose};"></div>'
                pay_circle = f'<div style="width: 18px; height: 18px; border-radius: 50%; background-color: {c_rose}; display: flex; align-items: center; justify-content: center; color: #ffffff; font-size: 9px;"><i class="fa fa-check"></i></div>'

                c_conn1 = c_rose
                c_conn2 = c_rose
                c_conn3 = c_rose
            else:
                c_emp = '#22c55e' if run.milestone_employees else '#3b82f6'
                c_conn1 = '#22c55e' if run.milestone_time else '#3b82f6'
                c_time = '#22c55e' if run.milestone_time else '#3b82f6'
                c_conn2 = '#22c55e' if run.milestone_attendances else '#3b82f6'
                c_conn3 = '#22c55e' if run.milestone_payslips else '#3b82f6'
                c_payslips = '#22c55e' if run.milestone_payslips else '#3b82f6'

                # Chevron indicators matching Screenshots 2, 3, 4
                arr_emp = '<i class="fa fa-chevron-down" style="color: #c084fc; font-size: 11px; margin-bottom: 2px;"></i>' if run.active_stage == 'employees' else '<div style="height: 13px;"></div>'
                arr_time = '<i class="fa fa-chevron-down" style="color: #c084fc; font-size: 11px; margin-bottom: 2px;"></i>' if run.active_stage == 'time' else '<div style="height: 13px;"></div>'
                arr_att = '<i class="fa fa-chevron-down" style="color: #c084fc; font-size: 11px; margin-bottom: 2px;"></i>' if run.active_stage == 'attendances' else '<div style="height: 13px;"></div>'
                arr_pay = '<i class="fa fa-chevron-down" style="color: #c084fc; font-size: 11px; margin-bottom: 2px;"></i>' if run.active_stage == 'payslips' else '<div style="height: 13px;"></div>'

                emp_circle = f'<div style="width: 18px; height: 18px; border-radius: 50%; background-color: {c_emp};"></div>'
                time_circle = f'<div style="width: 18px; height: 18px; border-radius: 50%; background-color: {c_time};"></div>'

                if run.has_attendance_shortage:
                    att_circle = '<div style="width: 18px; height: 18px; border-radius: 50%; border: 2px solid #f59e0b; color: #f59e0b; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; background: transparent;" title="Attendance Shortage Anomaly">!</div>'
                elif run.milestone_attendances:
                    att_circle = '<div style="width: 18px; height: 18px; border-radius: 50%; background-color: #22c55e;"></div>'
                else:
                    att_circle = '<div style="width: 18px; height: 18px; border-radius: 50%; background-color: #3b82f6;"></div>'

                pay_circle = f'<div style="width: 18px; height: 18px; border-radius: 50%; background-color: {c_payslips};"></div>'

            run.stepper_html = f"""
            <div style="display: flex; align-items: center; justify-content: flex-end; font-family: inherit; margin-bottom: 2px;">
                <div style="display: flex; flex-direction: column; align-items: center; width: 75px;">
                    {arr_emp}
                    {emp_circle}
                </div>
                <div style="width: 22px; height: 2px; background-color: {c_conn1}; margin-top: 13px;"></div>
                <div style="display: flex; flex-direction: column; align-items: center; width: 55px;">
                    {arr_time}
                    {time_circle}
                </div>
                <div style="width: 22px; height: 2px; background-color: {c_conn2}; margin-top: 13px;"></div>
                <div style="display: flex; flex-direction: column; align-items: center; width: 85px;">
                    {arr_att}
                    {att_circle}
                </div>
                <div style="width: 22px; height: 2px; background-color: {c_conn3}; margin-top: 13px;"></div>
                <div style="display: flex; flex-direction: column; align-items: center; width: 70px;">
                    {arr_pay}
                    {pay_circle}
                </div>
            </div>
            """

    @api.depends('date_start', 'date_end', 'payslip_count', 'employee_count')
    def _compute_period_summary_str(self):
        for run in self:
            count = run.payslip_count or run.employee_count or 0
            d_start = run.date_start.strftime("%d %b").lstrip("0") if run.date_start else ""
            d_end = run.date_end.strftime("%d %b").lstrip("0") if run.date_end else ""
            emp_label = _("Employee") if count == 1 else _("Employees")
            run.period_summary_str = f"{d_start} -> {d_end} | {count} {emp_label}"

    @api.depends('slip_ids', 'slip_ids.state', 'slip_ids.worked_days_line_ids', 'state')
    def _compute_milestones(self):
        for run in self:
            slips = run.slip_ids
            # 1. Employees milestone
            run.milestone_employees = bool(slips or run.employee_count > 0)

            # 2. Time milestone (worked days calculated or run confirmed)
            has_worked_days = any(bool(slip.worked_days_line_ids) for slip in slips) if slips else False
            run.milestone_time = has_worked_days or (bool(slips) and run.state in ('confirmed', 'paid', 'close'))

            # 3. Attendances & Shortage Anomaly
            total_shortage = 0.0
            for slip in slips:
                shortage_lines = slip.worked_days_line_ids.filtered(lambda l: l.code == 'SHORTAGE' and l.number_of_hours > 0)
                if shortage_lines:
                    total_shortage += sum(shortage_lines.mapped('number_of_hours'))
                elif hasattr(slip, 'attendance_discrepancy_hours') and slip.attendance_discrepancy_hours < -0.01:
                    total_shortage += abs(slip.attendance_discrepancy_hours)

            run.attendance_shortage_hours = total_shortage
            run.has_attendance_shortage = total_shortage > 0.01

            # Attendances dot is filled ONLY if slips exist AND no shortage!
            run.milestone_attendances = bool(slips) and not run.has_attendance_shortage

            # 4. Payslips milestone (all payslips done or paid)
            has_done_slips = bool(slips) and all(s.state in ('done', 'paid') for s in slips)
            run.milestone_payslips = has_done_slips or (bool(slips) and run.state in ('confirmed', 'paid', 'close'))

            # Fully Achieved = batch is confirmed/paid/close or all slips done, AND no attendance shortage!
            run.is_fully_achieved = bool(slips) and (run.state in ('confirmed', 'paid', 'close') or has_done_slips) and not run.has_attendance_shortage

    @api.depends('advice_id')
    def _compute_advice_count(self):
        for run in self:
            count = self.env['hudson.payroll.payment.advice'].search_count([('payslip_run_id', '=', run.id)])
            run.advice_count = count if count else (1 if run.advice_id else 0)

    def _get_eligible_employees_domain(self):
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('active', '=', True)
        ]
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        if self.employee_type_ids:
            reg_type = self.env['hr.employee.type'].search([('code', '=', 'EMP')], limit=1)
            if reg_type and reg_type.id in self.employee_type_ids.ids:
                domain.append('|')
                domain.append(('employee_type_id', 'in', self.employee_type_ids.ids))
                domain.append(('employee_type_id', '=', False))
            else:
                domain.append(('employee_type_id', 'in', self.employee_type_ids.ids))
        return domain

    @api.depends('slip_ids', 'department_ids', 'employee_type_ids', 'company_id')
    def _compute_counts(self):
        for run in self:
            run.payslip_count = len(run.slip_ids)
            domain = run._get_eligible_employees_domain()
            run.employee_count = self.env['hr.employee'].search_count(domain)
            run.department_count = len(run.department_ids) if run.department_ids else self.env['hr.department'].search_count([('company_id', '=', run.company_id.id)])
            if run.department_ids:
                run.department_names = ", ".join(run.department_ids.mapped('name'))
            else:
                run.department_names = _("All Departments")

    @api.onchange('department_ids', 'employee_type_ids')
    def _onchange_scoping_filters(self):
        """Immediately update counts and feedback when filters change in the form."""
        if self.company_id:
            domain = [
                ('company_id', '=', self.company_id.id),
                ('active', '=', True)
            ]
            if self.department_ids:
                domain.append(('department_id', 'in', self.department_ids.ids))
            if self.employee_type_ids:
                reg_type = self.env['hr.employee.type'].search([('code', '=', 'EMP')], limit=1)
                if reg_type and reg_type.id in self.employee_type_ids.ids:
                    domain.append('|')
                    domain.append(('employee_type_id', 'in', self.employee_type_ids.ids))
                    domain.append(('employee_type_id', '=', False))
                else:
                    domain.append(('employee_type_id', 'in', self.employee_type_ids.ids))
            self.employee_count = self.env['hr.employee'].search_count(domain)
            self.department_count = len(self.department_ids) if self.department_ids else self.env['hr.department'].search_count([('company_id', '=', self.company_id.id)])
            if self.department_ids:
                self.department_names = ", ".join(self.department_ids.mapped('name'))
            else:
                self.department_names = _("All Departments")

    def action_open_eligible_employees(self):
        self.ensure_one()
        domain = self._get_eligible_employees_domain()
        return {
            'name': _('Eligible Employees'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': domain,
        }

    def action_open_departments(self):
        self.ensure_one()
        domain = [('id', 'in', self.department_ids.ids)] if self.department_ids else [('company_id', '=', self.company_id.id)]
        return {
            'name': _('Departments'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.department',
            'view_mode': 'list,form',
            'domain': domain,
        }

    def action_draft(self):
        return self.write({'state': 'draft'})

    def action_generate_payslips(self):
        """Generates payslips for all eligible employees based on department and type filters."""
        self.ensure_one()
        domain = self._get_eligible_employees_domain()
        employees = self.env['hr.employee'].search(domain)
        if not employees:
            raise UserError(_("No eligible employees found for the specified department/type criteria."))

        # Existing employee IDs in batch to prevent duplication
        existing_emp_ids = self.slip_ids.mapped('employee_id.id')
        created_slips = self.env['hr.payslip']

        for emp in employees:
            if emp.id in existing_emp_ids:
                continue

            contract = False
            if emp.version_id:
                c = emp.version_id
                c_start = getattr(c, 'contract_date_start', False) or getattr(c, 'date_start', False)
                c_end = getattr(c, 'contract_date_end', False) or getattr(c, 'date_end', False)
                if (not c_start or c_start <= self.date_end) and (not c_end or c_end >= self.date_start):
                    contract = c

            if not contract:
                domain = [('employee_id', '=', emp.id)]
                if 'contract_date_start' in self.env['hr.version']._fields:
                    domain += [
                        '|', ('contract_date_start', '=', False), ('contract_date_start', '<=', self.date_end),
                        '|', ('contract_date_end', '=', False), ('contract_date_end', '>=', self.date_start),
                    ]
                contract = self.env['hr.version'].search(domain, limit=1, order='id desc')

            if not contract and emp.version_id:
                contract = emp.version_id

            if not contract:
                continue

            struct = self.struct_id or getattr(contract, 'struct_id', False)
            if not struct and hasattr(contract, 'structure_type_id') and contract.structure_type_id:
                struct = contract.structure_type_id.default_struct_id or self.env['hr.payroll.structure'].search([
                    ('type_id', '=', contract.structure_type_id.id)
                ], limit=1)

            if not struct:
                continue

            slip = self.env['hr.payslip'].create({
                'name': _('Salary Slip - %(emp)s - %(period)s') % {
                    'emp': emp.name,
                    'period': self.date_start.strftime('%B %Y')
                },
                'employee_id': emp.id,
                'contract_id': contract.id,
                'struct_id': struct.id,
                'date_from': self.date_start,
                'date_to': self.date_end,
                'payslip_run_id': self.id,
                'company_id': self.company_id.id,
            })
            slip._populate_worked_days()
            slip._populate_inputs()
            created_slips |= slip

        if created_slips:
            created_slips.compute_sheet()

        return True

    def action_compute_all(self):
        """Batch compute all payslips in this run."""
        self.ensure_one()
        self.slip_ids.compute_sheet()
        self._compute_department_summaries()
        return True

    def action_confirm_payrun(self):
        """Confirms batch, computes department summaries, and moves state to confirmed."""
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No payslips found in this batch to confirm."))

        if not self.number:
            self.number = self.env['ir.sequence'].next_by_code('hr.payslip.run') or _('New')

        self.slip_ids.filtered(lambda s: s.state != 'done').action_payslip_done()
        self._compute_department_summaries()
        return self.write({'state': 'confirmed'})

    def action_generate_payment_advice(self):
        """Generates Bank Payment Advice for all confirmed payslips in this batch."""
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No payslips to generate payment advice for."))

        slips_missing_bank = self.slip_ids.filtered(
            lambda s: not (s.bank_account_id or (s.employee_id and s.employee_id.bank_account_id))
        )
        if slips_missing_bank:
            emp_list = "\n • ".join(slips_missing_bank.mapped('employee_id.name'))
            raise UserError(_(
                "Payment Advice cannot be created!\n\n"
                "The following employee(s) do not have a bank account configured:\n"
                " • %(employees)s\n\n"
                "Please configure bank account details for these employee(s) before generating Payment Advice."
            ) % {'employees': emp_list})

        advice = self.advice_id
        if not advice:
            advice = self.env['hudson.payroll.payment.advice'].create({
                'payslip_run_id': self.id,
                'date': fields.Date.today(),
                'company_id': self.company_id.id,
            })
            self.advice_id = advice

        # Build lines
        lines_vals = []
        for slip in self.slip_ids:
            net_amt = slip.net_wage or sum(l.total for l in slip.line_ids if l.category_id.code == 'NET')
            lines_vals.append((0, 0, {
                'payslip_id': slip.id,
                'employee_id': slip.employee_id.id,
                'net_amount': net_amt,
            }))

        advice.line_ids = [(5, 0, 0)] + lines_vals
        return self.action_view_payment_advice()

    def action_pay_payrun(self):
        """Marks pay run as paid."""
        self.ensure_one()
        slips_missing_bank = self.slip_ids.filtered(
            lambda s: not (s.bank_account_id or (s.employee_id and s.employee_id.bank_account_id))
        )
        if slips_missing_bank:
            emp_list = "\n • ".join(slips_missing_bank.mapped('employee_id.name'))
            raise UserError(_(
                "Cannot mark as Paid!\n\n"
                "The following employee(s) do not have a bank account configured:\n"
                " • %(employees)s\n\n"
                "Please configure bank account details for these employee(s) before proceeding."
            ) % {'employees': emp_list})
        self.slip_ids.write({'paid': True, 'state': 'paid'})
        return self.write({'state': 'paid'})

    def unlink(self):
        for run in self:
            # Clean up child payslips
            for slip in run.slip_ids:
                if slip.state not in ('draft', 'cancel'):
                    slip.write({'state': 'draft'})
            run.slip_ids.unlink()

            # Clean up department summaries
            if run.dep_summary_ids:
                run.dep_summary_ids.unlink()

            # Clean up payment advice
            advices = self.env['hudson.payroll.payment.advice'].search([('payslip_run_id', '=', run.id)])
            if advices:
                advices.unlink()
        return super().unlink()

    def action_delete_payrun(self):
        """Permanently deletes this entire pay run and all its associated records, redirecting back to Pay Runs list."""
        self.ensure_one()
        self.unlink()
        return self.env['ir.actions.act_window']._for_xml_id('hudson_payroll_base.action_hr_payslip_run')

    def action_close(self):
        """Aliases to action_delete_payrun so clicking Delete permanently deletes the pay run."""
        return self.action_delete_payrun()

    def action_set_stage_employees(self):
        self.ensure_one()
        self.active_stage = 'employees'

    def action_set_stage_time(self):
        self.ensure_one()
        self.active_stage = 'time'

    def action_set_stage_attendances(self):
        self.ensure_one()
        self.active_stage = 'attendances'

    def action_set_stage_payslips(self):
        self.ensure_one()
        self.active_stage = 'payslips'

    def action_stage_continue(self):
        self.ensure_one()
        stages = ['employees', 'time', 'attendances', 'payslips']
        curr_idx = stages.index(self.active_stage) if self.active_stage in stages else 0
        if curr_idx < len(stages) - 1:
            self.active_stage = stages[curr_idx + 1]
        elif self.active_stage == 'payslips':
            return self.action_batch_validate()
        return True

    def action_batch_validate(self):
        """Validates all payslips, marks payrun confirmed, and opens the individual payslips view (Screenshot 1)."""
        self.ensure_one()
        for slip in self.slip_ids:
            if slip.state in ('draft', 'verify'):
                slip.action_payslip_done()
        if not self.number:
            self.number = self.env['ir.sequence'].next_by_code('hr.payslip.run') or _('New')
        self.write({
            'state': 'confirmed',
            'active_stage': 'payslips',
        })
        self._compute_department_summaries()
        self._compute_milestones()

        if self.slip_ids:
            return {
                'name': _('Employee Payslips'),
                'type': 'ir.actions.act_window',
                'res_model': 'hr.payslip',
                'view_mode': 'form,list',
                'res_id': self.slip_ids[0].id,
                'domain': [('payslip_run_id', '=', self.id)],
                'context': {'default_payslip_run_id': self.id},
            }
        return True

    def action_open_pay_wizard(self):
        """Opens the Pay wizard modal (Screenshot 4)."""
        self.ensure_one()
        if self.state == 'draft' and self.has_done_slips:
            if not self.number:
                self.number = self.env['ir.sequence'].next_by_code('hr.payslip.run') or _('New')
            self.write({'state': 'confirmed'})
        company = self.company_id or self.env.company
        bank_acc = company.partner_id.bank_ids and company.partner_id.bank_ids[0] or False
        if not bank_acc:
            bank_acc = self.env['res.partner.bank'].search([('company_id', '=', company.id)], limit=1)

        wizard = self.env['hr.payslip.run.pay.wizard'].create({
            'payslip_run_id': self.id,
            'payment_date': fields.Date.today(),
            'report_name': f"Payment Advice - {self.name}",
            'company_bank_id': bank_acc.id if bank_acc else False,
            'mode': 'advice',
            'include_unpaid': True,
            'by_neft': True,
            'by_cheque': False,
        })
        return {
            'name': _('Pay'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.run.pay.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_ids': [self.id],
                'active_model': 'hr.payslip.run',
                'default_payslip_run_id': self.id,
            },
        }

    def action_set_to_draft(self):
        """Reverts confirmed pay run to draft (Screenshot 3)."""
        self.ensure_one()
        return self.write({'state': 'draft'})

    def action_revert_paid(self):
        """Reverts paid pay run back to confirmed state (Matching Screenshot)."""
        self.ensure_one()
        self.slip_ids.write({'paid': False, 'state': 'done'})
        self.write({'state': 'confirmed', 'active_stage': 'payslips'})
        self._compute_department_summaries()
        self._compute_milestones()
        return True

    def action_open_warning_payslips(self):
        """Filters payslips with warnings (Matching Screenshot 5)."""
        self.ensure_one()
        slips_with_warnings = self.slip_ids.filtered(lambda s: s.payslip_warning)
        return {
            'name': _('Payslips with Warnings'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', (slips_with_warnings or self.slip_ids).ids)],
            'context': {'default_payslip_run_id': self.id},
        }

    def action_view_work_entries(self):
        """Opens Payslip Work Days Lines Report (Pivot & List) matching Odoo Online."""
        self.ensure_one()
        return {
            'name': _('Payslip Work Days Lines Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.worked.days',
            'view_mode': 'pivot,list',
            'domain': [('payslip_id.payslip_run_id', '=', self.id)],
            'context': {
                'search_default_group_code': 1,
                'default_payslip_run_id': self.id,
            },
        }

    def action_view_payroll_journal(self):
        """Opens Payslip Lines Report (Pivot & List) matching Odoo Online."""
        self.ensure_one()
        return {
            'name': _('Payslip Lines Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.line',
            'view_mode': 'pivot,list',
            'domain': [('slip_id.payslip_run_id', '=', self.id)],
            'context': {
                'search_default_group_code': 1,
                'default_payslip_run_id': self.id,
            },
        }

    def action_view_payslip_lines(self):
        return self.action_view_payroll_journal()

    def _compute_department_summaries(self):
        """Generates aggregate department summaries for this batch."""
        for run in self:
            dep_map = {}
            for slip in run.slip_ids:
                dep = slip.employee_id.department_id
                dep_id = dep.id if dep else False
                if dep_id not in dep_map:
                    dep_map[dep_id] = {
                        'department_id': dep_id,
                        'employee_count': 0,
                        'gross_total': 0.0,
                        'net_total': 0.0,
                    }
                dep_map[dep_id]['employee_count'] += 1
                dep_map[dep_id]['gross_total'] += slip.gross_wage
                dep_map[dep_id]['net_total'] += slip.net_wage

            run.dep_summary_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in dep_map.values()]

    def action_open_payslips(self):
        self.ensure_one()
        return {
            'name': _('Payslips in Batch'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('payslip_run_id', '=', self.id)],
            'context': {'default_payslip_run_id': self.id},
        }

    def action_view_payment_advice(self):
        self.ensure_one()
        advice = self.advice_id
        if not advice:
            advice = self.env['hudson.payroll.payment.advice'].search([('payslip_run_id', '=', self.id)], limit=1)
            if advice:
                self.advice_id = advice
        if not advice:
            raise UserError(_("No Payment Advice created yet."))
        return {
            'name': _('Payment Advice'),
            'type': 'ir.actions.act_window',
            'res_model': 'hudson.payroll.payment.advice',
            'view_mode': 'form',
            'res_id': advice.id,
        }
