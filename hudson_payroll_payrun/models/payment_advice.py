# -*- coding: utf-8 -*-
import base64
import csv
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HudsonPayrollPaymentAdvice(models.Model):
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
        required=True,
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
        string='Company Bank Account',
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
                vals['name'] = self.env['ir.sequence'].next_by_code('hudson.payroll.payment.advice') or _('PA/%s') % fields.Date.today()
        return super(HudsonPayrollPaymentAdvice, self).create(vals_list)

    def action_confirm(self):
        for advice in self:
            advice.write({'state': 'confirmed'})
        return True

    def action_send_email(self):
        """Open mail composer with company bank email pre-populated and PDF advice attached."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_("Please confirm the Payment Advice before sending by email."))

        # 1. Fetch Company Bank Email details
        bank = self.company_bank_id
        email_to = ''
        if bank:
            if bank.partner_id and bank.partner_id.email:
                email_to = bank.partner_id.email
            elif bank.bank_id and hasattr(bank.bank_id, 'email') and bank.bank_id.email:
                email_to = bank.bank_id.email
            elif hasattr(bank, 'email') and bank.email:
                email_to = bank.email

        # 2. Get mail template
        template = self.env.ref('hudson_payroll_payrun.mail_template_payment_advice', False)

        ctx = {
            'default_model': 'hudson.payroll.payment.advice',
            'default_res_ids': [self.id],
            'default_use_template': bool(template),
            'default_template_id': template.id if template else False,
            'default_composition_mode': 'comment',
            'default_email_to': email_to,
            'mark_so_as_sent': True,
            'force_email': True,
        }

        # 3. Generate and attach printable QWeb PDF Payment Advice
        report = self.env.ref('hudson_payroll_payrun.action_report_payment_advice', False)
        if report:
            pdf_content, _ = report._render_qweb_pdf(report.id, [self.id])
            attachment_name = f"Payment_Advice_{self.name.replace('/', '_')}.pdf"
            attachment = self.env['ir.attachment'].create({
                'name': attachment_name,
                'datas': base64.b64encode(pdf_content),
                'res_model': 'hudson.payroll.payment.advice',
                'res_id': self.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
            })
            ctx['default_attachment_ids'] = [(6, 0, [attachment.id])]

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def action_export_csv(self):
        """Generate a CSV bank transfer file for download."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No payment advice lines to export."))

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        
        # Write CSV Header
        writer.writerow([
            'Employee Name',
            'Bank Account Number',
            'Bank Name',
            'IFSC / Routing Code',
            'Net Payable Amount',
            'Status'
        ])

        for line in self.line_ids:
            writer.writerow([
                line.employee_id.name or '',
                line.acc_number or 'NO BANK ACCOUNT',
                line.bank_name or '',
                line.ifsc_code or '',
                f"{line.net_amount:.2f}",
                'VALID' if line.has_bank_account else 'MISSING BANK ACCOUNT'
            ])

        csv_data = output.getvalue().encode('utf-8')
        output.close()

        file_name = f"Payment_Advice_{self.name.replace('/', '_')}.csv"
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': base64.b64encode(csv_data),
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


class HudsonPayrollPaymentAdviceLine(models.Model):
    _name = 'hudson.payroll.payment.advice.line'
    _description = 'Payroll Payment Advice Line'
    _order = 'has_bank_account desc, employee_id'

    advice_id = fields.Many2one(
        'hudson.payroll.payment.advice',
        string='Payment Advice',
        required=True,
        ondelete='cascade',
        index=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip'
    )
    bank_account_id = fields.Many2one(
        'res.partner.bank',
        string='Employee Bank Account'
    )
    acc_number = fields.Char(string='Account Number')
    bank_name = fields.Char(string='Bank Name')
    ifsc_code = fields.Char(string='IFSC / Bank Code')
    net_amount = fields.Float(string='Net Amount', digits='Payroll')
    has_bank_account = fields.Boolean(
        string='Has Bank Account',
        compute='_compute_bank_account_info',
        store=True
    )

    @api.model
    def _get_employee_bank_account(self, employee):
        if not employee:
            return False
        # 1. Direct bank_account_id on hr.employee
        if hasattr(employee, 'bank_account_id') and employee.bank_account_id:
            return employee.bank_account_id
        # 2. Partner bank accounts linked to work_contact_id, address_home_id, or user_id.partner_id
        partners = self.env['res.partner']
        if hasattr(employee, 'work_contact_id') and employee.work_contact_id:
            partners |= employee.work_contact_id
        if hasattr(employee, 'address_home_id') and employee.address_home_id:
            partners |= employee.address_home_id
        if hasattr(employee, 'user_id') and employee.user_id and employee.user_id.partner_id:
            partners |= employee.user_id.partner_id

        for partner in partners:
            if partner.bank_ids:
                return partner.bank_ids[0]

        if partners:
            bank = self.env['res.partner.bank'].search([('partner_id', 'in', partners.ids)], limit=1)
            if bank:
                return bank
        return False

    @api.depends('bank_account_id', 'employee_id', 'employee_id.bank_account_id')
    def _compute_bank_account_info(self):
        for line in self:
            bank = line.bank_account_id or self._get_employee_bank_account(line.employee_id)
            if bank:
                line.bank_account_id = bank.id
                line.has_bank_account = True
                line.acc_number = bank.acc_number or False
                line.bank_name = bank.bank_id.name if bank.bank_id else (bank.acc_holder_name or '')
                line.ifsc_code = bank.bank_bic or bank.acc_type or ''
            else:
                line.has_bank_account = False
                line.acc_number = False
                line.bank_name = False
                line.ifsc_code = False
