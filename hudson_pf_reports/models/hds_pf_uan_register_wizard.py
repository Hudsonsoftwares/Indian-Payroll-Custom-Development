# -*- coding: utf-8 -*-
import base64
import io
from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class HdsPfUanRegisterWizard(models.TransientModel):
    _name = 'hds.pf.uan.register.wizard'
    _description = 'UAN Register Wizard'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    name = fields.Char(string='Report Name', compute='_compute_name', store=True)
    state = fields.Selection([('draft', 'Draft'), ('generated', 'Generated')], string='State', default='draft')
    xlsx_file = fields.Binary(string='UAN Register Excel (.xlsx)', readonly=True)
    xlsx_filename = fields.Char(string='Excel Filename', readonly=True)

    @api.depends('company_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f"UAN Register / {rec.company_id.name}"

    def action_export_xlsx(self):
        self.ensure_one()
        employees = self.env['hr.employee'].with_context(active_test=False).search([
            ('company_id', '=', self.company_id.id),
        ], order='name asc')

        if not employees:
            raise UserError(_("No employees found for company %s.") % self.company_id.name)

        rows = []
        for emp in employees:
            j_date = getattr(emp, 'joining_date', False)
            if not j_date:
                contracts = self.env['hr.version'].search([('employee_id', '=', emp.id)], order='id asc', limit=1)
                if contracts:
                    j_date = contracts.date_start

            exit_date = getattr(emp, 'resign_date', False) or getattr(emp, 'departure_date', False)

            rows.append({
                'employee': emp.name,
                'code': emp.identification_id or '',
                'uan': getattr(emp, 'hds_in_uan', '') or '',
                'pf_member_id': getattr(emp, 'hds_in_pf_member_id', '') or '',
                'doj': str(j_date) if j_date else '',
                'exit_date': str(exit_date) if exit_date else '',
                'epf_applicable': 'Yes' if getattr(emp, 'hds_in_epf_applicable', False) else 'No',
                'eps_applicable': 'Yes' if getattr(emp, 'hds_in_eps_applicable', False) else 'No',
                'active': 'Active' if emp.active else 'Archived/Resigned',
            })

        xlsx_filename = f"UAN_Register_{self.company_id.name.replace(' ', '_')}.xlsx"

        output = io.BytesIO()
        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('UAN Register')

            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF', 'border': 1})
            text_fmt = workbook.add_format({'border': 1})

            headers = [
                'Employee Name', 'Employee Code', 'UAN', 'PF Member ID',
                'Date of Joining (DOJ)', 'Date of Exit', 'EPF Applicable', 'EPS Applicable', 'Employment Status'
            ]
            for col_idx, text in enumerate(headers):
                sheet.write(0, col_idx, text, header_fmt)

            for row_idx, r in enumerate(rows, start=1):
                sheet.write(row_idx, 0, r['employee'], text_fmt)
                sheet.write(row_idx, 1, r['code'], text_fmt)
                sheet.write(row_idx, 2, r['uan'], text_fmt)
                sheet.write(row_idx, 3, r['pf_member_id'], text_fmt)
                sheet.write(row_idx, 4, r['doj'], text_fmt)
                sheet.write(row_idx, 5, r['exit_date'], text_fmt)
                sheet.write(row_idx, 6, r['epf_applicable'], text_fmt)
                sheet.write(row_idx, 7, r['eps_applicable'], text_fmt)
                sheet.write(row_idx, 8, r['active'], text_fmt)

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
