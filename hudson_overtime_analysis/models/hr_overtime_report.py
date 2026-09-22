# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools

class HrOvertimeReport(models.Model):
    _name = "hr.overtime.report"
    _description = "Overtime Reporting"
    _auto = False
    _order = 'date desc'

    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    department_id = fields.Many2one('hr.department', string="Department", readonly=True)
    date = fields.Date(string="Date", readonly=True)
    worked_hours = fields.Float(string="Worked Hours", readonly=True)
    expected_hours = fields.Float(string="Regular Hours", readonly=True)
    overtime_hours = fields.Float(string="Overtime Hours", readonly=True)
    is_leave_day = fields.Boolean(string="Is Leave Day", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s AS (
                SELECT
                    att.id as id,
                    att.employee_id as employee_id,
                    v.department_id as department_id,
                    att.date as date,
                    att.worked_hours as worked_hours,
                    att.expected_hours as expected_hours,
                    att.overtime_hours as overtime_hours,
                    EXISTS (
                        SELECT 1 FROM hr_leave l
                        WHERE l.employee_id = att.employee_id
                          AND l.state = 'validate'
                          AND l.date_from::date <= att.date
                          AND l.date_to::date >= att.date
                    ) as is_leave_day
                FROM hr_attendance att
                JOIN hr_employee emp ON att.employee_id = emp.id
                LEFT JOIN hr_version v ON emp.current_version_id = v.id
            )
        """ % self._table)

    @api.model
    def get_overtime_hours(self, employee_id, date_from, date_to):
        """
        Returns the total sum of overtime hours for the given employee and period (inclusive).
        This can be consumed by other modules (e.g. payroll) for overtime pay calculations.
        """
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee_id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ])
        return sum(attendances.mapped('overtime_hours'))
