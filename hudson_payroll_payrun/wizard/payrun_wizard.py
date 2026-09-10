# -*- coding: utf-8 -*-
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HudsonPayrollPayrunWizard(models.TransientModel):
    _name = 'hudson.payroll.payrun.wizard'
    _description = 'New Pay Run Wizard'

    name = fields.Char(
        string='Pay Run Name',
        required=True,
        default=lambda self: _('Pay Run %s') % date.today().strftime('%B %Y')
    )
    date_start = fields.Date(
        string='Date From',
        required=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1))
    )
    date_end = fields.Date(
        string='Date To',
        required=True,
        default=lambda self: fields.Date.to_string(
            (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()
        )
    )
    employee_type_ids = fields.Many2many(
        'hr.employee.type',
        string='Employee Types',
        help="Select specific employee classification types to include. Leave empty for all types."
    )
    department_ids = fields.Many2many(
        'hr.department',
        string='Departments',
        help="Select specific departments to include. Leave empty for all departments."
    )
    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Pay Structure',
        help="Optional override structure for generated payslips."
    )
    credit_note = fields.Boolean(
        string='Credit Note',
        help="Check if this pay run is for refund payslips."
    )

    def action_confirm_and_generate(self):
        """Create Pay Run record and automatically generate payslips."""
        self.ensure_one()
        if self.date_start > self.date_end:
            raise UserError(_("Date From must be earlier than or equal to Date To."))

        payrun_vals = {
            'name': self.name,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'department_ids': [(6, 0, self.department_ids.ids)],
            'employee_type_ids': [(6, 0, self.employee_type_ids.ids)],
            'struct_id': self.struct_id.id if self.struct_id else False,
            'credit_note': self.credit_note,
            'state': 'draft',
        }

        payrun = self.env['hr.payslip.run'].create(payrun_vals)
        payrun.action_generate_payslips()

        form_view = self.env.ref('hr_payroll_community.hr_payslip_run_view_form', False)

        return {
            'name': _('Pay Run - %s') % payrun.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.run',
            'res_id': payrun.id,
            'view_mode': 'form',
            'views': [(form_view and form_view.id or False, 'form')],
            'target': 'current',
        }
