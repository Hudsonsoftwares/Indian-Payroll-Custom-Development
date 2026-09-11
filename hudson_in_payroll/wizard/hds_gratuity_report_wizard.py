# -*- coding: utf-8 -*-
import base64
import io
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.hudson_in_payroll.services.gratuity.gratuity_validator import GratuityValidator
from odoo.addons.hudson_in_payroll.services.gratuity.gratuity_data_service import GratuityDataService
from odoo.addons.hudson_in_payroll.services.gratuity.gratuity_calculator import GratuityCalculator

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class HdsGratuityReportWizard(models.TransientModel):
    _name = 'hds.gratuity.report.wizard'
    _description = 'Gratuity Calculation Report Wizard'

    selection_mode = fields.Selection([
        ('by_employee', 'By Employee'),
        ('by_department', 'By Department'),
        ('by_job', 'By Job Position'),
        ('by_structure', 'By Salary Structure'),
        ('by_tag', 'By Employee Tag'),
    ], string='Selection Mode', default='by_employee', required=True)

    employee_ids = fields.Many2many(
        'hr.employee',
        'hds_gratuity_wiz_emp_rel',
        'wiz_id',
        'emp_id',
        string='Employees'
    )
    department_ids = fields.Many2many(
        'hr.department',
        'hds_gratuity_wiz_dept_rel',
        'wiz_id',
        'dept_id',
        string='Departments'
    )
    job_ids = fields.Many2many(
        'hr.job',
        'hds_gratuity_wiz_job_rel',
        'wiz_id',
        'job_id',
        string='Job Positions'
    )
    structure_ids = fields.Many2many(
        'hr.payroll.structure',
        'hds_gratuity_wiz_struct_rel',
        'wiz_id',
        'struct_id',
        string='Salary Structures'
    )
    category_ids = fields.Many2many(
        'hr.employee.category',
        'hds_gratuity_wiz_cat_rel',
        'wiz_id',
        'cat_id',
        string='Employee Tags'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    xlsx_file = fields.Binary(string='Gratuity Excel File (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    def _get_target_employees(self):
        self.ensure_one()
        domain = [('company_id', '=', self.company_id.id)]

        if self.selection_mode == 'by_employee':
            if self.employee_ids:
                return self.employee_ids
        elif self.selection_mode == 'by_department':
            if self.department_ids:
                domain.append(('department_id', 'in', self.department_ids.ids))
        elif self.selection_mode == 'by_job':
            if self.job_ids:
                domain.append(('job_id', 'in', self.job_ids.ids))
        elif self.selection_mode == 'by_structure':
            if self.structure_ids:
                contract_model = 'hr.version' if 'hr.version' in self.env else ('hr.contract' if 'hr.contract' in self.env else False)
                contracts = self.env[contract_model].search([
                    ('struct_id', 'in', self.structure_ids.ids)
                ]) if contract_model else False
                if contracts:
                    domain.append(('id', 'in', contracts.mapped('employee_id').ids))
        elif self.selection_mode == 'by_tag':
            if self.category_ids:
                domain.append(('category_ids', 'in', self.category_ids.ids))

        return self.env['hr.employee'].search(domain)

    def _get_gratuity_data(self):
        self.ensure_one()
        employees = self._get_target_employees()

        if not employees:
            raise UserError(_("No active employees found matching the selected scope criteria."))

        validator = GratuityValidator(self.env)
        data_service = GratuityDataService(self.env)
        calculator = GratuityCalculator()

        eval_date = fields.Date.today()
        gratuity_rows = []

        tot_wage_base = 0.0
        tot_raw_gratuity = 0.0
        tot_final_gratuity = 0.0

        contract_model = 'hr.version' if 'hr.version' in self.env else ('hr.contract' if 'hr.contract' in self.env else False)

        for emp in employees:
            emp_code = getattr(emp, 'registration_number', False) or getattr(emp, 'barcode', False) or str(emp.id)
            emp_name = emp.name or ''
            dept_name = emp.department_id.name if emp.department_id else ''
            job_name = emp.job_id.name if emp.job_id else ''

            joining_date = getattr(emp, 'hds_in_gratuity_joining_date', False) or getattr(emp, 'first_contract_date', False) or (emp.create_date.date() if emp.create_date else fields.Date.today())

            contract = getattr(emp, 'contract_id', False) or (self.env[contract_model].search([('employee_id', '=', emp.id)], limit=1) if contract_model else False)

            val_res = validator.validate(
                employee=emp,
                contract=contract,
                calc_date=eval_date
            )

            calc_data = data_service.prepare_calculation_data(
                employee=emp,
                contract=contract,
                separation_date=eval_date,
                calc_date=eval_date
            )

            calc_res = calculator.calculate(calc_data)

            gratuity_rows.append({
                'emp_code': emp_code,
                'emp_name': emp_name,
                'department': dept_name,
                'job': job_name,
                'joining_date': str(joining_date) if joining_date else '',
                'completed_years': calc_data.completed_years,
                'wage_base': round(calc_data.wage_base, 2),
                'status': 'Eligible' if val_res.is_eligible else 'Not Eligible',
                'raw_gratuity': round(calc_res.raw_gratuity_amount, 2),
                'final_gratuity': round(calc_res.final_gratuity_amount, 2),
            })

            tot_wage_base += calc_data.wage_base
            tot_raw_gratuity += calc_res.raw_gratuity_amount
            tot_final_gratuity += calc_res.final_gratuity_amount

        mode_label = dict(self._fields['selection_mode'].selection).get(self.selection_mode, '')

        return {
            'gratuity_rows': gratuity_rows,
            'tot_wage_base': round(tot_wage_base, 2),
            'tot_raw_gratuity': round(tot_raw_gratuity, 2),
            'tot_final_gratuity': round(tot_final_gratuity, 2),
            'mode_label': mode_label,
            'record_count': len(gratuity_rows),
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('hudson_in_payroll.action_report_gratuity').report_action(self)

    def action_export_xlsx(self):
        self.ensure_one()
        data = self._get_gratuity_data()
        gratuity_rows = data['gratuity_rows']
        tot_wage_base = data['tot_wage_base']
        tot_raw_gratuity = data['tot_raw_gratuity']
        tot_final_gratuity = data['tot_final_gratuity']
        mode_label = data['mode_label']

        today_str = fields.Date.today().strftime('%d_%b_%Y')
        xlsx_filename = f"Gratuity_Calculation_Report_{today_str}.xlsx"

        output = io.BytesIO()
        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Gratuity Calculation')

            title_fmt = workbook.add_format({'bold': True, 'font_size': 14})
            sub_title_fmt = workbook.add_format({'font_size': 10, 'italic': True, 'font_color': '#555555'})
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
            text_fmt = workbook.add_format({'border': 1})
            status_elig_fmt = workbook.add_format({'border': 1, 'bold': True, 'font_color': '#1E4620', 'bg_color': '#D4EDDA', 'align': 'center'})
            status_not_fmt = workbook.add_format({'border': 1, 'font_color': '#856404', 'bg_color': '#FFF3CD', 'align': 'center'})
            total_fmt = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'bg_color': '#D9E1F2', 'border': 1})

            sheet.write(0, 0, f"GRATUITY CALCULATION REPORT — {self.company_id.name}", title_fmt)
            mode_label = dict(self._fields['selection_mode'].selection).get(self.selection_mode, '')
            sheet.write(1, 0, f"Scope Mode: {mode_label} | Total Employees: {len(gratuity_rows)} | Date: {fields.Date.today()}", sub_title_fmt)

            headers = [
                'Employee ID', 'Employee Name', 'Department', 'Job Position',
                'Date of Joining', 'Service Tenure (Years)', 'Last Drawn Basic + DA (₹)',
                'Eligibility Status', 'Calculated Gratuity (₹)', 'Payable Gratuity (Capped ₹20L ₹)'
            ]
            for col_idx, text in enumerate(headers):
                sheet.write(3, col_idx, text, header_fmt)

            for row_idx, r in enumerate(gratuity_rows, start=4):
                sheet.write(row_idx, 0, r['emp_code'], text_fmt)
                sheet.write(row_idx, 1, r['emp_name'], text_fmt)
                sheet.write(row_idx, 2, r['department'], text_fmt)
                sheet.write(row_idx, 3, r['job'], text_fmt)
                sheet.write(row_idx, 4, r['joining_date'], text_fmt)
                sheet.write(row_idx, 5, r['completed_years'], text_fmt)
                sheet.write(row_idx, 6, r['wage_base'], num_fmt)

                s_fmt = status_elig_fmt if r['status'] == 'Eligible' else status_not_fmt
                sheet.write(row_idx, 7, r['status'], s_fmt)
                sheet.write(row_idx, 8, r['raw_gratuity'], num_fmt)
                sheet.write(row_idx, 9, r['final_gratuity'], num_fmt)

            tot_row = len(gratuity_rows) + 4
            sheet.write(tot_row, 0, "TOTAL", total_fmt)
            for c in range(1, 6):
                sheet.write(tot_row, c, "", total_fmt)
            sheet.write(tot_row, 6, round(tot_wage_base, 2), total_fmt)
            sheet.write(tot_row, 7, "", total_fmt)
            sheet.write(tot_row, 8, round(tot_raw_gratuity, 2), total_fmt)
            sheet.write(tot_row, 9, round(tot_final_gratuity, 2), total_fmt)

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
