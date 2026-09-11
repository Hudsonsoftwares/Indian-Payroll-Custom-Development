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


MONTH_SELECTION = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
    ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
    ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
]


class HdsSalaryStatementReport(models.Model):
    _name = 'hds.salary.statement.report'
    _description = 'Salary Statement Report'
    _order = 'year desc, month desc, id desc'

    name = fields.Char(
        string='Description',
        compute='_compute_name',
        store=True,
        readonly=False,
        required=True
    )

    year = fields.Selection(
        selection=lambda self: [(str(y), str(y)) for y in range(2020, 2031)],
        string='Year',
        default=lambda self: str(date.today().year),
        required=True
    )

    month = fields.Selection(
        selection=MONTH_SELECTION,
        string='Month',
        default=lambda self: str(date.today().month),
        required=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    payslip_state = fields.Selection([
        ('paid', 'Paid'),
        ('confirmed', 'Confirmed & Paid (Done, Paid)'),
        ('done', 'Done'),
        ('all', 'All States (Draft, Verify, Done, Paid)'),
    ], string='Payslip Status Filter', default='paid', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Populated'),
    ], string='Status', default='draft', required=True)

    line_ids = fields.One2many(
        'hds.salary.statement.line',
        'statement_id',
        string='Salary Statement Lines'
    )

    employee_count = fields.Integer(
        string='Eligible Employees Count',
        compute='_compute_employee_count',
        store=True
    )

    xlsx_file = fields.Binary(string='Excel Report (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    @api.depends('year', 'month')
    def _compute_name(self):
        month_dict = dict(MONTH_SELECTION)
        for rec in self:
            m_label = month_dict.get(str(rec.month), '')
            y_label = rec.year or ''
            if m_label and y_label:
                rec.name = f"Salary Statement - {m_label}, {y_label}"
            elif not rec.name:
                rec.name = "Salary Statement"

    @api.model_create_multi
    def create(self, vals_list):
        month_dict = dict(MONTH_SELECTION)
        for vals in vals_list:
            if not vals.get('name'):
                m = month_dict.get(str(vals.get('month', date.today().month)), '')
                y = vals.get('year', str(date.today().year))
                vals['name'] = f"Salary Statement - {m}, {y}" if m and y else "Salary Statement"
        return super().create(vals_list)

    @api.depends('line_ids', 'line_ids.employee_id')
    def _compute_employee_count(self):
        for rec in self:
            rec.employee_count = len(rec.line_ids.mapped('employee_id'))

    def action_populate(self):
        self.ensure_one()
        y = int(self.year)
        m = int(self.month)

        month_start = date(y, m, 1)
        month_end = date(y, m, calendar.monthrange(y, m)[1])

        # Search matching payslips for company and period based on payslip_state
        domain = [
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', month_start),
            ('date_to', '<=', month_end),
            ('state', '!=', 'cancel'),
        ]
        if self.payslip_state == 'done':
            domain.append(('state', '=', 'done'))
        elif self.payslip_state == 'paid':
            domain.append(('state', '=', 'paid'))
        elif self.payslip_state == 'confirmed':
            domain.append(('state', 'in', ('done', 'paid')))

        payslips = self.env['hr.payslip'].search(domain, order='employee_id asc, date_to desc, id desc')

        # Deduplicate per employee: pick the best slip per employee (paid > done > verify > draft, and latest id)
        state_prio = {'paid': 4, 'done': 3, 'verify': 2, 'draft': 1}
        emp_slips = {}
        for slip in payslips:
            if not slip.line_ids:
                continue
            emp_id = slip.employee_id.id
            if emp_id not in emp_slips:
                emp_slips[emp_id] = slip
            else:
                existing = emp_slips[emp_id]
                prio_new = (state_prio.get(slip.state, 0), slip.id)
                prio_old = (state_prio.get(existing.state, 0), existing.id)
                if prio_new > prio_old:
                    emp_slips[emp_id] = slip

        valid_slips = list(emp_slips.values())
        if not valid_slips:
            raise UserError(_("No computed payslips found for %s, %s matching the selected criteria.") % (dict(MONTH_SELECTION).get(str(self.month)), self.year))

        self.line_ids.unlink()

        month_label = f"{dict(MONTH_SELECTION).get(str(self.month))} {self.year}"

        for slip in valid_slips:
            emp = slip.employee_id
            emp_ref = getattr(emp, 'registration_number', False) or getattr(emp, 'emp_id', False) or f"EMP{emp.id:04d}"

            # Compute working days / paid days from worked_days_line_ids or default
            working_days = 0.0
            if slip.worked_days_line_ids:
                working_days = sum(float(w.number_of_days or 0.0) for w in slip.worked_days_line_ids if (w.code or '').upper() not in ('UNPAID', 'ABSENT', 'SHORTAGE', 'LEAVE_UNPAID'))
            if working_days <= 0:
                working_days = float(calendar.monthrange(y, m)[1])

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

                # Skip non-earning categories and intermediate calculation rules explicitly
                if cat_code in ('GROSS', 'NET', 'DED', 'COMP', 'PF_CALC', 'ESIC_CALC', 'CALC') or code in ('PF_WAGE', 'ESIC_WAGE', 'BASIC_PF', 'PF_BASE', 'ESI_WAGE', 'ESIC_BASE'):
                    continue

                if code == 'BASIC' or cat_code == 'BASIC':
                    basic_val += amt
                elif code == 'HRA':
                    hra_val += amt
                elif cat_code == 'ALW':
                    alw_val += amt
                elif amt > 0:
                    other_earn_val += amt

            # Gross Salary
            gross_line = lines.filtered(lambda l: (l.code or '').upper() == 'GROSS' or (l.category_id and l.category_id.code == 'GROSS'))
            if gross_line:
                gross_val = float(gross_line[0].total or 0.0)
            else:
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

                # Skip company contributions, earnings, intermediate calculations, net/gross
                if cat_code in ('COMP', 'BASIC', 'ALW', 'GROSS', 'NET', 'PF_CALC', 'ESIC_CALC', 'CALC') or code in ('PF_WAGE', 'ESIC_WAGE', 'BASIC_PF', 'PF_BASE', 'ESI_WAGE', 'ESIC_BASE'):
                    continue

                if code in ('PF', 'EPF', 'EE_PF') or (cat_code == 'DED' and code in ('PF', 'EPF', 'EE_PF')):
                    pf_ee_val += amt
                elif code in ('ESI', 'ESIC', 'EE_ESI', 'ESIC_EE') or (cat_code == 'DED' and code in ('ESI', 'ESIC', 'EE_ESI', 'ESIC_EE')):
                    esi_ee_val += amt
                elif code in ('PT', 'PROF_TAX', 'PT_DED') or (cat_code == 'DED' and 'PT' in code):
                    pt_val += amt
                elif code in ('LWF', 'LWF_EE', 'EE_LWF') or (cat_code == 'DED' and 'LWF' in code):
                    lwf_ee_val += amt
                elif code in ('TDS', 'HDS_IN_TDS', 'INCOME_TAX', 'IT') or 'TDS' in code or cat_code == 'TDS':
                    tds_val += amt
                elif cat_code == 'DED':
                    other_ded_val += amt

            total_ded_val = pf_ee_val + esi_ee_val + pt_val + lwf_ee_val + tds_val + other_ded_val

            # 3. Net Pay
            net_line = lines.filtered(lambda l: (l.code or '').upper() == 'NET' or (l.category_id and l.category_id.code == 'NET'))
            if net_line:
                net_val = float(net_line[0].total or 0.0)
            else:
                net_val = float(getattr(slip, 'net_amount', None) or getattr(slip, 'net_wage', 0.0) or 0.0)
                if net_val <= 0:
                    net_val = gross_val - total_ded_val

            # 4. Employer Contributions & Rates Breakdown
            comp_lines = lines.filtered(lambda l: l.category_id and l.category_id.code == 'COMP')
            comp_map = { (l.code or '').upper(): abs(float(l.total or 0.0)) for l in comp_lines }

            # Statutory EPF:
            # EMPLOYER_EPF = 12% (EPS 8.33% + EPF_SHARE 3.67%).
            # Avoid double-counting: if EMPLOYER_EPF is present, use it as total base.
            # Otherwise, sum EPS and EPF_SHARE.
            pf_er_eps = comp_map.get('EPS', 0.0)
            pf_er_share = comp_map.get('EPF_SHARE', 0.0)
            if 'EMPLOYER_EPF' in comp_map:
                pf_er_base = comp_map['EMPLOYER_EPF']
            elif pf_er_eps or pf_er_share:
                pf_er_base = pf_er_eps + pf_er_share
            else:
                pf_er_base = comp_map.get('ER_PF', 0.0) or comp_map.get('PF_ER', 0.0) or comp_map.get('EMPR_PF', 0.0)

            if pf_er_base > 0 and pf_er_eps == 0.0 and pf_er_share == 0.0:
                pf_er_eps = round(min(pf_er_base / 0.12, 15000.0) * 0.0833, 2)
                pf_er_share = round(pf_er_base - pf_er_eps, 2)

            pf_er_admin = (
                comp_map.get('EDLI', 0.0) +
                comp_map.get('EPF_ADMIN', 0.0) +
                comp_map.get('EDLI_ADMIN', 0.0) +
                comp_map.get('EDLI_ADMIN_CHARGE', 0.0) +
                comp_map.get('EPF_ADMIN_CHARGE', 0.0)
            )
            pf_er_val = pf_er_base + pf_er_admin

            # Employer ESI (Statutory 3.25%)
            esi_er_val = comp_map.get('ESIC_ER', 0.0) or comp_map.get('ESI_ER', 0.0) or comp_map.get('ER_ESI', 0.0)

            # Employer LWF
            lwf_er_val = comp_map.get('LWF_ER', 0.0) or comp_map.get('ER_LWF', 0.0)

            # Other Employer Contributions
            accounted_codes = {
                'EMPLOYER_EPF', 'EPS', 'EPF_SHARE', 'EDLI', 'EPF_ADMIN', 'EDLI_ADMIN',
                'EDLI_ADMIN_CHARGE', 'EPF_ADMIN_CHARGE',
                'ER_PF', 'PF_ER', 'EMPR_PF', 'ESIC_ER', 'ESI_ER', 'ER_ESI', 'LWF_ER', 'ER_LWF'
            }
            other_er_val = sum(amt for code, amt in comp_map.items() if code not in accounted_codes)

            total_er_val = pf_er_val + esi_er_val + lwf_er_val + other_er_val
            emp_cost_val = gross_val + total_er_val

            self.env['hds.salary.statement.line'].create({
                'statement_id': self.id,
                'employee_id': emp.id,
                'emp_ref': emp_ref,
                'department_id': emp.department_id.id if emp.department_id else False,
                'job_id': emp.job_id.id if emp.job_id else False,
                'payslip_id': slip.id,
                'payroll_month': month_label,
                'working_days': round(working_days, 1),
                'basic': round(basic_val, 2),
                'hra': round(hra_val, 2),
                'allowances': round(alw_val, 2),
                'other_earnings': round(other_earn_val, 2),
                'gross': round(gross_val, 2),
                'pf_ee': round(pf_ee_val, 2),
                'esi_ee': round(esi_ee_val, 2),
                'pt': round(pt_val, 2),
                'lwf_ee': round(lwf_ee_val, 2),
                'tds': round(tds_val, 2),
                'other_deductions': round(other_ded_val, 2),
                'total_deductions': round(total_ded_val, 2),
                'net_pay': round(net_val, 2),
                'pf_er_eps': round(pf_er_eps, 2),
                'pf_er_share': round(pf_er_share, 2),
                'pf_er_admin': round(pf_er_admin, 2),
                'pf_er': round(pf_er_val, 2),
                'esi_er': round(esi_er_val, 2),
                'lwf_er': round(lwf_er_val, 2),
                'other_er_contrib': round(other_er_val, 2),
                'total_employer_cost': round(emp_cost_val, 2),
            })

        self.state = 'done'
        return True

    def action_export_xlsx(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_populate()

        if not self.line_ids:
            raise UserError(_("No salary statement lines available to export."))

        filename = f"Salary_Statement_{dict(MONTH_SELECTION).get(str(self.month))}_{self.year}.xlsx"
        output = io.BytesIO()

        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Salary Statement')

            title_fmt = workbook.add_format({'bold': True, 'font_size': 14})
            sub_title_fmt = workbook.add_format({'font_size': 10, 'italic': True, 'font_color': '#555555'})

            hdr_emp_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_earn_fmt = workbook.add_format({'bold': True, 'bg_color': '#2E75B6', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_ded_fmt = workbook.add_format({'bold': True, 'bg_color': '#C55A11', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_er_fmt = workbook.add_format({'bold': True, 'bg_color': '#548235', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            hdr_final_fmt = workbook.add_format({'bold': True, 'bg_color': '#70AD47', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})

            num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
            days_fmt = workbook.add_format({'num_format': '0.0', 'border': 1, 'align': 'center'})
            text_fmt = workbook.add_format({'border': 1})
            total_fmt = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'bg_color': '#D9E1F2', 'border': 1})
            total_text_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})

            sheet.write(0, 0, f"SALARY STATEMENT REPORT — {self.company_id.name}", title_fmt)
            sheet.write(1, 0, f"{self.name} | Period: {dict(MONTH_SELECTION).get(str(self.month))} {self.year} | Generated: {fields.Date.today()}", sub_title_fmt)

            headers = [
                ('Employee ID / Ref', hdr_emp_fmt),
                ('Employee Name', hdr_emp_fmt),
                ('Department', hdr_emp_fmt),
                ('Job Position', hdr_emp_fmt),
                ('Payroll Month', hdr_emp_fmt),
                ('Paid Days', hdr_emp_fmt),
                ('Basic Salary', hdr_earn_fmt),
                ('HRA', hdr_earn_fmt),
                ('Allowances', hdr_earn_fmt),
                ('Other Earnings', hdr_earn_fmt),
                ('Gross Salary', hdr_earn_fmt),
                ('Employee PF', hdr_ded_fmt),
                ('Employee ESI', hdr_ded_fmt),
                ('Professional Tax', hdr_ded_fmt),
                ('LWF', hdr_ded_fmt),
                ('TDS', hdr_ded_fmt),
                ('Other Deductions', hdr_ded_fmt),
                ('Total Deductions', hdr_ded_fmt),
                ('Net Pay', hdr_final_fmt),
                ('Employer EPS (8.33%)', hdr_er_fmt),
                ('Employer EPF Share (3.67%)', hdr_er_fmt),
                ('EPF Admin & EDLI (1.0%)', hdr_er_fmt),
                ('Total Employer PF', hdr_er_fmt),
                ('Employer ESI (3.25%)', hdr_er_fmt),
                ('Employer LWF', hdr_er_fmt),
                ('Other Employer Contrib.', hdr_er_fmt),
                ('Total Employer Cost (CTC)', hdr_final_fmt),
            ]

            for col_idx, (text, fmt) in enumerate(headers):
                sheet.write(3, col_idx, text, fmt)

            tot_days = 0.0
            tot_basic = 0.0
            tot_hra = 0.0
            tot_alw = 0.0
            tot_other_earn = 0.0
            tot_gross = 0.0

            tot_pf_ee = 0.0
            tot_esi_ee = 0.0
            tot_pt = 0.0
            tot_lwf_ee = 0.0
            tot_tds = 0.0
            tot_other_ded = 0.0
            tot_total_ded = 0.0

            tot_net = 0.0

            tot_pf_eps = 0.0
            tot_pf_share = 0.0
            tot_pf_admin = 0.0
            tot_pf_er = 0.0
            tot_esi_er = 0.0
            tot_lwf_er = 0.0
            tot_other_er = 0.0
            tot_total_cost = 0.0

            for row_idx, line in enumerate(self.line_ids, start=4):
                sheet.write(row_idx, 0, line.emp_ref or '', text_fmt)
                sheet.write(row_idx, 1, line.employee_id.name or '', text_fmt)
                sheet.write(row_idx, 2, line.department_id.name if line.department_id else '', text_fmt)
                sheet.write(row_idx, 3, line.job_id.name if line.job_id else '', text_fmt)
                sheet.write(row_idx, 4, line.payroll_month or '', text_fmt)
                sheet.write(row_idx, 5, line.working_days, days_fmt)

                sheet.write(row_idx, 6, line.basic, num_fmt)
                sheet.write(row_idx, 7, line.hra, num_fmt)
                sheet.write(row_idx, 8, line.allowances, num_fmt)
                sheet.write(row_idx, 9, line.other_earnings, num_fmt)
                sheet.write(row_idx, 10, line.gross, num_fmt)

                sheet.write(row_idx, 11, line.pf_ee, num_fmt)
                sheet.write(row_idx, 12, line.esi_ee, num_fmt)
                sheet.write(row_idx, 13, line.pt, num_fmt)
                sheet.write(row_idx, 14, line.lwf_ee, num_fmt)
                sheet.write(row_idx, 15, line.tds, num_fmt)
                sheet.write(row_idx, 16, line.other_deductions, num_fmt)
                sheet.write(row_idx, 17, line.total_deductions, num_fmt)

                sheet.write(row_idx, 18, line.net_pay, num_fmt)

                sheet.write(row_idx, 19, line.pf_er_eps, num_fmt)
                sheet.write(row_idx, 20, line.pf_er_share, num_fmt)
                sheet.write(row_idx, 21, line.pf_er_admin, num_fmt)
                sheet.write(row_idx, 22, line.pf_er, num_fmt)
                sheet.write(row_idx, 23, line.esi_er, num_fmt)
                sheet.write(row_idx, 24, line.lwf_er, num_fmt)
                sheet.write(row_idx, 25, line.other_er_contrib, num_fmt)
                sheet.write(row_idx, 26, line.total_employer_cost, num_fmt)

                tot_days += line.working_days
                tot_basic += line.basic
                tot_hra += line.hra
                tot_alw += line.allowances
                tot_other_earn += line.other_earnings
                tot_gross += line.gross

                tot_pf_ee += line.pf_ee
                tot_esi_ee += line.esi_ee
                tot_pt += line.pt
                tot_lwf_ee += line.lwf_ee
                tot_tds += line.tds
                tot_other_ded += line.other_deductions
                tot_total_ded += line.total_deductions

                tot_net += line.net_pay

                tot_pf_eps += line.pf_er_eps
                tot_pf_share += line.pf_er_share
                tot_pf_admin += line.pf_er_admin
                tot_pf_er += line.pf_er
                tot_esi_er += line.esi_er
                tot_lwf_er += line.lwf_er
                tot_other_er += line.other_er_contrib
                tot_total_cost += line.total_employer_cost

            tot_row = len(self.line_ids) + 4
            sheet.write(tot_row, 0, "TOTAL", total_text_fmt)
            sheet.write(tot_row, 1, f"{len(self.line_ids)} Employees", total_text_fmt)
            for c in range(2, 5):
                sheet.write(tot_row, c, "", total_text_fmt)
            sheet.write(tot_row, 5, tot_days, total_fmt)
            sheet.write(tot_row, 6, tot_basic, total_fmt)
            sheet.write(tot_row, 7, tot_hra, total_fmt)
            sheet.write(tot_row, 8, tot_alw, total_fmt)
            sheet.write(tot_row, 9, tot_other_earn, total_fmt)
            sheet.write(tot_row, 10, tot_gross, total_fmt)
            sheet.write(tot_row, 11, tot_pf_ee, total_fmt)
            sheet.write(tot_row, 12, tot_esi_ee, total_fmt)
            sheet.write(tot_row, 13, tot_pt, total_fmt)
            sheet.write(tot_row, 14, tot_lwf_ee, total_fmt)
            sheet.write(tot_row, 15, tot_tds, total_fmt)
            sheet.write(tot_row, 16, tot_other_ded, total_fmt)
            sheet.write(tot_row, 17, tot_total_ded, total_fmt)
            sheet.write(tot_row, 18, tot_net, total_fmt)
            sheet.write(tot_row, 19, tot_pf_eps, total_fmt)
            sheet.write(tot_row, 20, tot_pf_share, total_fmt)
            sheet.write(tot_row, 21, tot_pf_admin, total_fmt)
            sheet.write(tot_row, 22, tot_pf_er, total_fmt)
            sheet.write(tot_row, 23, tot_esi_er, total_fmt)
            sheet.write(tot_row, 24, tot_lwf_er, total_fmt)
            sheet.write(tot_row, 25, tot_other_er, total_fmt)
            sheet.write(tot_row, 26, tot_total_cost, total_fmt)
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

    def action_print_pdf(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_populate()
        if not self.line_ids:
            raise UserError(_("No salary statement lines available to print."))
        return self.env.ref('hudson_in_payroll.action_report_salary_statement').report_action(self)

    def action_view_employees(self):
        self.ensure_one()
        emp_ids = self.line_ids.mapped('employee_id').ids
        return {
            'name': _('Eligible Employees'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', emp_ids)],
            'target': 'current',
        }

    def action_reset_to_draft(self):
        self.ensure_one()
        self.state = 'draft'
        return True


class HdsSalaryStatementLine(models.Model):
    _name = 'hds.salary.statement.line'
    _description = 'Salary Statement Report Line Item'
    _order = 'id asc'

    statement_id = fields.Many2one(
        'hds.salary.statement.report',
        string='Statement Header',
        ondelete='cascade',
        required=True
    )

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    emp_ref = fields.Char(string='Employee ID / Reference')
    department_id = fields.Many2one('hr.department', string='Department')
    job_id = fields.Many2one('hr.job', string='Job Position')

    payslip_id = fields.Many2one('hr.payslip', string='Payslip')
    payroll_month = fields.Char(string='Payroll Month')
    working_days = fields.Float(string='Paid Days / Working Days')

    # Earnings
    basic = fields.Monetary(string='Basic Salary')
    hra = fields.Monetary(string='HRA')
    allowances = fields.Monetary(string='Allowances')
    other_earnings = fields.Monetary(string='Other Earnings')
    gross = fields.Monetary(string='Gross Salary')

    # Employee Deductions
    pf_ee = fields.Monetary(string='Employee PF')
    esi_ee = fields.Monetary(string='Employee ESI')
    pt = fields.Monetary(string='Professional Tax')
    lwf_ee = fields.Monetary(string='LWF')
    tds = fields.Monetary(string='TDS')
    other_deductions = fields.Monetary(string='Other Deductions')
    total_deductions = fields.Monetary(string='Total Deductions')

    # Net Pay
    net_pay = fields.Monetary(string='Net Pay')

    # Employer Contributions
    pf_er_eps = fields.Monetary(string='Employer EPS (8.33%)')
    pf_er_share = fields.Monetary(string='Employer EPF Share (3.67%)')
    pf_er_admin = fields.Monetary(string='EPF Admin & EDLI (1.0%)')
    pf_er = fields.Monetary(string='Employer PF (12% + Admin)')
    esi_er = fields.Monetary(string='Employer ESI (3.25%)')
    lwf_er = fields.Monetary(string='Employer LWF')
    other_er_contrib = fields.Monetary(string='Other Employer Contributions')
    total_employer_cost = fields.Monetary(string='Total Employer Cost (CTC)')

    currency_id = fields.Many2one(
        'res.currency',
        related='statement_id.company_id.currency_id',
        readonly=True
    )
