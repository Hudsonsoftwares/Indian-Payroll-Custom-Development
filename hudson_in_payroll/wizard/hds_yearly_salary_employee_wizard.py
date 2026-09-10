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


MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]


class HdsYearlySalaryEmployeeWizard(os_model := models.TransientModel):
    _name = 'hds.yearly.salary.employee.wizard'
    _description = 'Yearly Salary by Employee Wizard'

    year = fields.Selection(
        selection=lambda self: [(str(y), str(y)) for y in range(2020, 2031)],
        string='Year',
        default=lambda self: str(date.today().year),
        required=True
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department'
    )

    job_id = fields.Many2one(
        'hr.job',
        string='Job Position'
    )

    employee_ids = fields.Many2many(
        'hr.employee',
        'hds_yearly_salary_wizard_emp_rel',
        'wizard_id',
        'employee_id',
        string='Employees'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    xlsx_file = fields.Binary(string='Excel Report (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    def _get_target_employees(self):
        self.ensure_one()
        y = int(self.year)
        year_start = date(y, 1, 1)
        year_end = date(y, 12, 31)

        # 1. Find all paid/done payslips in the year for the company
        domain = [
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', year_start),
            ('date_to', '<=', year_end),
            ('state', 'in', ('done', 'paid'))
        ]
        if self.department_id:
            domain.append(('employee_id.department_id', '=', self.department_id.id))
        if self.job_id:
            domain.append(('employee_id.job_id', '=', self.job_id.id))

        payslips = self.env['hr.payslip'].search(domain)
        paid_emp_ids = payslips.mapped('employee_id').ids

        if not paid_emp_ids:
            return self.env['hr.employee']

        # 2. Filter target employees
        if self.employee_ids:
            target_ids = list(set(self.employee_ids.ids).intersection(paid_emp_ids))
            return self.env['hr.employee'].browse(target_ids)
        else:
            return self.env['hr.employee'].browse(paid_emp_ids)

    def action_print_xlsx(self):
        self.ensure_one()
        employees = self._get_target_employees()

        if not employees:
            raise UserError(_("No paid payslips found for the selected criteria in %s.") % self.year)

        y = int(self.year)
        filename = f"Yearly_Salary_by_Employee_{self.year}.xlsx"
        output = io.BytesIO()

        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})

            # Formatting styles
            title_fmt = workbook.add_format({'bold': True, 'font_size': 14})
            sub_title_fmt = workbook.add_format({'font_size': 10, 'italic': True, 'font_color': '#555555'})

            hdr_main_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_month_fmt = workbook.add_format({'bold': True, 'bg_color': '#2E75B6', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_tot_fmt = workbook.add_format({'bold': True, 'bg_color': '#70AD47', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_ded_fmt = workbook.add_format({'bold': True, 'bg_color': '#C55A11', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})

            num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
            text_fmt = workbook.add_format({'border': 1})
            total_fmt = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'bg_color': '#D9E1F2', 'border': 1})
            total_text_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})

            # SHEET 1: Yearly Summary Matrix
            sheet_sum = workbook.add_worksheet('Yearly Summary')
            sheet_sum.write(0, 0, f"YEARLY SALARY SUMMARY BY EMPLOYEE — {self.year}", title_fmt)
            sheet_sum.write(1, 0, f"Company: {self.company_id.name} | Generated: {fields.Date.today()}", sub_title_fmt)

            sum_headers = ['Emp Ref', 'Employee Name', 'Department', 'Job Position'] + MONTH_NAMES + ['Annual Gross', 'Annual Deductions', 'Annual Net Pay', 'Annual CTC']
            for col_idx, h_text in enumerate(sum_headers):
                fmt = hdr_main_fmt if col_idx < 4 else (hdr_tot_fmt if col_idx >= 16 else hdr_month_fmt)
                sheet_sum.write(3, col_idx, h_text, fmt)

            sum_row = 4
            annual_totals = [0.0] * 16  # 12 months Net + 4 annual totals

            # Data structure for detailed employee sheets
            emp_data_map = {}

            for emp in employees:
                emp_ref = getattr(emp, 'registration_number', False) or getattr(emp, 'emp_id', False) or f"EMP{emp.id:04d}"

                sheet_sum.write(sum_row, 0, emp_ref, text_fmt)
                sheet_sum.write(sum_row, 1, emp.name or '', text_fmt)
                sheet_sum.write(sum_row, 2, emp.department_id.name if emp.department_id else '', text_fmt)
                sheet_sum.write(sum_row, 3, emp.job_id.name if emp.job_id else '', text_fmt)

                emp_months = {}
                ann_gross = 0.0
                ann_ded = 0.0
                ann_net = 0.0
                ann_ctc = 0.0

                for m in range(1, 13):
                    m_start = date(y, m, 1)
                    m_end = date(y, m, calendar.monthrange(y, m)[1])

                    slips = self.env['hr.payslip'].search([
                        ('employee_id', '=', emp.id),
                        ('company_id', '=', self.company_id.id),
                        ('date_from', '>=', m_start),
                        ('date_to', '<=', m_end),
                        ('state', 'in', ('done', 'paid'))
                    ])

                    if not slips:
                        sheet_sum.write(sum_row, 3 + m, 0.0, num_fmt)
                        emp_months[m] = False
                        continue

                    # Consolidate slips for the month
                    struct_name = slips[0].struct_id.name if slips[0].struct_id else ''
                    basic_v = 0.0
                    hra_v = 0.0
                    alw_v = 0.0
                    other_earn_v = 0.0

                    pf_ee_v = 0.0
                    esi_ee_v = 0.0
                    pt_v = 0.0
                    lwf_ee_v = 0.0
                    tds_v = 0.0
                    other_ded_v = 0.0

                    pf_er_v = 0.0
                    esi_er_v = 0.0
                    lwf_er_v = 0.0
                    other_er_v = 0.0

                    for slip in slips:
                        for line in slip.line_ids:
                            code = (line.code or '').upper()
                            cat_code = (line.category_id.code or '').upper() if line.category_id else ''
                            amt = abs(float(line.total or 0.0))

                            if cat_code == 'BASIC' or code == 'BASIC':
                                basic_v += float(line.total or 0.0)
                            elif code == 'HRA':
                                hra_v += float(line.total or 0.0)
                            elif cat_code == 'ALW':
                                alw_v += float(line.total or 0.0)
                            elif cat_code == 'DED':
                                if code in ('PF', 'EPF', 'EE_PF') or 'PF' in code:
                                    pf_ee_v += amt
                                elif code in ('ESI', 'ESIC', 'EE_ESI') or 'ESI' in code:
                                    esi_ee_v += amt
                                elif code in ('PT', 'PROF_TAX', 'PT_DED') or 'PT' in code:
                                    pt_v += amt
                                elif code in ('LWF', 'LWF_EE', 'EE_LWF') or 'LWF' in code:
                                    lwf_ee_v += amt
                                elif code in ('TDS', 'INCOME_TAX', 'IT'):
                                    tds_v += amt
                                else:
                                    other_ded_v += amt
                            elif cat_code == 'TDS':
                                tds_v += amt
                            elif cat_code == 'COMP':
                                if any(k in code for k in ('PF', 'EPS', 'EDLI', 'ER_PF', 'EMPR_PF')):
                                    pf_er_v += amt
                                elif any(k in code for k in ('ESI', 'ER_ESI', 'EMPR_ESI')):
                                    esi_er_v += amt
                                elif any(k in code for k in ('LWF', 'ER_LWF', 'EMPR_LWF')):
                                    lwf_er_v += amt
                                else:
                                    other_er_v += amt
                            elif cat_code not in ('GROSS', 'NET') and float(line.total or 0.0) > 0:
                                other_earn_v += float(line.total or 0.0)

                    gross_v = sum(float(getattr(s, 'gross_amount', None) or getattr(s, 'gross_wage', 0.0) or 0.0) for s in slips)
                    if gross_v <= 0:
                        gross_v = basic_v + hra_v + alw_v + other_earn_v

                    tot_ded_v = pf_ee_v + esi_ee_v + pt_v + lwf_ee_v + tds_v + other_ded_v

                    net_v = sum(float(getattr(s, 'net_amount', None) or getattr(s, 'net_wage', 0.0) or 0.0) for s in slips)
                    if net_v <= 0:
                        net_v = gross_v - tot_ded_v

                    tot_er_v = pf_er_v + esi_er_v + lwf_er_v + other_er_v
                    ctc_v = gross_v + tot_er_v

                    sheet_sum.write(sum_row, 3 + m, round(net_v, 2), num_fmt)
                    annual_totals[m - 1] += net_v

                    ann_gross += gross_v
                    ann_ded += tot_ded_v
                    ann_net += net_v
                    ann_ctc += ctc_v

                    emp_months[m] = {
                        'struct_name': struct_name,
                        'basic': round(basic_v, 2),
                        'hra': round(hra_v, 2),
                        'allowances': round(alw_v, 2),
                        'other_earnings': round(other_earn_v, 2),
                        'gross': round(gross_v, 2),
                        'pf_ee': round(pf_ee_v, 2),
                        'esi_ee': round(esi_ee_v, 2),
                        'pt': round(pt_v, 2),
                        'lwf_ee': round(lwf_ee_v, 2),
                        'tds': round(tds_v, 2),
                        'other_deductions': round(other_ded_v, 2),
                        'total_deductions': round(tot_ded_v, 2),
                        'net_pay': round(net_v, 2),
                        'pf_er': round(pf_er_v, 2),
                        'esi_er': round(esi_er_v, 2),
                        'lwf_er': round(lwf_er_v, 2),
                        'other_er_contrib': round(other_er_v, 2),
                        'total_employer_cost': round(ctc_v, 2),
                    }

                sheet_sum.write(sum_row, 16, round(ann_gross, 2), num_fmt)
                sheet_sum.write(sum_row, 17, round(ann_ded, 2), num_fmt)
                sheet_sum.write(sum_row, 18, round(ann_net, 2), num_fmt)
                sheet_sum.write(sum_row, 19, round(ann_ctc, 2), num_fmt)

                annual_totals[12] += ann_gross
                annual_totals[13] += ann_ded
                annual_totals[14] += ann_net
                annual_totals[15] += ann_ctc

                emp_data_map[emp.id] = (emp, emp_ref, emp_months, ann_gross, ann_ded, ann_net, ann_ctc)
                sum_row += 1

            # Total row on Summary sheet
            sheet_sum.write(sum_row, 0, "TOTAL", total_text_fmt)
            for c in range(1, 4):
                sheet_sum.write(sum_row, c, "", total_text_fmt)
            for c in range(16):
                sheet_sum.write(sum_row, 4 + c, round(annual_totals[c], 2), total_fmt)

            # SHEET 2: Month-by-Month Component Breakdown Details
            sheet_dtl = workbook.add_worksheet('Detailed Breakdown')
            sheet_dtl.write(0, 0, f"YEARLY SALARY DETAILED BREAKDOWN — {self.year}", title_fmt)

            dtl_headers = [
                'Emp Ref', 'Employee Name', 'Department', 'Month', 'Salary Structure',
                'Basic', 'HRA', 'Allowances', 'Other Earnings', 'Gross Salary',
                'EE PF', 'EE ESI', 'PT', 'LWF', 'TDS', 'Other Ded.', 'Total Deductions',
                'Net Pay', 'ER PF', 'ER ESI', 'ER LWF', 'Other ER', 'Total CTC'
            ]
            for col_idx, h_text in enumerate(dtl_headers):
                fmt = hdr_main_fmt if col_idx < 5 else (hdr_ded_fmt if 10 <= col_idx <= 16 else (hdr_tot_fmt if col_idx in (9, 17, 22) else hdr_month_fmt))
                sheet_dtl.write(2, col_idx, h_text, fmt)

            d_row = 3
            for emp_id, (emp, emp_ref, emp_months, ag, ad, an, ac) in emp_data_map.items():
                for m_idx, m_name in enumerate(MONTH_NAMES, start=1):
                    m_data = emp_months.get(m_idx)
                    if not m_data:
                        continue

                    sheet_dtl.write(d_row, 0, emp_ref, text_fmt)
                    sheet_dtl.write(d_row, 1, emp.name or '', text_fmt)
                    sheet_dtl.write(d_row, 2, emp.department_id.name if emp.department_id else '', text_fmt)
                    sheet_dtl.write(d_row, 3, m_name, text_fmt)
                    sheet_dtl.write(d_row, 4, m_data['struct_name'], text_fmt)

                    sheet_dtl.write(d_row, 5, m_data['basic'], num_fmt)
                    sheet_dtl.write(d_row, 6, m_data['hra'], num_fmt)
                    sheet_dtl.write(d_row, 7, m_data['allowances'], num_fmt)
                    sheet_dtl.write(d_row, 8, m_data['other_earnings'], num_fmt)
                    sheet_dtl.write(d_row, 9, m_data['gross'], num_fmt)

                    sheet_dtl.write(d_row, 10, m_data['pf_ee'], num_fmt)
                    sheet_dtl.write(d_row, 11, m_data['esi_ee'], num_fmt)
                    sheet_dtl.write(d_row, 12, m_data['pt'], num_fmt)
                    sheet_dtl.write(d_row, 13, m_data['lwf_ee'], num_fmt)
                    sheet_dtl.write(d_row, 14, m_data['tds'], num_fmt)
                    sheet_dtl.write(d_row, 15, m_data['other_deductions'], num_fmt)
                    sheet_dtl.write(d_row, 16, m_data['total_deductions'], num_fmt)

                    sheet_dtl.write(d_row, 17, m_data['net_pay'], num_fmt)

                    sheet_dtl.write(d_row, 18, m_data['pf_er'], num_fmt)
                    sheet_dtl.write(d_row, 19, m_data['esi_er'], num_fmt)
                    sheet_dtl.write(d_row, 20, m_data['lwf_er'], num_fmt)
                    sheet_dtl.write(d_row, 21, m_data['other_er_contrib'], num_fmt)
                    sheet_dtl.write(d_row, 22, m_data['total_employer_cost'], num_fmt)

                    d_row += 1

            workbook.close()
            output.seek(0)
            xlsx_content = output.read()
        else:
            xlsx_content = b"Excel export requires xlsxwriter library."

        self.write({
            'xlsx_file': base64.b64encode(xlsx_content),
            'xlsx_filename': filename,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=xlsx_file&filename_field=xlsx_filename&download=true',
            'target': 'self',
        }
