# -*- coding: utf-8 -*-
import base64
import io
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class HudsonPayrollPayRunPayWizard(models.TransientModel):
    """Wizard to execute Pay Run / Payslip payment, generate bank payment advice, Cheque, NEFT, PDF and XLSX."""
    _name = 'hr.payslip.run.pay.wizard'
    _description = 'Pay Run / Payslip Payment Wizard'

    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Pay Run',
        required=False,
        readonly=True,
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        required=False,
        readonly=True,
    )
    mode = fields.Selection([
        ('advice', 'Payment Advice'),
        ('manual', 'Manually'),
        ('csv', 'CSV'),
        ('enet', 'ENet'),
    ], string='Mode', default='advice', required=True)

    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.context_today,
        help="Date on which the salary disbursement will be executed."
    )
    include_unpaid = fields.Boolean(
        string='Include Unpaid',
        default=True,
        help="Include payslips that have not yet been marked as paid."
    )
    report_name = fields.Char(
        string='Report Name',
        help="Custom name for the generated payment report or advice."
    )
    company_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Company Bank Account',
        domain="['|', ('company_id', '=', company_id), ('company_id', '=', False)]",
        help="Disbursing bank account of the company."
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        compute='_compute_company_id',
        store=True,
        readonly=True
    )
    by_cheque = fields.Boolean(
        string='By Cheque',
        default=False
    )
    cheque_number = fields.Char(
        string='Cheque Number',
        help="Reference number of the corporate disbursement cheque."
    )
    cheque_date = fields.Date(
        string='Cheque Date',
        default=fields.Date.context_today,
        help="Date printed on the disbursement cheque."
    )
    by_neft = fields.Boolean(
        string='By NEFT',
        default=True,
        help="Process electronic bank transfer via NEFT / RTGS / IMPS."
    )
    missing_bank_employee_count = fields.Integer(
        string='Missing Bank Employee Count',
        compute='_compute_missing_bank_employees',
    )
    missing_bank_employee_names = fields.Char(
        string='Employees Without Bank Account',
        compute='_compute_missing_bank_employees',
    )

    @api.depends('payslip_run_id', 'payslip_id')
    def _compute_company_id(self):
        for wiz in self:
            if wiz.payslip_run_id:
                wiz.company_id = wiz.payslip_run_id.company_id
            elif wiz.payslip_id:
                wiz.company_id = wiz.payslip_id.company_id
            else:
                wiz.company_id = self.env.company

    @api.depends('payslip_run_id', 'payslip_run_id.slip_ids', 'payslip_id', 'include_unpaid')
    def _compute_missing_bank_employees(self):
        for wiz in self:
            if wiz.payslip_id:
                slips = wiz.payslip_id
            elif wiz.payslip_run_id:
                slips = wiz.payslip_run_id.slip_ids
            else:
                slips = self.env['hr.payslip']
            if not wiz.include_unpaid:
                slips = slips.filtered(lambda s: not getattr(s, 'paid', False))
            missing = slips.filtered(lambda s: not s.has_bank_account)
            wiz.missing_bank_employee_count = len(missing)
            wiz.missing_bank_employee_names = ", ".join(missing.mapped('employee_id.name')) if missing else False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # 1. Check individual payslip context
        slip_id = self.env.context.get('default_payslip_id')
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if not slip_id and active_model == 'hr.payslip' and active_id:
            slip_id = active_id
        
        if slip_id:
            slip = self.env['hr.payslip'].browse(slip_id).exists()
            if slip:
                res['payslip_id'] = slip.id
                if slip.payslip_run_id:
                    res['payslip_run_id'] = slip.payslip_run_id.id
                if 'report_name' in fields_list and not res.get('report_name'):
                    res['report_name'] = f"Payment Advice - {slip.name}"
                company = slip.company_id or self.env.company
                bank_acc = company.partner_id.bank_ids and company.partner_id.bank_ids[0] or False
                if not bank_acc:
                    bank_acc = self.env['res.partner.bank'].search([('company_id', '=', company.id)], limit=1)
                if bank_acc and 'company_bank_id' in fields_list:
                    res['company_bank_id'] = bank_acc.id
                return res

        # 2. Check pay run context
        active_run_id = self.env.context.get('default_payslip_run_id') or (active_id if active_model == 'hr.payslip.run' else False)
        if active_run_id:
            run = self.env['hr.payslip.run'].browse(active_run_id).exists()
            if run:
                res['payslip_run_id'] = run.id
                if 'report_name' in fields_list and not res.get('report_name'):
                    res['report_name'] = f"Payment Advice - {run.name}"
                company = run.company_id or self.env.company
                bank_acc = company.partner_id.bank_ids and company.partner_id.bank_ids[0] or False
                if not bank_acc:
                    bank_acc = self.env['res.partner.bank'].search([('company_id', '=', company.id)], limit=1)
                if bank_acc and 'company_bank_id' in fields_list:
                    res['company_bank_id'] = bank_acc.id
        return res

    def _ensure_payment_advice(self):
        """Creates or updates the payment advice with current run's or payslip's lines."""
        self.ensure_one()
        if self.payslip_id:
            slips_to_include = self.payslip_id
        elif self.payslip_run_id:
            run = self.payslip_run_id
            if not run.slip_ids:
                raise UserError(_("No payslips found in this pay run to process payment."))
            slips_to_include = run.slip_ids
            if not self.include_unpaid:
                slips_to_include = slips_to_include.filtered(lambda s: not getattr(s, 'paid', False))
        else:
            raise UserError(_("No payslip or pay run specified to process payment."))

        # Validation: Verify all included employees have a bank account configured
        slips_missing_bank = slips_to_include.filtered(lambda s: not s.has_bank_account)
        if slips_missing_bank:
            emp_list = "\n • ".join(slips_missing_bank.mapped('employee_id.name'))
            raise UserError(_(
                "Payment Advice cannot be created!\n\n"
                "The following employee(s) do not have a bank account configured:\n"
                " • %(employees)s\n\n"
                "Please configure bank account details for these employee(s) before creating Payment Advice or marking as Paid."
            ) % {'employees': emp_list})

        advice = False
        if self.payslip_id and getattr(self.payslip_id, 'advice_id', False):
            advice = self.payslip_id.advice_id
        elif self.payslip_run_id and getattr(self.payslip_run_id, 'advice_id', False):
            advice = self.payslip_run_id.advice_id

        company = self.company_id or self.env.company
        note_str = f"Cheque No: {self.cheque_number or 'N/A'}, Date: {self.cheque_date or 'N/A'}" if self.by_cheque else "Processed via NEFT / Online Banking"

        if not advice:
            advice_vals = {
                'date': self.payment_date,
                'company_id': company.id,
                'company_bank_id': self.company_bank_id.id if self.company_bank_id else False,
                'note': note_str,
            }
            if self.payslip_run_id:
                advice_vals['payslip_run_id'] = self.payslip_run_id.id
            if self.payslip_id:
                advice_vals['payslip_id'] = self.payslip_id.id
            advice = self.env['hudson.payroll.payment.advice'].create(advice_vals)
            if self.payslip_run_id:
                self.payslip_run_id.advice_id = advice
            if self.payslip_id:
                self.payslip_id.advice_id = advice
        else:
            advice_vals = {
                'date': self.payment_date,
            }
            if self.company_bank_id:
                advice_vals['company_bank_id'] = self.company_bank_id.id
            if self.by_cheque:
                advice_vals['note'] = note_str
            advice.write(advice_vals)

        # Populate lines
        lines_vals = []
        for slip in slips_to_include:
            net_amt = slip.net_wage or sum(l.total for l in slip.line_ids if l.category_id.code == 'NET')
            lines_vals.append((0, 0, {
                'payslip_id': slip.id,
                'employee_id': slip.employee_id.id,
                'net_amount': net_amt,
            }))

        advice.line_ids = [(5, 0, 0)] + lines_vals
        return advice

    def action_mark_paid(self):
        """Marks payslips as paid, updates pay run state if applicable, and confirms advice."""
        self.ensure_one()
        advice = self._ensure_payment_advice()
        if self.payslip_id:
            self.payslip_id.write({'paid': True, 'state': 'paid'})
            run = self.payslip_id.payslip_run_id
            if run and all(s.state == 'paid' for s in run.slip_ids):
                run.write({'state': 'paid'})
        elif self.payslip_run_id:
            run = self.payslip_run_id
            slips = run.slip_ids
            slips.write({'paid': True})
            slips.filtered(lambda s: s.state != 'paid').write({'state': 'paid'})
            run.write({'state': 'paid'})

        advice.action_confirm()
        return {'type': 'ir.actions.act_window_close'}

    def action_create_pdf(self):
        """Generates and downloads PDF Payment Advice report."""
        self.ensure_one()
        advice = self._ensure_payment_advice()
        return self.env.ref('hudson_payroll_base.action_report_payment_advice').report_action(advice)

    def action_create_xlsx(self):
        """Generates and downloads a formatted Excel (.xlsx) file."""
        self.ensure_one()
        advice = self._ensure_payment_advice()

        if not xlsxwriter:
            # Fallback to CSV if xlsxwriter not available
            return advice.action_export_csv()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Payment Advice')

        # Styles
        fmt_title = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter', 'font_color': '#1e293b'})
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#7c3aed', 'font_color': '#ffffff', 'align': 'center', 'valign': 'vcenter', 'border': 1})
        fmt_bold = workbook.add_format({'bold': True})
        fmt_cell = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right', 'valign': 'vcenter'})
        fmt_total = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#f1f5f9', 'num_format': '#,##0.00', 'align': 'right'})

        worksheet.set_column('A:A', 8)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 26)
        worksheet.set_column('D:D', 20)
        worksheet.set_column('E:E', 22)
        worksheet.set_column('F:F', 24)
        worksheet.set_column('G:G', 16)
        worksheet.set_column('H:H', 18)

        # Title Block
        target_name = self.payslip_id.name if self.payslip_id else (self.payslip_run_id.name if self.payslip_run_id else 'Salary')
        worksheet.merge_range('A1:H1', f"BANK PAYMENT ADVICE - {target_name}", fmt_title)
        worksheet.write('A3', "Date:", fmt_bold)
        worksheet.write('B3', str(self.payment_date or advice.date or date.today()))
        worksheet.write('E3', "Disbursing Bank:", fmt_bold)
        worksheet.write('F3', advice.company_bank_id.bank_id.name if advice.company_bank_id and advice.company_bank_id.bank_id else 'N/A')

        worksheet.write('A4', "Company:", fmt_bold)
        worksheet.write('B4', self.company_id.name or '')
        worksheet.write('E4', "Account Number:", fmt_bold)
        worksheet.write('F4', advice.company_bank_id.acc_number if advice.company_bank_id else 'N/A')

        if self.by_cheque:
            worksheet.write('A5', "Cheque No:", fmt_bold)
            worksheet.write('B5', self.cheque_number or 'N/A')
            worksheet.write('C5', f"Date: {self.cheque_date or ''}")

        # Table Header
        headers = ['#', 'Emp Code', 'Employee Name', 'Department', 'Bank Name', 'Account Number', 'IFSC / Routing', 'Net Amount']
        row = 6
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, fmt_header)

        # Table Data
        row += 1
        total_net = 0.0
        for idx, line in enumerate(advice.line_ids, start=1):
            worksheet.write(row, 0, idx, fmt_cell)
            worksheet.write(row, 1, line.employee_id.registration_number or '', fmt_cell)
            worksheet.write(row, 2, line.employee_id.name or '', fmt_cell)
            worksheet.write(row, 3, line.department_id.name if line.department_id else '', fmt_cell)
            worksheet.write(row, 4, line.bank_name or '', fmt_cell)
            worksheet.write(row, 5, line.acc_number or '', fmt_cell)
            worksheet.write(row, 6, line.bank_bic or '', fmt_cell)
            worksheet.write(row, 7, line.net_amount or 0.0, fmt_num)
            total_net += (line.net_amount or 0.0)
            row += 1

        # Total Row
        worksheet.merge_range(row, 0, row, 6, "Total Disbursed", fmt_header)
        worksheet.write(row, 7, total_net, fmt_total)

        workbook.close()
        xlsx_data = output.getvalue()
        output.close()

        filename = f"Payment_Advice_{target_name.replace('/', '_').replace(' ', '_')}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(xlsx_data),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
