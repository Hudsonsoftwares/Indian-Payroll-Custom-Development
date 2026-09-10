# -*- coding: utf-8 -*-
import base64
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class HdsPfBasisWizard(models.TransientModel):
    _name = 'hds.pf.basis.wizard'
    _inherit = 'hds.pf.report.wizard.base'
    _description = 'PF Contribution Basis Report Wizard'

    name = fields.Char(string='Report Name', compute='_compute_name', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
    ], string='State', default='draft')

    xlsx_file = fields.Binary(string='Contribution Basis Excel (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    @api.depends('month', 'year')
    def _compute_name(self):
        month_dict = dict(self._fields['month'].selection)
        for rec in self:
            m_label = month_dict.get(rec.month, '')
            rec.name = f"PF Contribution Basis / {m_label}-{rec.year}"

    def action_export_xlsx(self):
        self.ensure_one()
        payslips = self._get_confirmed_payslips([('employee_id.hds_in_epf_applicable', '=', True)])

        if not payslips:
            raise UserError(_("No confirmed payslips found for EPF-applicable employees in period (%s).") % self._get_month_label())

        date_from, date_to = self._get_date_range()
        pf_ceiling = self.env['hr.rule.parameter'].get_pf_parameter('PF_WAGE_CEILING', date=date_to)

        rows = []
        for payslip in payslips:
            emp = payslip.employee_id
            basis_code = getattr(emp, 'hds_in_pf_contribution_basis', False)

            # Resolve label via field._description_selection(env)
            basis_label = ''
            if basis_code and 'hds_in_pf_contribution_basis' in emp._fields:
                field_obj = emp._fields['hds_in_pf_contribution_basis']
                if hasattr(field_obj, '_description_selection') and callable(getattr(field_obj, '_description_selection')):
                    sel_dict = dict(field_obj._description_selection(self.env))
                    basis_label = sel_dict.get(basis_code, str(basis_code))
                else:
                    basis_label = str(basis_code)

            actual_pf_wage = payslip.hds_in_get_actual_pf_wage()
            pf_used = payslip.hds_in_get_pf_contribution_wage()

            rows.append({
                'employee': emp.name,
                'basis': basis_label,
                'actual_pf_wage': round(actual_pf_wage, 2),
                'statutory_ceiling': round(pf_ceiling, 2),
                'pf_used': round(pf_used, 2),
            })

        month_label = self._get_month_label().replace('-', '_')
        xlsx_filename = f"PF_Contribution_Basis_{month_label}.xlsx"

        output = io.BytesIO()
        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('PF Contribution Basis')

            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF', 'border': 1})
            num_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
            text_fmt = workbook.add_format({'border': 1})

            headers = ['Employee', 'Contribution Basis', 'Actual PF Wage', 'Statutory Wage Ceiling', 'PF Wage Used']
            for col_idx, text in enumerate(headers):
                sheet.write(0, col_idx, text, header_fmt)

            for row_idx, r in enumerate(rows, start=1):
                sheet.write(row_idx, 0, r['employee'], text_fmt)
                sheet.write(row_idx, 1, r['basis'], text_fmt)
                sheet.write(row_idx, 2, r['actual_pf_wage'], num_fmt)
                sheet.write(row_idx, 3, r['statutory_ceiling'], num_fmt)
                sheet.write(row_idx, 4, r['pf_used'], num_fmt)

            workbook.close()
            output.seek(0)
            xlsx_content = output.read()
        else:
            xlsx_content = b"Excel export requires xlsxwriter library."

        self.write({
            'state': 'generated',
            'xlsx_file': base64.b64encode(xlsx_content),
            'xlsx_filename': xlsx_filename,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
