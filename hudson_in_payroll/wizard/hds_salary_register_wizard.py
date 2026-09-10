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


class HdsSalaryRegisterWizard(models.TransientModel):
    _name = 'hds.salary.register.wizard'
    _description = 'Salary Register Report Wizard'

    date_from = fields.Date(
        string='Start Date',
        default=lambda self: date(fields.Date.today().year, fields.Date.today().month, 1),
        required=True
    )
    date_to = fields.Date(
        string='End Date',
        default=fields.Date.today,
        required=True
    )

    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Pay Structure',
        help='Optional pay structure filter.'
    )

    payslip_state = fields.Selection([
        ('done', 'Done'),
        ('paid', 'Paid'),
        ('all', 'Done & Paid'),
    ], string='Payslip Status', default='all', required=True)

    employee_ids = fields.Many2many(
        'hr.employee',
        'hds_salary_register_wizard_employee_rel',
        'wizard_id',
        'employee_id',
        string='Employees',
        help='Optional employee filter. Leave empty to include all matching employees.'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    xlsx_file = fields.Binary(string='Salary Register Excel File (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    def _get_target_payslips(self):
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
        ]

        if self.payslip_state == 'done':
            domain.append(('state', '=', 'done'))
        elif self.payslip_state == 'paid':
            domain.append(('state', '=', 'paid'))
        else:
            domain.append(('state', 'in', ('done', 'paid')))

        if self.struct_id:
            domain.append(('struct_id', '=', self.struct_id.id))

        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))

        return self.env['hr.payslip'].search(domain, order='date_to desc, employee_id asc')

    def action_export_xlsx(self):
        self.ensure_one()
        payslips = self._get_target_payslips()

        if not payslips:
            raise UserError(_("No confirmed or paid payslips found for the selected period and criteria."))

        rows = []
        tot_basic = 0.0
        tot_hra = 0.0
        tot_alw = 0.0
        tot_other_earn = 0.0
        tot_gross = 0.0

        tot_pf_ee = 0.0
        tot_esi_ee = 0.0
        tot_pt = 0.0
        tot_lwf_ee = 0.0
        tot_other_ded = 0.0
        tot_tds = 0.0
        tot_total_ded = 0.0

        tot_pf_er = 0.0
        tot_esi_er = 0.0
        tot_lwf_er = 0.0
        tot_other_er = 0.0
        tot_total_er = 0.0

        tot_net = 0.0
        tot_cost = 0.0

        for slip in payslips:
            emp = slip.employee_id
            emp_ref = getattr(emp, 'registration_number', False) or getattr(emp, 'emp_id', False) or f"EMP{emp.id:04d}"
            emp_name = emp.name or ''
            dept_name = emp.department_id.name if emp.department_id else ''
            job_name = emp.job_id.name if emp.job_id else ''
            slip_num = slip.number or slip.name or ''

            month_label = slip.date_to.strftime('%B %Y') if slip.date_to else ''

            lines = slip.line_ids

            # 1. Earnings Breakdown
            basic_val = 0.0
            hra_val = 0.0
            alw_val = 0.0
            other_earn_val = 0.0

            for line in lines:
                code = (line.code or '').upper()
                cat_code = (line.category_id.code or '').upper() if line.category_id else ''
                amt = float(line.total or 0.0)

                if code == 'BASIC' or cat_code == 'BASIC':
                    basic_val += amt
                elif code == 'HRA':
                    hra_val += amt
                elif cat_code == 'ALW':
                    alw_val += amt
                elif cat_code in ('GROSS', 'NET', 'DED', 'COMP'):
                    continue
                else:
                    # Other earnings (e.g. Bonus, Incentives)
                    if amt > 0:
                        other_earn_val += amt

            gross_val = float(getattr(slip, 'gross_amount', None) or getattr(slip, 'gross_wage', 0.0) or 0.0)
            if gross_val <= 0:
                gross_val = basic_val + hra_val + alw_val + other_earn_val

            # 2. Employee Deductions Breakdown
            pf_ee_val = 0.0
            esi_ee_val = 0.0
            pt_val = 0.0
            lwf_ee_val = 0.0
            tds_val = 0.0
            other_ded_val = 0.0

            for line in lines:
                code = (line.code or '').upper()
                cat_code = (line.category_id.code or '').upper() if line.category_id else ''
                amt = abs(float(line.total or 0.0))

                if cat_code == 'COMP':
                    continue

                if code in ('PF', 'EPF', 'EE_PF') or (cat_code == 'DED' and 'PF' in code):
                    pf_ee_val += amt
                elif code in ('ESI', 'ESIC', 'EE_ESI') or (cat_code == 'DED' and 'ESI' in code):
                    esi_ee_val += amt
                elif code in ('PT', 'PROF_TAX', 'PT_DED') or (cat_code == 'DED' and 'PT' in code):
                    pt_val += amt
                elif code in ('LWF', 'LWF_EE', 'EE_LWF') or (cat_code == 'DED' and 'LWF' in code):
                    lwf_ee_val += amt
                elif code in ('TDS', 'INCOME_TAX', 'IT') or cat_code == 'TDS':
                    tds_val += amt
                elif cat_code == 'DED':
                    other_ded_val += amt

            total_ded_val = pf_ee_val + esi_ee_val + pt_val + lwf_ee_val + tds_val + other_ded_val

            # 3. Employer Contributions Breakdown
            pf_er_val = 0.0
            esi_er_val = 0.0
            lwf_er_val = 0.0
            other_er_val = 0.0

            for line in lines:
                code = (line.code or '').upper()
                cat_code = (line.category_id.code or '').upper() if line.category_id else ''
                amt = abs(float(line.total or 0.0))

                if cat_code == 'COMP':
                    if any(k in code for k in ('PF', 'EPS', 'EDLI', 'ER_PF', 'EMPR_PF')):
                        pf_er_val += amt
                    elif any(k in code for k in ('ESI', 'ER_ESI', 'EMPR_ESI')):
                        esi_er_val += amt
                    elif any(k in code for k in ('LWF', 'ER_LWF', 'EMPR_LWF')):
                        lwf_er_val += amt
                    else:
                        other_er_val += amt

            total_er_val = pf_er_val + esi_er_val + lwf_er_val + other_er_val

            # 4. Final Values
            net_val = float(getattr(slip, 'net_amount', None) or getattr(slip, 'net_wage', 0.0) or 0.0)
            if net_val <= 0:
                net_val = gross_val - total_ded_val

            emp_cost_val = gross_val + total_er_val

            rows.append({
                'emp_ref': emp_ref,
                'emp_name': emp_name,
                'department': dept_name,
                'job_position': job_name,
                'payslip_num': slip_num,
                'month': month_label,
                'basic': round(basic_val, 2),
                'hra': round(hra_val, 2),
                'alw': round(alw_val, 2),
                'other_earn': round(other_earn_val, 2),
                'gross': round(gross_val, 2),
                'pf_ee': round(pf_ee_val, 2),
                'esi_ee': round(esi_ee_val, 2),
                'pt': round(pt_val, 2),
                'lwf_ee': round(lwf_ee_val, 2),
                'other_ded': round(other_ded_val, 2),
                'tds': round(tds_val, 2),
                'total_ded': round(total_ded_val, 2),
                'pf_er': round(pf_er_val, 2),
                'esi_er': round(esi_er_val, 2),
                'lwf_er': round(lwf_er_val, 2),
                'other_er': round(other_er_val, 2),
                'net': round(net_val, 2),
                'cost': round(emp_cost_val, 2),
            })

            tot_basic += basic_val
            tot_hra += hra_val
            tot_alw += alw_val
            tot_other_earn += other_earn_val
            tot_gross += gross_val

            tot_pf_ee += pf_ee_val
            tot_esi_ee += esi_ee_val
            tot_pt += pt_val
            tot_lwf_ee += lwf_ee_val
            tot_other_ded += other_ded_val
            tot_tds += tds_val
            tot_total_ded += total_ded_val

            tot_pf_er += pf_er_val
            tot_esi_er += esi_er_val
            tot_lwf_er += lwf_er_val
            tot_other_er += other_er_val
            tot_total_er += total_er_val

            tot_net += net_val
            tot_cost += emp_cost_val

        filename = f"Salary_Register_{self.date_from}_{self.date_to}.xlsx"
        output = io.BytesIO()

        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Salary Register')

            title_fmt = workbook.add_format({'bold': True, 'font_size': 14})
            sub_title_fmt = workbook.add_format({'font_size': 10, 'italic': True, 'font_color': '#555555'})

            # Category Headers formatting
            hdr_emp_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_earn_fmt = workbook.add_format({'bold': True, 'bg_color': '#2E75B6', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_ded_fmt = workbook.add_format({'bold': True, 'bg_color': '#C55A11', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_er_fmt = workbook.add_format({'bold': True, 'bg_color': '#548235', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_final_fmt = workbook.add_format({'bold': True, 'bg_color': '#70AD47', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})

            num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
            text_fmt = workbook.add_format({'border': 1})
            total_fmt = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'bg_color': '#D9E1F2', 'border': 1})
            total_text_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})

            sheet.write(0, 0, f"SALARY REGISTER REPORT — {self.company_id.name}", title_fmt)
            status_label = dict(self._fields['payslip_state'].selection).get(self.payslip_state, '')
            sheet.write(1, 0, f"Period: {self.date_from} to {self.date_to} | Status: {status_label} | Generated: {fields.Date.today()}", sub_title_fmt)

            headers = [
                ('Emp Reference', hdr_emp_fmt),
                ('Employee Name', hdr_emp_fmt),
                ('Department', hdr_emp_fmt),
                ('Job Position', hdr_emp_fmt),
                ('Payslip Number', hdr_emp_fmt),
                ('Payroll Month', hdr_emp_fmt),
                ('Basic Salary', hdr_earn_fmt),
                ('HRA', hdr_earn_fmt),
                ('Allowances', hdr_earn_fmt),
                ('Other Earnings', hdr_earn_fmt),
                ('Gross Salary', hdr_earn_fmt),
                ('PF (Employee)', hdr_ded_fmt),
                ('ESI (Employee)', hdr_ded_fmt),
                ('Professional Tax', hdr_ded_fmt),
                ('LWF (Employee)', hdr_ded_fmt),
                ('Other Deductions', hdr_ded_fmt),
                ('TDS (Income Tax)', hdr_ded_fmt),
                ('Total Deductions', hdr_ded_fmt),
                ('Employer PF', hdr_er_fmt),
                ('Employer ESI', hdr_er_fmt),
                ('Employer LWF', hdr_er_fmt),
                ('Other Employer Contrib.', hdr_er_fmt),
                ('Net Pay', hdr_final_fmt),
                ('Total Employer Cost', hdr_final_fmt),
            ]

            for col_idx, (text, fmt) in enumerate(headers):
                sheet.write(3, col_idx, text, fmt)

            for row_idx, r in enumerate(rows, start=4):
                sheet.write(row_idx, 0, r['emp_ref'], text_fmt)
                sheet.write(row_idx, 1, r['emp_name'], text_fmt)
                sheet.write(row_idx, 2, r['department'], text_fmt)
                sheet.write(row_idx, 3, r['job_position'], text_fmt)
                sheet.write(row_idx, 4, r['payslip_num'], text_fmt)
                sheet.write(row_idx, 5, r['month'], text_fmt)
                sheet.write(row_idx, 6, r['basic'], num_fmt)
                sheet.write(row_idx, 7, r['hra'], num_fmt)
                sheet.write(row_idx, 8, r['alw'], num_fmt)
                sheet.write(row_idx, 9, r['other_earn'], num_fmt)
                sheet.write(row_idx, 10, r['gross'], num_fmt)
                sheet.write(row_idx, 11, r['pf_ee'], num_fmt)
                sheet.write(row_idx, 12, r['esi_ee'], num_fmt)
                sheet.write(row_idx, 13, r['pt'], num_fmt)
                sheet.write(row_idx, 14, r['lwf_ee'], num_fmt)
                sheet.write(row_idx, 15, r['other_ded'], num_fmt)
                sheet.write(row_idx, 16, r['tds'], num_fmt)
                sheet.write(row_idx, 17, r['total_ded'], num_fmt)
                sheet.write(row_idx, 18, r['pf_er'], num_fmt)
                sheet.write(row_idx, 19, r['esi_er'], num_fmt)
                sheet.write(row_idx, 20, r['lwf_er'], num_fmt)
                sheet.write(row_idx, 21, r['other_er'], num_fmt)
                sheet.write(row_idx, 22, r['net'], num_fmt)
                sheet.write(row_idx, 23, r['cost'], num_fmt)

            tot_row = len(rows) + 4
            sheet.write(tot_row, 0, "TOTAL", total_text_fmt)
            for c in range(1, 6):
                sheet.write(tot_row, c, "", total_text_fmt)

            totals_data = [
                (6, round(tot_basic, 2)),
                (7, round(tot_hra, 2)),
                (8, round(tot_alw, 2)),
                (9, round(tot_other_earn, 2)),
                (10, round(tot_gross, 2)),
                (11, round(tot_pf_ee, 2)),
                (12, round(tot_esi_ee, 2)),
                (13, round(tot_pt, 2)),
                (14, round(tot_lwf_ee, 2)),
                (15, round(tot_other_ded, 2)),
                (16, round(tot_tds, 2)),
                (17, round(tot_total_ded, 2)),
                (18, round(tot_pf_er, 2)),
                (19, round(tot_esi_er, 2)),
                (20, round(tot_lwf_er, 2)),
                (21, round(tot_other_er, 2)),
                (22, round(tot_net, 2)),
                (23, round(tot_cost, 2)),
            ]
            for col_idx, val in totals_data:
                sheet.write(tot_row, col_idx, val, total_fmt)

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
