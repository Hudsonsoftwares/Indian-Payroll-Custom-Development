# -*- coding: utf-8 -*-
from datetime import datetime
from pytz import timezone, utc
from odoo import api, fields, models

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Override expected_hours and overtime_hours compute methods
    expected_hours = fields.Float(string="Regular Hours", compute='_compute_expected_hours', store=True)
    overtime_hours = fields.Float(string="Over Time", compute='_compute_overtime_hours', store=True)

    @api.depends('employee_id', 'date', 'check_in', 'check_out')
    def _compute_expected_hours(self):
        for attendance in self:
            if not attendance.employee_id or not attendance.date:
                attendance.expected_hours = 0.0
                continue
            
            employee = attendance.employee_id
            calendar = employee.resource_calendar_id
            if not calendar:
                attendance.expected_hours = 8.0
                continue
            
            tz_name = employee._get_tz() or 'UTC'
            tz = timezone(tz_name)
            
            # Calculate start and end of date in the employee's timezone
            start_dt_local = tz.localize(datetime.combine(attendance.date, datetime.min.time()))
            end_dt_local = tz.localize(datetime.combine(attendance.date, datetime.max.time()))
            
            # Convert to UTC for intervals calculation
            start_dt = start_dt_local.astimezone(utc)
            end_dt = end_dt_local.astimezone(utc)
            
            resource = employee.resource_id
            if not resource:
                # Fallback to calendar default if no resource is linked
                expected = calendar.get_work_hours_count(start_dt, end_dt, compute_leaves=True)
                attendance.expected_hours = expected
                continue
            
            # Get work intervals taking global and employee leaves into account
            intervals = calendar._work_intervals_batch(start_dt, end_dt, resources=resource)[resource.id]
            expected_hours = sum((stop - start).total_seconds() / 3600 for start, stop, meta in intervals)
            attendance.expected_hours = expected_hours

    @api.depends('worked_hours', 'expected_hours')
    def _compute_overtime_hours(self):
        for attendance in self:
            attendance.overtime_hours = attendance.worked_hours - attendance.expected_hours
