# -*- coding: utf-8 -*-
import base64
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class HdsPfEcrWizard(models.TransientModel):
    _name = 'hds.pf.ecr.wizard'
    _inherit = 'hds.pf.report.wizard.base'
    _description = 'EPFO ECR Export Wizard'

    report_type = fields.Selection([
        ('epf_report', 'EPF Report'),
        ('epf_summary', 'EPF Summary'),
    ], string='Report Type', default='epf_report', required=True)

    name = fields.Char(string='Report Name', compute='_compute_name', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
    ], string='State', default='draft')

    txt_file = fields.Binary(string='ECR Text File (.txt)', readonly=True)
    txt_filename = fields.Char(string='Text Filename', readonly=True)
    xlsx_file = fields.Binary(string='Report Excel File (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    record_count = fields.Integer(string='Total Employees', readonly=True)
    total_epf_wages = fields.Float(string='Total EPF Wages', readonly=True)
    total_epf_deduction = fields.Float(string='Total Employee EPF', readonly=True)
    total_eps_contribution = fields.Float(string='Total Employer EPS', readonly=True)
    total_epf_er_contribution = fields.Float(string='Total Employer EPF', readonly=True)

    @api.depends('month', 'year', 'report_type')
    def _compute_name(self):
        month_dict = dict(self._fields['month'].selection)
        report_dict = dict(self._fields['report_type'].selection)
        for rec in self:
            m_label = month_dict.get(rec.month, '')
            r_label = report_dict.get(rec.report_type, 'EPF Report')
            rec.name = f"{r_label} / {m_label}-{rec.year}"

    def _get_ecr_data(self):
        self.ensure_one()
        payslips = self._get_confirmed_payslips([('employee_id.hds_in_epf_applicable', '=', True)])

        if not payslips:
            raise UserError(_("No confirmed payslips found for EPF-applicable employees in the selected period (%s).") % self._get_month_label())

        # Pre-export statutory UAN compliance validation
        from odoo.addons.hudson_in_payroll.services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        compliance_service = StatutoryComplianceValidationService(self.env)
        compliance_service.validate_scope_compliance(
            employees=payslips.mapped('employee_id'),
            statutory_type='epf',
            report_title='EPF-ECR'
        )

        eps_ceiling = 15000.0
        ecr_rows = []
        summary_rows = []
        tot_wages = 0.0
        tot_ee_epf = 0.0
        tot_er_eps = 0.0
        tot_er_epf = 0.0
        tot_edli = 0.0
        tot_admin = 0.0
        tot_vpf = 0.0
        tot_overall_contrib = 0.0

        for payslip in payslips:
            emp = payslip.employee_id
            uan = emp.hds_in_uan or ''
            member_name = emp.name or ''
            emp_ref = getattr(emp, 'registration_number', False) or getattr(emp, 'barcode', False) or str(emp.id)
            acc_num = getattr(emp, 'hds_in_pf_member_id', False) or getattr(emp, 'hds_in_pf_number', False) or (emp.bank_account_id.acc_number if emp.bank_account_id else '') or ''

            pf_vals = self._get_pf_line_amounts(payslip)

            gross_line = payslip.line_ids.filtered(lambda l: l.code == 'GROSS')
            gross_wages = gross_line.total if gross_line else (payslip.contract_id.wage if payslip.contract_id else 0.0)

            epf_wages = pf_vals['pf_wage']
            eps_wages = min(epf_wages, eps_ceiling) if getattr(emp, 'hds_in_eps_applicable', True) else 0.0
            edli_wages = min(epf_wages, eps_ceiling) if getattr(emp, 'hds_in_edli_applicable', True) else 0.0

            ee_epf = pf_vals['ee_epf']
            vpf_amt = pf_vals.get('vpf', 0.0)
            er_epf = pf_vals['er_epf']
            er_eps = pf_vals['er_eps']
            edli_amt = pf_vals.get('edli', 0.0)
            admin_amt = pf_vals.get('admin', 0.0)

            ncp_days = 0
            if getattr(payslip, 'hds_snapshot_id', False):
                ncp_days = int(payslip.hds_snapshot_id.lop_days or 0)
            else:
                unpaid_lines = payslip.worked_days_line_ids.filtered(lambda l: l.code == 'UNPAID')
                ncp_days = int(sum(unpaid_lines.mapped('number_of_days')) if unpaid_lines else 0)

            refund_advances = 0

            ecr_rows.append({
                'uan': uan,
                'name': member_name,
                'gross': round(gross_wages, 2),
                'epf_wages': round(epf_wages, 2),
                'eps_wages': round(eps_wages, 2),
                'edli_wages': round(edli_wages, 2),
                'ee_epf': round(ee_epf, 2),
                'er_epf': round(er_epf, 2),
                'er_eps': round(er_eps, 2),
                'ncp_days': ncp_days,
                'refund': refund_advances,
            })

            tot_pf_amount = round(ee_epf + vpf_amt, 2)
            tot_contrib = round(ee_epf + vpf_amt + er_epf + er_eps + edli_amt + admin_amt, 2)

            summary_rows.append({
                'employee_id': emp_ref,
                'employee_name': member_name,
                'account_number': acc_num,
                'uan': uan,
                'pf_wages': round(epf_wages, 2),
                'employee_pf_amount': round(ee_epf, 2),
                'vpf_amount': round(vpf_amt, 2),
                'pf_amount': tot_pf_amount,
                'eps_amount': round(er_eps, 2),
                'edli': round(edli_amt, 2),
                'admin_charge': round(admin_amt, 2),
                'total_contribution': tot_contrib,
            })

            tot_wages += epf_wages
            tot_ee_epf += ee_epf
            tot_er_eps += er_eps
            tot_er_epf += er_epf
            tot_edli += edli_amt
            tot_admin += admin_amt
            tot_vpf += vpf_amt
            tot_overall_contrib += tot_contrib

        est_name = self.company_id.name or ''
        est_id = getattr(self.company_id, 'hds_in_epf_employer_id', False) or getattr(self.company_id, 'vat', False) or ''

        return {
            'ecr_rows': ecr_rows,
            'summary_rows': summary_rows,
            'tot_wages': round(tot_wages, 2),
            'tot_ee_epf': round(tot_ee_epf, 2),
            'tot_er_eps': round(tot_er_eps, 2),
            'tot_er_epf': round(tot_er_epf, 2),
            'tot_edli': round(tot_edli, 2),
            'tot_admin': round(tot_admin, 2),
            'tot_vpf': round(tot_vpf, 2),
            'tot_overall_contrib': round(tot_overall_contrib, 2),
            'record_count': len(ecr_rows),
            'est_name': est_name,
            'est_id': est_id,
        }

    def action_print_pdf(self):
        self.ensure_one()
        data = self._get_ecr_data()
        if not data.get('ecr_rows'):
            raise UserError(_("No employee records found for the selected period (%s).") % self._get_month_label())
        return self.env.ref('hudson_pf_reports.action_report_pf_ecr').report_action(self)

    def _generate_ecr_report_files(self):
        self.ensure_one()
        data = self._get_ecr_data()
        ecr_rows = data['ecr_rows']
        summary_rows = data['summary_rows']
        tot_wages = data['tot_wages']
        tot_ee_epf = data['tot_ee_epf']
        tot_er_eps = data['tot_er_eps']
        tot_er_epf = data['tot_er_epf']

        month_label = self._get_month_label().replace('-', '_')
        txt_filename = f"EPFO_ECR_{month_label}.txt"

        if self.report_type == 'epf_summary':
            xlsx_filename = f"EPF_Summary_Report_{month_label}.xlsx"
        else:
            xlsx_filename = f"EPF_ECR_Report_{month_label}.xlsx"

        txt_lines = []
        for row in ecr_rows:
            line = f"{row['uan']}#~#{row['name']}#~#{int(round(row['gross']))}#~#{int(round(row['epf_wages']))}#~#{int(round(row['eps_wages']))}#~#{int(round(row['ee_epf']))}#~#{int(round(row['er_epf']))}#~#{int(round(row['er_eps']))}#~#{row['ncp_days']}#~#{row['refund']}"
            txt_lines.append(line)
        txt_content = "\n".join(txt_lines)

        output = io.BytesIO()
        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
            text_fmt = workbook.add_format({'border': 1})
            meta_label_fmt = workbook.add_format({'bold': True, 'font_size': 11})
            meta_val_fmt = workbook.add_format({'font_size': 11})

            if self.report_type == 'epf_summary':
                sheet = workbook.add_worksheet('EPF Summary')

                headers = [
                    'Employee ID', 'Employee Name', 'Account Number', 'UAN',
                    'PF Wages', 'Employee PF Amount', 'VPF Amount', 'PF Amount',
                    'EPS Amount', 'EDLI', 'Admin Charge', 'Total Contribution'
                ]
                for col_idx, text in enumerate(headers):
                    sheet.write(0, col_idx, text, header_fmt)

                for row_idx, r in enumerate(summary_rows, start=1):
                    sheet.write(row_idx, 0, r['employee_id'], text_fmt)
                    sheet.write(row_idx, 1, r['employee_name'], text_fmt)
                    sheet.write(row_idx, 2, r['account_number'], text_fmt)
                    sheet.write(row_idx, 3, r['uan'], text_fmt)
                    sheet.write(row_idx, 4, r['pf_wages'], num_fmt)
                    sheet.write(row_idx, 5, r['employee_pf_amount'], num_fmt)
                    sheet.write(row_idx, 6, r['vpf_amount'], num_fmt)
                    sheet.write(row_idx, 7, r['pf_amount'], num_fmt)
                    sheet.write(row_idx, 8, r['eps_amount'], num_fmt)
                    sheet.write(row_idx, 9, r['edli'], num_fmt)
                    sheet.write(row_idx, 10, r['admin_charge'], num_fmt)
                    sheet.write(row_idx, 11, r['total_contribution'], num_fmt)
            else:
                sheet = workbook.add_worksheet('EPF Report')

                sheet.write(0, 0, "Establishment Name", meta_label_fmt)
                sheet.write(0, 1, data['est_name'], meta_val_fmt)
                sheet.write(1, 0, "Establishment ID", meta_label_fmt)
                sheet.write(1, 1, data['est_id'], meta_val_fmt)
                sheet.write(2, 0, "Total Members", meta_label_fmt)
                sheet.write(2, 1, len(ecr_rows), meta_val_fmt)

                headers = [
                    'SI No', 'UAN', 'Member Name', 'Gross Wages', 'EPF Wages', 'EPS Wages', 'EDLI Wages',
                    'Employee EPF Contribution', 'Employer EPF Contribution',
                    'EPS Contribution', 'Difference Remitted', 'NCP Days', 'Refunded Advances'
                ]
                for col_idx, text in enumerate(headers):
                    sheet.write(4, col_idx, text, header_fmt)

                for row_idx, r in enumerate(ecr_rows, start=1):
                    excel_row = row_idx + 4
                    sheet.write(excel_row, 0, row_idx, text_fmt)
                    sheet.write(excel_row, 1, r['uan'], text_fmt)
                    sheet.write(excel_row, 2, r['name'], text_fmt)
                    sheet.write(excel_row, 3, r['gross'], num_fmt)
                    sheet.write(excel_row, 4, r['epf_wages'], num_fmt)
                    sheet.write(excel_row, 5, r['eps_wages'], num_fmt)
                    sheet.write(excel_row, 6, r['edli_wages'], num_fmt)
                    sheet.write(excel_row, 7, r['ee_epf'], num_fmt)
                    sheet.write(excel_row, 8, r['er_epf'], num_fmt)
                    sheet.write(excel_row, 9, r['er_eps'], num_fmt)
                    sheet.write(excel_row, 10, 0.00, num_fmt)
                    sheet.write(excel_row, 11, r['ncp_days'], text_fmt)
                    sheet.write(excel_row, 12, r['refund'], text_fmt)

            workbook.close()
            output.seek(0)
            xlsx_content = output.read()
        else:
            xlsx_content = txt_content.encode('utf-8')

        self.write({
            'state': 'generated',
            'txt_file': base64.b64encode(txt_content.encode('utf-8')),
            'txt_filename': txt_filename,
            'xlsx_file': base64.b64encode(xlsx_content),
            'xlsx_filename': xlsx_filename,
            'record_count': len(ecr_rows),
            'total_epf_wages': tot_wages,
            'total_epf_deduction': tot_ee_epf,
            'total_eps_contribution': tot_er_eps,
            'total_epf_er_contribution': tot_er_epf,
        })

    def action_generate_ecr(self):
        self.ensure_one()
        self._generate_ecr_report_files()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_export_xlsx(self):
        return self.action_generate_ecr()

    def web_save(self, vals, specification: dict, next_id=None):
        res = super().web_save(vals, specification, next_id=next_id)
        for rec in self:
            try:
                rec._generate_ecr_report_files()
            except Exception:
                pass
        return super().web_save({}, specification, next_id=next_id)
