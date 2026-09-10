# -*- coding: utf-8 -*-
import base64
import csv
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HudsonPayrollPaymentAdvice(models.Model):
    """Bank Payment Advice statement generated from a pay run for salary disbursement."""
    _name = 'hudson.payroll.payment.advice'
    _description = 'Payroll Payment Advice'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Advice Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Pay Run',
        required=False,
        ondelete='cascade',
        readonly=True
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        required=False,
        ondelete='cascade',
        readonly=True
    )
    date = fields.Date(
        string='Advice Date',
        required=True,
        default=fields.Date.context_today
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    company_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Disbursing Bank Account',
        domain="['|', ('company_id', '=', company_id), ('company_id', '=', False)]",
        help="Select the company bank account used to disburse salaries"
    )
    line_ids = fields.One2many(
        'hudson.payroll.payment.advice.line',
        'advice_id',
        string='Payment Lines'
    )
    total_amount = fields.Float(
        string='Total Disbursed',
        compute='_compute_total_amount',
        store=True,
        digits='Payroll'
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', tracking=True)

    note = fields.Text(string='Notes / Instructions')

    @api.depends('line_ids.net_amount')
    def _compute_total_amount(self):
        for advice in self:
            advice.total_amount = sum(advice.line_ids.mapped('net_amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hudson.payroll.payment.advice') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        return self.write({'state': 'confirmed'})

    def action_set_to_draft(self):
        return self.write({'state': 'draft'})

    def action_export_csv(self):
        """Generates a bank-ready CSV disbursement statement and returns a download action."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No payment advice lines found to export."))

        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Header row
        writer.writerow([
            'Serial No',
            'Employee Code',
            'Employee Name',
            'Bank Name',
            'Account Number',
            'IFSC / Routing Code',
            'Net Amount',
            'Payment Reference',
        ])

        for idx, line in enumerate(self.line_ids, start=1):
            writer.writerow([
                idx,
                line.employee_id.registration_number or '',
                line.employee_id.name or '',
                line.bank_name or '',
                line.acc_number or '',
                line.bank_bic or '',
                f"{line.net_amount:.2f}",
                line.payslip_id.number or self.name,
            ])

        csv_content = output.getvalue().encode('utf-8-sig')
        output.close()

        filename = f"Payment_Advice_{self.name.replace('/', '_')}.csv"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(csv_content),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'text/csv',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_print_pdf(self):
        return self.env.ref('hudson_payroll_base.action_report_payment_advice').report_action(self)


class HudsonPayrollPaymentAdviceLine(models.Model):
    """Line item representing an individual employee bank disbursement."""
    _name = 'hudson.payroll.payment.advice.line'
    _description = 'Payroll Payment Advice Line'
    _order = 'employee_id'

    advice_id = fields.Many2one(
        'hudson.payroll.payment.advice',
        string='Payment Advice',
        required=True,
        ondelete='cascade',
        index=True
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        required=True,
        ondelete='cascade'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        string='Department',
        store=True,
        readonly=True
    )
    bank_account_id = fields.Many2one(
        'res.partner.bank',
        string='Bank Account',
        compute='_compute_bank_details',
        store=True,
        readonly=False
    )
    bank_name = fields.Char(
        string='Bank Name',
        compute='_compute_bank_details',
        store=True
    )
    acc_number = fields.Char(
        string='Account Number',
        compute='_compute_bank_details',
        store=True
    )
    bank_bic = fields.Char(
        string='IFSC / BIC / Routing',
        compute='_compute_bank_details',
        store=True
    )
    net_amount = fields.Float(
        string='Net Payable Amount',
        digits='Payroll',
        default=0.0
    )
    has_bank_account = fields.Boolean(
        string='Bank Configured',
        compute='_compute_bank_details',
        store=True
    )

    @api.depends('employee_id', 'payslip_id')
    def _compute_bank_details(self):
        for line in self:
            slip = line.payslip_id
            bank_acc = False
            if slip and slip.bank_account_id:
                bank_acc = slip.bank_account_id
            elif line.employee_id:
                emp = line.employee_id
                bank_acc = getattr(emp, 'bank_account_id', False) or (emp.bank_account_ids and emp.bank_account_ids[0]) or False
            line.bank_account_id = bank_acc
            line.bank_name = bank_acc.bank_id.name if bank_acc and bank_acc.bank_id else (bank_acc.acc_holder_name or '')
            line.acc_number = bank_acc.acc_number if bank_acc else ''
            line.bank_bic = (bank_acc.bank_id.bic or getattr(bank_acc, 'routing_number', '')) if bank_acc and bank_acc.bank_id else ''
            line.has_bank_account = bool(bank_acc and bank_acc.acc_number)
