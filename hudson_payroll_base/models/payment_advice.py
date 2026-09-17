import base64
import csv
import io
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


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
    payment_method = fields.Selection([
        ('enet_rtgs', 'ENet RTGS'),
        ('enet_neft', 'ENet NEFT'),
        ('enet_fund_transfer', 'ENet Fund Transfer'),
        ('enet_demand_draft', 'ENet Demand Draft'),
        ('enet_intra', 'ENet Intra'),
    ], string='Payment Method', default='enet_rtgs')
    enet_transaction_type = fields.Selection([
        ('auto', 'Auto (Smart Route: IFT / RTGS / NEFT)'),
        ('ift', 'IFT (Internal Fund Transfer - Within HDFC)'),
        ('neft', 'NEFT (Inter-Bank)'),
        ('rtgs', 'RTGS (High Value >= 2 Lakhs)'),
        ('imps', 'IMPS (Immediate Payment Service)'),
    ], string='ENet Transaction Type', default='auto')
    enet_client_code = fields.Char(string='Corporate / Client Code')
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

    @staticmethod
    def _get_employee_code(emp):
        """Safely extracts employee code across standard and custom employee models."""
        if not emp:
            return ''
        return (
            getattr(emp, 'registration_number', False)
            or getattr(emp, 'barcode', False)
            or getattr(emp, 'identification_id', False)
            or getattr(emp, 'biometric_code', False)
            or str(emp.id)
        )

    def action_export_csv(self):
        """Generates a bank-ready generic CSV disbursement statement and returns a download action."""
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
                self._get_employee_code(line.employee_id),
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

    def _get_enet_transaction_type(self, line, chosen_mode=None):
        """Evaluates ENet transaction type based on payment_method or explicit transaction type."""
        mode = chosen_mode or self.payment_method or self.enet_transaction_type or 'enet_rtgs'
        tx_map = {
            'enet_rtgs': 'RTGS',
            'enet_neft': 'NEFT',
            'enet_fund_transfer': 'FT',
            'enet_demand_draft': 'DD',
            'enet_intra': 'INTRA',
        }
        if mode in tx_map:
            return tx_map[mode]
        elif mode and mode.upper() in ('RTGS', 'NEFT', 'FT', 'DD', 'INTRA', 'IFT', 'IMPS'):
            return mode.upper()

        emp_bic = (line.bank_bic or '').strip().upper()
        co_bic = (self.company_bank_id.bank_id.bic or '').strip().upper() if (self.company_bank_id and self.company_bank_id.bank_id) else ''

        # Smart Routing: Within HDFC or same bank BIC prefix -> INTRA
        if emp_bic.startswith('HDFC') or (co_bic and emp_bic.startswith(co_bic[:4])):
            return 'INTRA'
        # Inter-bank high-value >= 2 Lakhs -> RTGS
        elif (line.net_amount or 0.0) >= 200000.0:
            return 'RTGS'
        # Standard inter-bank -> NEFT
        else:
            return 'NEFT'

    def action_export_enet(self, payment_method=None, enet_tx_type=None, narration=None):
        """Generates HDFC ENet CMS formatted bulk salary upload CSV file."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No payment advice lines found to export."))

        mode_tx = payment_method or enet_tx_type or self.payment_method or self.enet_transaction_type or 'enet_rtgs'
        debit_acc = self.company_bank_id.acc_number if self.company_bank_id else ''
        val_date_str = (self.date or date.today()).strftime('%d/%m/%Y')
        default_narr = narration or self.note or f"Salary {self.date.strftime('%b %Y') if self.date else ''}"
        clean_narr = default_narr.replace(',', '').replace('\n', ' ').strip()[:30]

        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Standard HDFC ENet CMS Header
        writer.writerow([
            'Transaction Type',
            'Beneficiary Account Number',
            'Amount',
            'Beneficiary Name',
            'Drawee IFSC Code',
            'Customer Reference Number',
            'Debit Account Number',
            'Value Date',
            'Beneficiary Email ID',
            'Beneficiary Mobile Number',
            'Payment Remarks',
        ])

        for idx, line in enumerate(self.line_ids, start=1):
            tx_code = self._get_enet_transaction_type(line, chosen_mode=mode_tx)
            emp = line.employee_id
            emp_name = (emp.name or '').replace(',', '').strip()
            cust_ref = f"SAL{self.id}_{self._get_employee_code(emp)}_{idx}"[:20]
            email = emp.work_email or ''
            mobile = emp.mobile_phone or emp.work_phone or ''

            writer.writerow([
                tx_code,
                line.acc_number or '',
                f"{line.net_amount:.2f}",
                emp_name,
                line.bank_bic or '',
                cust_ref,
                debit_acc,
                val_date_str,
                email,
                mobile,
                clean_narr,
            ])

        csv_content = output.getvalue().encode('utf-8-sig')
        output.close()

        filename = f"ENet_Salary_Upload_{self.name.replace('/', '_')}.csv"
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

    def action_export_xlsx(self):
        """Generates and downloads a formatted Excel (.xlsx) file."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No payment advice lines found to export."))

        if not xlsxwriter:
            return self.action_export_csv()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Payment Advice')

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

        target_name = self.payslip_id.name if self.payslip_id else (self.payslip_run_id.name if self.payslip_run_id else self.name)
        worksheet.merge_range('A1:H1', f"BANK PAYMENT ADVICE - {target_name}", fmt_title)
        worksheet.write('A3', "Date:", fmt_bold)
        worksheet.write('B3', str(self.date or date.today()))
        worksheet.write('E3', "Disbursing Bank:", fmt_bold)
        worksheet.write('F3', self.company_bank_id.bank_id.name if self.company_bank_id and self.company_bank_id.bank_id else 'N/A')

        worksheet.write('A4', "Company:", fmt_bold)
        worksheet.write('B4', self.company_id.name or '')
        worksheet.write('E4', "Account Number:", fmt_bold)
        worksheet.write('F4', self.company_bank_id.acc_number if self.company_bank_id else 'N/A')

        headers = ['#', 'Emp Code', 'Employee Name', 'Department', 'Bank Name', 'Account Number', 'IFSC / Routing', 'Net Amount']
        row = 6
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, fmt_header)

        row += 1
        total_net = 0.0
        for idx, line in enumerate(self.line_ids, start=1):
            worksheet.write(row, 0, idx, fmt_cell)
            worksheet.write(row, 1, self._get_employee_code(line.employee_id), fmt_cell)
            worksheet.write(row, 2, line.employee_id.name or '', fmt_cell)
            worksheet.write(row, 3, line.department_id.name if line.department_id else '', fmt_cell)
            worksheet.write(row, 4, line.bank_name or '', fmt_cell)
            worksheet.write(row, 5, line.acc_number or '', fmt_cell)
            worksheet.write(row, 6, line.bank_bic or '', fmt_cell)
            worksheet.write(row, 7, line.net_amount or 0.0, fmt_num)
            total_net += (line.net_amount or 0.0)
            row += 1

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
        store=True,
        readonly=False
    )
    acc_number = fields.Char(
        string='Account Number',
        compute='_compute_bank_details',
        store=True,
        readonly=False
    )
    bank_bic = fields.Char(
        string='IFSC / BIC / Routing',
        compute='_compute_bank_details',
        store=True,
        readonly=False
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
            bank_name = bank_acc.bank_id.name if bank_acc and bank_acc.bank_id else (bank_acc.acc_holder_name if bank_acc else '')
            line.bank_name = bank_name or line.bank_name or ''
            line.acc_number = (bank_acc.acc_number if bank_acc else '') or line.acc_number or ''
            bic = ''
            if bank_acc:
                bic = (bank_acc.bank_id.bic if bank_acc.bank_id else '') or getattr(bank_acc, 'routing_number', '') or getattr(bank_acc, 'bank_bic', '') or ''
            line.bank_bic = bic or line.bank_bic or ''
            line.has_bank_account = bool(line.acc_number)
