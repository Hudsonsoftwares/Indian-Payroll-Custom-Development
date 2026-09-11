# -*- coding: utf-8 -*-
import base64
import calendar
import io
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class HdsEsicReportWizard(models.TransientModel):
    _name = 'hds.esic.report.wizard'
    _description = 'Employees State Insurance (ESI) Report Wizard'

    @api.model
    def _default_year(self):
        return fields.Date.today().year

    @api.model
    def _default_month(self):
        return str(fields.Date.today().month)

    year = fields.Integer(
        string='Year',
        default=_default_year,
        required=True
    )
    month = fields.Selection([
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
    ], string='Month', default=_default_month, required=True)

    report_type = fields.Selection([
        ('esic_report', 'ESIC Report'),
        ('esi_summary', 'ESI Summary'),
    ], string='Report Type', default='esic_report', required=True)

    payslip_state = fields.Selection([
        ('all', 'All States (Draft, Verify, Done, Paid)'),
        ('confirmed', 'Confirmed & Paid (Done, Paid)'),
        ('done', 'Done Only'),
        ('paid', 'Paid Only'),
    ], string='Payslip Status', default='all', required=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    name = fields.Char(string='Report Name', compute='_compute_name', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
    ], string='State', default='draft')

    xlsx_file = fields.Binary(string='ESI Excel File (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    record_count = fields.Integer(string='Total Employees Covered', readonly=True)
    total_esi_wages = fields.Float(string='Total ESI Wages', readonly=True)
    total_ee_esic = fields.Float(string='Total Employee Contribution', readonly=True)
    total_er_esic = fields.Float(string='Total Employer Contribution', readonly=True)

    @api.depends('month', 'year', 'report_type')
    def _compute_name(self):
        month_dict = dict(self._fields['month'].selection)
        report_dict = dict(self._fields['report_type'].selection)
        for rec in self:
            m_label = month_dict.get(rec.month, '')
            r_label = report_dict.get(rec.report_type, 'ESI Report')
            rec.name = f"{r_label} / {m_label}-{rec.year}"

    def _get_date_range(self):
        self.ensure_one()
        year = int(self.year)
        month = int(self.month)
        last_day = calendar.monthrange(year, month)[1]
        date_from = date(year, month, 1)
        date_to = date(year, month, last_day)
        return date_from, date_to

    def _get_month_label(self):
        self.ensure_one()
        month_dict = dict(self._fields['month'].selection)
        return f"{month_dict.get(self.month, '')} {self.year}"

    def _get_esic_data(self):
        self.ensure_one()
        date_from, date_to = self._get_date_range()

        state_sel = getattr(self, 'payslip_state', 'all')
        if state_sel == 'done':
            states = ['done']
        elif state_sel == 'paid':
            states = ['paid']
        elif state_sel == 'confirmed':
            states = ['done', 'paid']
        else:
            states = ['draft', 'verify', 'done', 'paid']

        domain = [
            ('state', 'in', states),
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('employee_id.hds_in_esic_applicable', '=', True),
        ]
        all_slips = self.env['hr.payslip'].search(domain, order='date_to desc, id desc')

        priority = {'paid': 4, 'done': 3, 'verify': 2, 'draft': 1}
        best_slip_by_emp = {}
        for slip in all_slips:
            emp_id = slip.employee_id.id
            if emp_id not in best_slip_by_emp:
                best_slip_by_emp[emp_id] = slip
            else:
                curr_prio = priority.get(slip.state, 0)
                best_prio = priority.get(best_slip_by_emp[emp_id].state, 0)
                if curr_prio > best_prio:
                    best_slip_by_emp[emp_id] = slip

        payslips = self.env['hr.payslip'].browse([s.id for s in best_slip_by_emp.values()])

        if not payslips:
            raise UserError(_("No payslips found for ESIC-applicable employees in the selected period (%s).") % self._get_month_label())

        # Pre-export statutory ESIC compliance validation
        from odoo.addons.hudson_in_payroll.services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        compliance_service = StatutoryComplianceValidationService(self.env)
        compliance_service.validate_scope_compliance(
            employees=payslips.mapped('employee_id'),
            statutory_type='esic',
            report_title='ESIC Report'
        )

        esic_rows = []
        tot_wages = 0.0
        tot_ee = 0.0
        tot_er = 0.0

        for payslip in payslips:
            emp = payslip.employee_id
            lines = payslip.line_ids

            ip_number = getattr(emp, 'hds_in_esic_ip_number', False) or getattr(emp, 'esic_number', False) or ''
            emp_name = emp.name or ''

            # Calculate worked / payable days
            unpaid_lines = payslip.worked_days_line_ids.filtered(lambda l: l.code in ('UNPAID', 'ABSENT', 'LEAVE_UNPAID'))
            lop_days = sum(unpaid_lines.mapped('number_of_days')) if unpaid_lines else 0
            if getattr(payslip, 'hds_snapshot_id', False) and payslip.hds_snapshot_id.lop_days:
                lop_days = payslip.hds_snapshot_id.lop_days

            month_days = calendar.monthrange(int(self.year), int(self.month))[1]
            worked_days = max(0, int(month_days - lop_days))

            # ESI Contributable Wage
            wage_lines = lines.filtered(lambda l: l.code in ('ESIC_WAGE', 'ESI_WAGE', 'ESIC_CONTRIBUTABLE_WAGE'))
            if wage_lines:
                esi_wage = abs(wage_lines[0].total)
            else:
                gross_lines = lines.filtered(lambda l: l.code == 'GROSS')
                esi_wage = abs(gross_lines[0].total) if gross_lines else (payslip.contract_id.wage if payslip.contract_id else 0.0)

            # Employee ESI Deduction (0.75%)
            ee_lines = lines.filtered(lambda l: l.code in ('ESIC_EE', 'ESI_EE', 'EMPLOYEE_ESIC', 'ESIC_DED', 'ESI', 'ESIC'))
            if ee_lines:
                ee_contrib = abs(sum(ee_lines.mapped('total')))
            else:
                ee_contrib = round(esi_wage * 0.0075, 2) if (emp.hds_in_esic_applicable and esi_wage <= 21000.0) else 0.0

            # Employer ESI Contribution (3.25%)
            er_lines = lines.filtered(lambda l: l.code in ('ESIC_ER', 'ESI_ER', 'EMPLOYER_ESIC'))
            if er_lines:
                er_contrib = abs(sum(er_lines.mapped('total')))
            else:
                er_contrib = round(esi_wage * 0.0325, 2) if (emp.hds_in_esic_applicable and esi_wage <= 21000.0) else 0.0

            reason_code = getattr(emp, 'hds_in_esic_exit_reason', False) or ''
            tot_contrib = round(ee_contrib + er_contrib, 2)

            esic_rows.append({
                'ip_number': ip_number,
                'employee_name': emp_name,
                'number_of_days': worked_days,
                'total_monthly_wages': round(esi_wage, 2),
                'employee_contribution': round(ee_contrib, 2),
                'employer_contribution': round(er_contrib, 2),
                'total_contribution': tot_contrib,
                'reason_code': reason_code,
            })

            tot_wages += esi_wage
            tot_ee += ee_contrib
            tot_er += er_contrib

        est_code = getattr(self.company_id, 'hds_in_esic_employer_code', False) or getattr(self.company_id, 'vat', '') or ''
        return {
            'esic_rows': esic_rows,
            'tot_wages': round(tot_wages, 2),
            'tot_ee': round(tot_ee, 2),
            'tot_er': round(tot_er, 2),
            'total_payable': round(tot_ee + tot_er, 2),
            'record_count': len(esic_rows),
            'est_name': self.company_id.name or '',
            'est_code': est_code,
        }

    def action_print_pdf(self):
        self.ensure_one()
        data = self._get_esic_data()
        if not data.get('esic_rows'):
            raise UserError(_("No employee records found for the selected period (%s).") % self._get_month_label())
        return self.env.ref('hudson_in_payroll.action_report_esic').report_action(self)

    def action_generate_xlsx(self):
        self.ensure_one()
        data = self._get_esic_data()
        esic_rows = data['esic_rows']
        tot_wages = data['tot_wages']
        tot_ee = data['tot_ee']
        tot_er = data['tot_er']

        month_label = self._get_month_label().replace(' ', '_')
        if self.report_type == 'esi_summary':
            xlsx_filename = f"ESI_Summary_Report_{month_label}.xlsx"
        else:
            xlsx_filename = f"ESIC_Report_{month_label}.xlsx"

        output = io.BytesIO()
        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
            text_fmt = workbook.add_format({'border': 1})
            meta_label_fmt = workbook.add_format({'bold': True, 'font_size': 11})
            meta_val_fmt = workbook.add_format({'font_size': 11})

            if self.report_type == 'esi_summary':
                sheet = workbook.add_worksheet('ESI Summary')

                headers = [
                    'Establishment/Company', 'Reporting Month & Year', 'Total Employees Covered',
                    'Total ESI Wages', 'Total Employee Contribution', 'Total Employer Contribution', 'Total ESI Payable'
                ]
                for col_idx, text in enumerate(headers):
                    sheet.write(0, col_idx, text, header_fmt)

                total_payable = round(tot_ee + tot_er, 2)
                sheet.write(1, 0, self.company_id.name or '', text_fmt)
                sheet.write(1, 1, self._get_month_label(), text_fmt)
                sheet.write(1, 2, len(esic_rows), text_fmt)
                sheet.write(1, 3, round(tot_wages, 2), num_fmt)
                sheet.write(1, 4, round(tot_ee, 2), num_fmt)
                sheet.write(1, 5, round(tot_er, 2), num_fmt)
                sheet.write(1, 6, total_payable, num_fmt)
            else:
                sheet = workbook.add_worksheet('ESIC Report')

                headers = [
                    'IP Number / ESIC Number', 'Employee Name', 'Number of Days',
                    'Total Monthly Wages', 'Employee Contribution', 'Employer Contribution',
                    'Total Contribution', 'Reason Code'
                ]
                for col_idx, text in enumerate(headers):
                    sheet.write(0, col_idx, text, header_fmt)

                for row_idx, r in enumerate(esic_rows, start=1):
                    sheet.write(row_idx, 0, r['ip_number'], text_fmt)
                    sheet.write(row_idx, 1, r['employee_name'], text_fmt)
                    sheet.write(row_idx, 2, r['number_of_days'], text_fmt)
                    sheet.write(row_idx, 3, r['total_monthly_wages'], num_fmt)
                    sheet.write(row_idx, 4, r['employee_contribution'], num_fmt)
                    sheet.write(row_idx, 5, r['employer_contribution'], num_fmt)
                    sheet.write(row_idx, 6, r['total_contribution'], num_fmt)
                    sheet.write(row_idx, 7, r['reason_code'], text_fmt)

            workbook.close()
            output.seek(0)
            xlsx_content = output.read()
        else:
            xlsx_content = b"Excel export requires xlsxwriter library."

        self.write({
            'state': 'generated',
            'xlsx_file': base64.b64encode(xlsx_content),
            'xlsx_filename': xlsx_filename,
            'record_count': len(esic_rows),
            'total_esi_wages': tot_wages,
            'total_ee_esic': tot_ee,
            'total_er_esic': tot_er,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
