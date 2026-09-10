# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipEmployees(models.TransientModel):
    """Wizard to generate multiple payslips at once for a payslip batch."""
    _name = 'hr.payslip.employees'
    _description = 'Generate Payslips for all selected employees'

    employee_ids = fields.Many2many(
        'hr.employee',
        'hr_payslip_employees_rel',
        'wizard_id',
        'employee_id',
        string='Employees',
        required=True
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and self.env.context.get('active_model') == 'hr.payslip.run':
            run = self.env['hr.payslip.run'].browse(active_id)
            off_cycle_slips = self.env['hr.payslip'].search([
                ('payslip_run_id', '=', False),
                ('date_from', '<=', run.date_end),
                ('date_to', '>=', run.date_start),
                ('company_id', '=', run.company_id.id)
            ])
            if 'employee_ids' in fields_list and off_cycle_slips:
                res['employee_ids'] = [(6, 0, off_cycle_slips.mapped('employee_id').ids)]
        return res

    def compute_sheet(self):
        payslip_run_id = self.env.context.get('active_id')
        if not payslip_run_id:
            raise UserError(_("No active payrun batch found."))

        run = self.env['hr.payslip.run'].browse(payslip_run_id)
        payslips = self.env['hr.payslip']

        existing_emp_ids = set(run.slip_ids.mapped('employee_id.id'))
        for employee in self.employee_ids:
            # Check if employee is already in this run
            if employee.id in existing_emp_ids:
                continue

            # 1. Check if employee has a detached off-cycle payslip for this period
            existing_slip = self.env['hr.payslip'].search([
                ('employee_id', '=', employee.id),
                ('payslip_run_id', '=', False),
                ('date_from', '<=', run.date_end),
                ('date_to', '>=', run.date_start),
            ], limit=1)

            if existing_slip:
                existing_slip.write({'payslip_run_id': run.id})
                payslips |= existing_slip
                existing_emp_ids.add(employee.id)
                continue

            # 2. Otherwise generate a new payslip for employee
            contract = False
            if employee.version_id:
                c = employee.version_id
                c_start = getattr(c, 'contract_date_start', False) or getattr(c, 'date_start', False)
                c_end = getattr(c, 'contract_date_end', False) or getattr(c, 'date_end', False)
                if (not c_start or c_start <= run.date_end) and (not c_end or c_end >= run.date_start):
                    contract = c

            if not contract:
                domain = [('employee_id', '=', employee.id)]
                if 'contract_date_start' in self.env['hr.version']._fields:
                    domain += [
                        '|', ('contract_date_start', '=', False), ('contract_date_start', '<=', run.date_end),
                        '|', ('contract_date_end', '=', False), ('contract_date_end', '>=', run.date_start),
                    ]
                contract = self.env['hr.version'].search(domain, limit=1, order='id desc')

            if not contract and employee.version_id:
                contract = employee.version_id

            if not contract:
                continue

            struct = getattr(contract, 'struct_id', False)
            if not struct and hasattr(contract, 'structure_type_id') and contract.structure_type_id:
                struct = self.env['hr.payroll.structure'].search([
                    ('type_id', '=', contract.structure_type_id.id)
                ], limit=1)

            if not struct:
                continue

            slip_vals = {
                'name': _('Salary Slip - %(emp)s - %(period)s') % {
                    'emp': employee.name,
                    'period': run.date_start.strftime('%B %Y')
                },
                'employee_id': employee.id,
                'contract_id': contract.id,
                'struct_id': run.struct_id.id if run.struct_id else struct.id,
                'date_from': run.date_start,
                'date_to': run.date_end,
                'payslip_run_id': run.id,
                'company_id': run.company_id.id,
            }
            slip = self.env['hr.payslip'].create(slip_vals)
            slip._populate_worked_days()
            slip._populate_inputs()
            payslips |= slip

        if payslips:
            draft_uncomputed = payslips.filtered(lambda s: s.state == 'draft' and not s.line_ids)
            if draft_uncomputed:
                draft_uncomputed.compute_sheet()

        run._compute_counts()
        run._compute_financial_totals()
        run._compute_milestones()

        return {'type': 'ir.actions.act_window_close'}
