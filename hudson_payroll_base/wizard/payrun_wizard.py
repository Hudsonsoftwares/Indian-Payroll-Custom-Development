# -*- coding: utf-8 -*-
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HudsonPayrollPayrunWizard(models.TransientModel):
    _name = 'hudson.payroll.payrun.wizard'
    _description = 'New Pay Run Wizard'

    name = fields.Char(
        string='Pay Run Title',
        help="Leave blank to automatically name based on period and structure."
    )
    date_start = fields.Date(
        string='Period From',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1)
    )
    date_end = fields.Date(
        string='Period To',
        required=True,
        default=lambda self: (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()
    )
    employee_type_ids = fields.Many2many(
        'hr.employee.type',
        string='Employee Types',
        help="Select specific employee types. Leave empty for all employee types."
    )
    department_ids = fields.Many2many(
        'hr.department',
        string='Departments',
        help="Select specific departments. Leave empty for all departments."
    )
    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Pay Structure',
        help="Select a structure. Leave empty to use employee default structure."
    )

    def action_confirm_and_generate(self):
        """Create Pay Run record, automatically generate payslips, compute attendance/worked days, and return to Kanban view."""
        self.ensure_one()
        if self.date_start > self.date_end:
            raise UserError(_("Date From must be earlier than or equal to Date To."))

        run_name = self.name
        if not run_name:
            struct_name = self.struct_id.name if self.struct_id else _("Regular Pay")
            run_name = "%s - %s" % (self.date_start.strftime("%b %Y"), struct_name)

        payrun_vals = {
            'name': run_name,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'department_ids': [(6, 0, self.department_ids.ids)],
            'employee_type_ids': [(6, 0, self.employee_type_ids.ids)],
            'struct_id': self.struct_id.id if self.struct_id else False,
            'state': 'draft',
        }

        payrun = self.env['hr.payslip.run'].create(payrun_vals)
        # Generate payslips
        payrun.action_generate_payslips()
        # Compute sheet for slips so worked days and attendances are immediately populated!
        payrun.action_compute_all()

        action = self.env.ref('hudson_payroll_base.action_hr_payslip_run').read()[0]
        action['target'] = 'current'
        return action
