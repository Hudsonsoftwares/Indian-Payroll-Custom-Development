# -*- coding: utf-8 -*-
base64_import = True
import base64
import calendar
import io
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.hudson_in_payroll.services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
from odoo.addons.hudson_in_payroll.services.lwf.lwf_service import LWFService

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class HdsLwfReportWizard(models.TransientModel):
    _name = 'hds.lwf.report.wizard'
    _description = 'Labour Welfare Fund (LWF) Report Wizard'

    date_from = fields.Date(
        string='From Date',
        default=lambda self: date(fields.Date.today().year, 1, 1),
        required=True
    )
    date_to = fields.Date(
        string='To Date',
        default=lambda self: date(fields.Date.today().year, 12, 31),
        required=True
    )

    @api.onchange('date_from')
    def _onchange_date_from(self):
        if self.date_from:
            last_day = calendar.monthrange(self.date_from.year, self.date_from.month)[1]
            self.date_to = self.date_from.replace(day=last_day)

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help='Optional department filter. If left empty, all applicable employees are included.'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    xlsx_file = fields.Binary(string='LWF Report Excel File (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    def _get_target_employees(self):
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('hds_in_lwf_applicable', '=', True),
            ('active', '=', True)
        ]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))

        return self.env['hr.employee'].search(domain)

    def action_export_xlsx(self):
        self.ensure_one()
        employees = self._get_target_employees()

        if not employees:
            raise UserError(_("No active LWF-applicable employees found matching the selected criteria."))

        # Pre-export statutory LWF compliance validation
        compliance_service = StatutoryComplianceValidationService(self.env)
        compliance_service.validate_scope_compliance(
            employees=employees,
            statutory_type='lwf',
            report_title='Labour Welfare Fund (LWF) Report'
        )

        lwf_service = LWFService(self.env)
        lwf_rows = []

        tot_ee_contrib = 0.0
        tot_er_contrib = 0.0
        tot_total_contrib = 0.0

        for emp in employees:
            lwf_no = getattr(emp, 'hds_in_lwf_number', False) or ''
            emp_name = emp.name or ''
            dept_name = emp.department_id.name if emp.department_id else ''

            state_rec = False
            if emp.work_location_id:
                state_rec = getattr(emp.work_location_id, 'state_id', False) or getattr(getattr(emp.work_location_id, 'address_id', None), 'state_id', False)
            if not state_rec and self.company_id:
                state_rec = getattr(self.company_id, 'state_id', False) or getattr(getattr(self.company_id, 'partner_id', None), 'state_id', False)

            state_name = state_rec.name if state_rec else ''

            # Find confirmed payslips within the date range
            payslips = self.env['hr.payslip'].search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'done'),
                ('date_from', '>=', self.date_from),
                ('date_to', '<=', self.date_to)
            ])

            ee_contrib = 0.0
            er_contrib = 0.0

            if payslips:
                for payslip in payslips:
                    lines = payslip.line_ids
                    ee_lines = lines.filtered(lambda l: l.code in ('LWF_EE', 'LWF'))
                    er_lines = lines.filtered(lambda l: l.code in ('LWF_ER', 'EMPR_LWF'))

                    if ee_lines:
                        ee_contrib += abs(sum(ee_lines.mapped('total')))
                    else:
                        ee_contrib += lwf_service.compute_lwf_employee(payslip)

                    if er_lines:
                        er_contrib += abs(sum(er_lines.mapped('total')))
                    else:
                        er_contrib += lwf_service.compute_lwf_employer(payslip)
            else:
                # Calculate default scheduled contribution using LWFService
                ee_contrib = lwf_service.compute_lwf_employee({'employee': emp})
                er_contrib = lwf_service.compute_lwf_employer({'employee': emp})

            total_contrib = round(ee_contrib + er_contrib, 2)

            lwf_rows.append({
                'lwf_no': lwf_no,
                'emp_name': emp_name,
                'department': dept_name,
                'state': state_name,
                'ee_contrib': round(ee_contrib, 2),
                'er_contrib': round(er_contrib, 2),
                'total_contrib': total_contrib,
                'status': 'Compliant',
            })

            tot_ee_contrib += ee_contrib
            tot_er_contrib += er_contrib
            tot_total_contrib += total_contrib

        year_str = self.date_from.strftime('%Y') if self.date_from else str(fields.Date.today().year)
        xlsx_filename = f"LWF_Report_{year_str}.xlsx"

        output = io.BytesIO()
        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('LWF Report')

            title_fmt = workbook.add_format({'bold': True, 'font_size': 14})
            sub_title_fmt = workbook.add_format({'font_size': 10, 'italic': True, 'font_color': '#555555'})
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
            text_fmt = workbook.add_format({'border': 1})
            status_fmt = workbook.add_format({'border': 1, 'bold': True, 'font_color': '#1E4620', 'bg_color': '#D4EDDA', 'align': 'center'})
            total_fmt = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'bg_color': '#D9E1F2', 'border': 1})

            dept_label = self.department_id.name if self.department_id else 'All Departments'
            sheet.write(0, 0, f"LABOUR WELFARE FUND (LWF) REPORT — {self.company_id.name}", title_fmt)
            sheet.write(1, 0, f"Period: {self.date_from} to {self.date_to} | Department: {dept_label} | Generated: {fields.Date.today()}", sub_title_fmt)

            headers = [
                'LWF Reg / Employee No', 'Employee Name', 'Department', 'Work Location State',
                'Employee Contribution (₹)', 'Employer Contribution (₹)', 'Total LWF Contribution (₹)', 'Status'
            ]
            for col_idx, text in enumerate(headers):
                sheet.write(3, col_idx, text, header_fmt)

            for row_idx, r in enumerate(lwf_rows, start=4):
                sheet.write(row_idx, 0, r['lwf_no'], text_fmt)
                sheet.write(row_idx, 1, r['emp_name'], text_fmt)
                sheet.write(row_idx, 2, r['department'], text_fmt)
                sheet.write(row_idx, 3, r['state'], text_fmt)
                sheet.write(row_idx, 4, r['ee_contrib'], num_fmt)
                sheet.write(row_idx, 5, r['er_contrib'], num_fmt)
                sheet.write(row_idx, 6, r['total_contrib'], num_fmt)
                sheet.write(row_idx, 7, r['status'], status_fmt)

            tot_row = len(lwf_rows) + 4
            sheet.write(tot_row, 0, "TOTAL", total_fmt)
            for c in range(1, 4):
                sheet.write(tot_row, c, "", total_fmt)
            sheet.write(tot_row, 4, round(tot_ee_contrib, 2), total_fmt)
            sheet.write(tot_row, 5, round(tot_er_contrib, 2), total_fmt)
            sheet.write(tot_row, 6, round(tot_total_contrib, 2), total_fmt)
            sheet.write(tot_row, 7, "", total_fmt)

            workbook.close()
            output.seek(0)
            xlsx_content = output.read()
        else:
            xlsx_content = b"Excel export requires xlsxwriter library."

        self.write({
            'xlsx_file': base64.b64encode(xlsx_content),
            'xlsx_filename': xlsx_filename,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=xlsx_file&filename_field=xlsx_filename&download=true',
            'target': 'self',
        }
