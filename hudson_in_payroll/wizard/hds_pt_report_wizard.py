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


class HdsPtReportWizard(models.TransientModel):
    """
    Unified Professional Tax (PT) Report Wizard.
    Modeled in the exact same format and structure as the ESIC and Labour Statutory Report Wizards.
    Provides monthly/periodic selection, multi-company and state filtering, Excel export, and live summary statistics.
    """
    _name = 'hds.pt.report.wizard'
    _description = 'Professional Tax (PT) Report Wizard'

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
        ('pt_report', 'Professional Tax Register'),
        ('pt_summary', 'Monthly PT Summary'),
        ('pt_state_summary', 'State-wise PT Summary'),
    ], string='Report Type', default='pt_report', required=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    state_id = fields.Many2one(
        'res.country.state',
        string='Work State',
        domain="[('country_id.code', '=', 'IN')]",
        help="Optional state filter (e.g. Maharashtra, Karnataka, West Bengal)"
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee Filter',
        help="Optional employee filter"
    )

    name = fields.Char(string='Report Name', compute='_compute_name', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
    ], string='State', default='draft')

    xlsx_file = fields.Binary(string='PT Excel File (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    record_count = fields.Integer(string='Total Employees Covered', readonly=True)
    total_pt_wages = fields.Float(string='Total Gross / PT Wages', readonly=True)
    total_pt_deduction = fields.Float(string='Total PT Deductions', readonly=True)

    @api.depends('month', 'year', 'report_type', 'state_id')
    def _compute_name(self):
        month_dict = dict(self._fields['month'].selection)
        report_dict = dict(self._fields['report_type'].selection)
        for rec in self:
            m_label = month_dict.get(rec.month, '')
            r_label = report_dict.get(rec.report_type, 'PT Report')
            state_label = f" ({rec.state_id.code or rec.state_id.name})" if rec.state_id else ""
            rec.name = f"{r_label}{state_label} / {m_label}-{rec.year}"

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

    def _get_employee_state_name(self, emp, contract=None):
        """Resolves employee work state cleanly from contract, work location, or employee profile."""
        if contract and hasattr(contract, 'hds_in_work_state_id') and contract.hds_in_work_state_id:
            return contract.hds_in_work_state_id.name or contract.hds_in_work_state_id.code or ''
        if emp.work_location_id and emp.work_location_id.address_id and emp.work_location_id.address_id.state_id:
            return emp.work_location_id.address_id.state_id.name or ''
        if emp.company_id and emp.company_id.state_id:
            return emp.company_id.state_id.name or ''
        return 'Not Specified'

    def action_generate_xlsx(self):
        self.ensure_one()
        date_from, date_to = self._get_date_range()

        domain = [
            ('state', '=', 'done'),
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
        ]
        if self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))

        payslips = self.env['hr.payslip'].search(domain)

        # Filter payslips where employee or contract matches state_id if state_id is selected
        if self.state_id:
            filtered_payslips = self.env['hr.payslip']
            for p in payslips:
                emp_state = getattr(p.contract_id, 'hds_in_work_state_id', False) or (
                    p.employee_id.work_location_id.address_id.state_id if (p.employee_id.work_location_id and p.employee_id.work_location_id.address_id) else False
                ) or p.company_id.state_id
                if emp_state and emp_state.id == self.state_id.id:
                    filtered_payslips |= p
            payslips = filtered_payslips

        if not payslips:
            raise UserError(_("No confirmed payslips found for the selected period (%s) matching criteria.") % self._get_month_label())

        # Pre-export statutory PT compliance validation
        from odoo.addons.hudson_in_payroll.services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        compliance_service = StatutoryComplianceValidationService(self.env)
        compliance_service.validate_scope_compliance(
            employees=payslips.mapped('employee_id'),
            statutory_type='pt',
            report_title='Professional Tax Report'
        )

        pt_rows = []
        tot_wages = 0.0
        tot_pt = 0.0

        for payslip in payslips:
            emp = payslip.employee_id
            lines = payslip.line_ids

            pt_lines = lines.filtered(lambda l: l.code in ('PT', 'PROF_TAX', 'PROFESSIONAL_TAX'))
            pt_amount = abs(sum(pt_lines.mapped('total'))) if pt_lines else 0.0

            gross_lines = lines.filtered(lambda l: l.code in ('PT_GROSS', 'PT_WAGE', 'GROSS'))
            gross_wage = abs(gross_lines[0].total) if gross_lines else (payslip.contract_id.wage if payslip.contract_id else 0.0)

            emp_code = emp.identification_id or getattr(emp, 'registration_number', False) or ''
            state_name = self._get_employee_state_name(emp, payslip.contract_id)

            pt_rows.append({
                'employee_code': emp_code,
                'employee_name': emp.name or '',
                'state_name': state_name,
                'department': emp.department_id.name if emp.department_id else '',
                'gross_wage': round(gross_wage, 2),
                'pt_amount': round(pt_amount, 2),
                'payslip_number': payslip.number or payslip.name or '',
            })

            tot_wages += gross_wage
            tot_pt += pt_amount

        month_label = self._get_month_label().replace(' ', '_')
        xlsx_filename = f"PT_Report_{self.report_type}_{month_label}.xlsx"

        output = io.BytesIO()
        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            header_fmt = workbook.add_format({
                'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF',
                'border': 1, 'align': 'center', 'valign': 'vcenter'
            })
            sub_fmt = workbook.add_format({
                'bold': True, 'bg_color': '#D9E1F2', 'border': 1
            })
            num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
            text_fmt = workbook.add_format({'border': 1})
            tot_fmt = workbook.add_format({
                'bold': True, 'bg_color': '#D9D9D9', 'border': 1, 'num_format': '#,##0.00'
            })
            tot_label_fmt = workbook.add_format({
                'bold': True, 'bg_color': '#D9D9D9', 'border': 1, 'align': 'center'
            })

            if self.report_type == 'pt_summary':
                sheet = workbook.add_worksheet('PT Summary')
                headers = [
                    'Establishment / Company', 'Reporting Period', 'Total Employees Covered',
                    'Total Gross / PT Wages', 'Total PT Deductions'
                ]
                for col_idx, text in enumerate(headers):
                    sheet.write(0, col_idx, text, header_fmt)

                sheet.write(1, 0, self.company_id.name or '', text_fmt)
                sheet.write(1, 1, self._get_month_label(), text_fmt)
                sheet.write(1, 2, len(pt_rows), text_fmt)
                sheet.write(1, 3, round(tot_wages, 2), num_fmt)
                sheet.write(1, 4, round(tot_pt, 2), num_fmt)

                sheet.set_column('A:A', 30)
                sheet.set_column('B:E', 22)

            elif self.report_type == 'pt_state_summary':
                sheet = workbook.add_worksheet('State-wise PT Summary')
                headers = ['Work State', 'Employee Count', 'Total Gross Wages', 'Total PT Deductions']
                for col_idx, text in enumerate(headers):
                    sheet.write(0, col_idx, text, header_fmt)

                # Group by state
                state_groups = {}
                for r in pt_rows:
                    st = r['state_name']
                    if st not in state_groups:
                        state_groups[st] = {'count': 0, 'wages': 0.0, 'pt': 0.0}
                    state_groups[st]['count'] += 1
                    state_groups[st]['wages'] += r['gross_wage']
                    state_groups[st]['pt'] += r['pt_amount']

                row_idx = 1
                for st, data in sorted(state_groups.items()):
                    sheet.write(row_idx, 0, st, text_fmt)
                    sheet.write(row_idx, 1, data['count'], text_fmt)
                    sheet.write(row_idx, 2, round(data['wages'], 2), num_fmt)
                    sheet.write(row_idx, 3, round(data['pt'], 2), num_fmt)
                    row_idx += 1

                sheet.write(row_idx, 0, 'TOTAL', tot_label_fmt)
                sheet.write(row_idx, 1, len(pt_rows), tot_label_fmt)
                sheet.write(row_idx, 2, round(tot_wages, 2), tot_fmt)
                sheet.write(row_idx, 3, round(tot_pt, 2), tot_fmt)

                sheet.set_column('A:A', 26)
                sheet.set_column('B:D', 20)

            else:
                # Default: Professional Tax Register
                sheet = workbook.add_worksheet('PT Register')
                headers = [
                    'Sr.', 'Employee ID', 'Employee Name', 'Department',
                    'Work Location / State', 'Payslip Ref', 'Gross Salary (Rs)', 'PT Deduction (Rs)'
                ]
                for col_idx, text in enumerate(headers):
                    sheet.write(0, col_idx, text, header_fmt)

                for idx, r in enumerate(pt_rows, start=1):
                    sheet.write(idx, 0, idx, text_fmt)
                    sheet.write(idx, 1, r['employee_code'], text_fmt)
                    sheet.write(idx, 2, r['employee_name'], text_fmt)
                    sheet.write(idx, 3, r['department'], text_fmt)
                    sheet.write(idx, 4, r['state_name'], text_fmt)
                    sheet.write(idx, 5, r['payslip_number'], text_fmt)
                    sheet.write(idx, 6, r['gross_wage'], num_fmt)
                    sheet.write(idx, 7, r['pt_amount'], num_fmt)

                last_row = len(pt_rows) + 1
                sheet.write(last_row, 0, 'TOTAL', tot_label_fmt)
                sheet.write(last_row, 1, '', tot_label_fmt)
                sheet.write(last_row, 2, '', tot_label_fmt)
                sheet.write(last_row, 3, '', tot_label_fmt)
                sheet.write(last_row, 4, '', tot_label_fmt)
                sheet.write(last_row, 5, '', tot_label_fmt)
                sheet.write(last_row, 6, round(tot_wages, 2), tot_fmt)
                sheet.write(last_row, 7, round(tot_pt, 2), tot_fmt)

                sheet.set_column('A:A', 6)
                sheet.set_column('B:B', 14)
                sheet.set_column('C:C', 26)
                sheet.set_column('D:D', 20)
                sheet.set_column('E:E', 22)
                sheet.set_column('F:F', 18)
                sheet.set_column('G:H', 18)

            workbook.close()
            output.seek(0)
            xlsx_content = output.read()
        else:
            xlsx_content = b"Excel export requires xlsxwriter library."

        self.write({
            'state': 'generated',
            'xlsx_file': base64.b64encode(xlsx_content),
            'xlsx_filename': xlsx_filename,
            'record_count': len(pt_rows),
            'total_pt_wages': tot_wages,
            'total_pt_deduction': tot_pt,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
