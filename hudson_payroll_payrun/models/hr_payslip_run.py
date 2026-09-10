# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('paid', 'Paid'),
            ('close', 'Done'),
        ],
        string='Status',
        index=True,
        readonly=True,
        copy=False,
        default='draft',
        help="Status of Payslip Batch / Pay Run"
    )

    department_ids = fields.Many2many(
        'hr.department',
        'hr_payslip_run_department_rel',
        'run_id',
        'department_id',
        string='Departments',
        help="Filter pay run by department(s). Leave empty to apply to all departments."
    )

    employee_type_ids = fields.Many2many(
        'hr.employee.type',
        'hr_payslip_run_employee_type_rel',
        'run_id',
        'type_id',
        string='Employee Types',
        help="Filter pay run by employee classification types. Leave empty for all types."
    )

    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Salary Structure',
        help="Salary structure used for bulk payslip generation"
    )

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

    employee_count = fields.Integer(
        string='Eligible Employees',
        compute='_compute_employee_count',
        help="Number of active employees matching scope filters and active contracts"
    )

    payslip_count = fields.Integer(
        string='Payslip Count',
        compute='_compute_payslip_count',
        help="Total payslips currently attached to this run"
    )

    department_count = fields.Integer(
        string='Department Count',
        compute='_compute_department_count'
    )

    department_names = fields.Char(
        string='Department Scope',
        compute='_compute_department_names'
    )

    department_summary_ids = fields.One2many(
        'hr.payslip.run.dep.summary',
        'payslip_run_id',
        string='Department Breakdown',
        compute='_compute_department_summary_ids',
        store=False,
        help="Department-wise summary of employee counts and gross/net salary totals"
    )

    generation_log = fields.Text(
        string='Generation Summary',
        readonly=True,
        copy=False
    )

    @api.depends('advice_id')
    def _compute_advice_count(self):
        for run in self:
            run.advice_count = 1 if run.advice_id else 0

    @api.depends('department_ids', 'employee_type_ids', 'date_start', 'date_end')
    def _compute_employee_count(self):
        for run in self:
            domain = [('active', '=', True)]
            if run.department_ids:
                domain.append(('department_id', 'in', run.department_ids.ids))
            if run.employee_type_ids:
                domain.append(('employee_type_id', 'in', run.employee_type_ids.ids))
            domain.append(('company_id', 'in', [self.env.company.id, False]))

            employees = self.env['hr.employee'].search(domain)
            if not (run.date_start and run.date_end):
                run.employee_count = len(employees)
                continue

            count = 0
            for emp in employees:
                contracts = self.env['hr.payslip'].get_contract(emp, run.date_start, run.date_end)
                if contracts:
                    count += 1
            run.employee_count = count

    @api.depends('slip_ids')
    def _compute_payslip_count(self):
        for run in self:
            run.payslip_count = len(run.slip_ids)

    @api.depends('department_ids')
    def _compute_department_count(self):
        for run in self:
            run.department_count = len(run.department_ids)

    @api.depends('department_ids')
    def _compute_department_names(self):
        for run in self:
            if run.department_ids:
                names = run.department_ids.mapped('name')
                run.department_names = ", ".join(names)
            else:
                run.department_names = _("All Departments")

    @api.depends('slip_ids', 'slip_ids.employee_id.department_id', 'slip_ids.gross_amount', 'slip_ids.net_amount')
    def _compute_department_summary_ids(self):
        Summary = self.env['hr.payslip.run.dep.summary']
        for run in self:
            existing = Summary.search([('payslip_run_id', '=', run.id)])
            if existing:
                existing.unlink()

            if not run.slip_ids:
                run.department_summary_ids = [(5, 0, 0)]
                continue

            dept_map = {}
            for slip in run.slip_ids:
                dept = slip.employee_id.department_id
                dept_id = dept.id if dept else False
                if dept_id not in dept_map:
                    dept_map[dept_id] = {
                        'payslip_run_id': run.id,
                        'department_id': dept_id,
                        'employee_count': 0,
                        'gross_total': 0.0,
                        'net_total': 0.0,
                    }
                dept_map[dept_id]['employee_count'] += 1
                dept_map[dept_id]['gross_total'] += slip.gross_amount
                dept_map[dept_id]['net_total'] += slip.net_amount

            created_summaries = Summary.create(list(dept_map.values()))
            run.department_summary_ids = created_summaries

    def action_generate_payslips(self):
        """Bulk generate payslips for active employees matching department and employee type filters."""
        self.ensure_one()
        if not self.date_start or not self.date_end:
            raise UserError(_("Please define Date From and Date To before generating payslips."))

        if self.date_start > self.date_end:
            raise UserError(_("Date From must be earlier than or equal to Date To."))

        domain = [('active', '=', True)]
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        if self.employee_type_ids:
            domain.append(('employee_type_id', 'in', self.employee_type_ids.ids))
        domain.append(('company_id', 'in', [self.env.company.id, False]))

        employees = self.env['hr.employee'].search(domain)
        if not employees:
            raise UserError(_("No active employees found matching the selected scope filters."))

        created_payslips = self.env['hr.payslip']
        created_count = 0
        skipped_count = 0
        log_lines = []
        log_lines.append(_("=== Pay Run Generation Started (%s to %s) ===") % (self.date_start, self.date_end))
        scope_str = ", ".join(self.department_ids.mapped('name')) if self.department_ids else _("All Departments")
        type_str = ", ".join(self.employee_type_ids.mapped('name')) if self.employee_type_ids else _("All Employee Types")
        log_lines.append(_("Target Scope: %s | Types: %s") % (scope_str, type_str))
        log_lines.append(_("Evaluated Employees: %d") % len(employees))
        log_lines.append("-" * 50)

        # Pre-fetch existing non-cancelled payslips for all targeted employees to avoid N search queries in loop
        existing_slips = self.env['hr.payslip'].search([
            ('employee_id', 'in', employees.ids),
            ('state', '!=', 'cancel'),
            ('date_from', '<=', self.date_end),
            ('date_to', '>=', self.date_start),
        ])
        existing_slips_by_emp = {s.employee_id.id: s for s in existing_slips}

        for employee in employees:
            dept_name = employee.department_id.name or _("No Dept")
            
            # 1. Check for active contract
            contract_ids = self.env['hr.payslip'].get_contract(employee, self.date_start, self.date_end)
            if not contract_ids:
                skipped_count += 1
                log_lines.append(_("[SKIPPED] %s (%s): No valid active contract for period.") % (employee.name, dept_name))
                continue

            # 2. Check for duplicate non-cancelled payslip in period
            existing_slip = existing_slips_by_emp.get(employee.id)

            if existing_slip:
                skipped_count += 1
                slip_ref = existing_slip.name or existing_slip.number or str(existing_slip.id)
                log_lines.append(_("[SKIPPED] %s (%s): Existing payslip found (%s).") % (employee.name, dept_name, slip_ref))
                continue

            # 3. Generate payslip
            try:
                slip_data = self.env['hr.payslip'].onchange_employee_id(
                    self.date_start, self.date_end, employee.id, contract_id=False
                )
                vals = slip_data.get('value', {})
                struct_id = self.struct_id.id if self.struct_id else vals.get('struct_id')
                res = {
                    'employee_id': employee.id,
                    'name': vals.get('name') or _('Salary Slip of %s') % employee.name,
                    'struct_id': struct_id,
                    'contract_id': vals.get('contract_id'),
                    'payslip_run_id': self.id,
                    'input_line_ids': [(0, 0, x) for x in vals.get('input_line_ids', [])],
                    'worked_days_line_ids': [(0, 0, x) for x in vals.get('worked_days_line_ids', [])],
                    'date_from': self.date_start,
                    'date_to': self.date_end,
                    'credit_note': self.credit_note,
                    'company_id': employee.company_id.id or self.env.company.id,
                }
                payslip = self.env['hr.payslip'].create(res)
                payslip.action_compute_sheet()
                created_payslips += payslip
                created_count += 1
                log_lines.append(_("[CREATED] %s (%s): Payslip #%s created.") % (employee.name, dept_name, payslip.name))
            except (UserError, ValidationError, ValueError, TypeError) as e:
                _logger.warning("Payslip generation validation error for employee %s (ID: %s) in Pay Run %s: %s", employee.name, employee.id, self.name, str(e), exc_info=True)
                skipped_count += 1
                log_lines.append(_("[ERROR] %s (%s): Failed to create payslip - %s") % (employee.name, dept_name, str(e)))
            except Exception as e:
                _logger.error("Unexpected error creating/computing payslip for employee %s (ID: %s) in Pay Run %s: %s", employee.name, employee.id, self.name, str(e), exc_info=True)
                skipped_count += 1
                log_lines.append(_("[ERROR] %s (%s): Unexpected error - %s") % (employee.name, dept_name, str(e)))

        log_lines.append("-" * 50)
        log_lines.append(_("Generation Complete. Created: %d | Skipped: %d") % (created_count, skipped_count))

        full_log = "\n".join(log_lines)
        self.write({
            'generation_log': full_log,
        })

        if hasattr(self, 'message_post'):
            self.message_post(body=_("Pay Run Generation complete. %d payslips created, %d skipped.") % (created_count, skipped_count))

        return True

    def action_confirm_payrun(self):
        """Confirm the Pay Run and validate underlying payslips."""
        for run in self:
            pending_slips = run.slip_ids.filtered(lambda s: s.state in ('draft', 'verify'))
            for slip in pending_slips:
                if not slip.line_ids:
                    slip.action_compute_sheet()
                slip.action_payslip_done()
            run.write({'state': 'confirmed'})
        return True

    def action_pay_payrun(self):
        """Mark the Pay Run as Paid."""
        return self.write({'state': 'paid'})

    def close_payslip_run(self):
        """Backward compatible close method."""
        return self.action_confirm_payrun()

    def action_payslip_run(self):
        """Set Pay Run back to Draft state."""
        return self.write({'state': 'draft'})

    def action_generate_payment_advice(self):
        """Generate or view the Payment Advice for this Pay Run."""
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No payslips found in this Pay Run to generate Payment Advice."))

        if self.advice_id:
            form_view = self.env.ref('hudson_payroll_payrun.hudson_payment_advice_view_form', False)
            return {
                'name': _('Payment Advice - %s') % self.advice_id.name,
                'type': 'ir.actions.act_window',
                'res_model': 'hudson.payroll.payment.advice',
                'res_id': self.advice_id.id,
                'view_mode': 'form',
                'views': [(form_view and form_view.id or False, 'form')],
                'target': 'current',
            }

        advice_lines = []
        AdviceLine = self.env['hudson.payroll.payment.advice.line']
        for slip in self.slip_ids:
            bank = AdviceLine._get_employee_bank_account(slip.employee_id)
            advice_lines.append((0, 0, {
                'employee_id': slip.employee_id.id,
                'payslip_id': slip.id,
                'bank_account_id': bank.id if bank else False,
                'acc_number': bank.acc_number if bank else False,
                'bank_name': bank.bank_id.name if bank and bank.bank_id else (bank.acc_holder_name if bank else False),
                'ifsc_code': bank.bank_bic or bank.acc_type if bank else False,
                'net_amount': slip.net_amount,
            }))

        advice_vals = {
            'payslip_run_id': self.id,
            'date': fields.Date.today(),
            'company_id': self.env.company.id,
            'line_ids': advice_lines,
        }

        advice = self.env['hudson.payroll.payment.advice'].create(advice_vals)
        self.advice_id = advice.id

        form_view = self.env.ref('hudson_payroll_payrun.hudson_payment_advice_view_form', False)
        return {
            'name': _('Payment Advice - %s') % advice.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hudson.payroll.payment.advice',
            'res_id': advice.id,
            'view_mode': 'form',
            'views': [(form_view and form_view.id or False, 'form')],
            'target': 'current',
        }
