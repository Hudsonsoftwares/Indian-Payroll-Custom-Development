# -*- coding: utf-8 -*-
import pytz
from datetime import datetime, time
from odoo import api, fields, models, _

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model_create_multi
    def create(self, vals_list):
        records = super(HrAttendance, self).create(vals_list)
        for rec in records:
            ot = getattr(rec, 'overtime_hours', 0.0) or 0.0
            val = getattr(rec, 'validated_overtime_hours', 0.0) or 0.0
            if ot == 0.0 and val > 0.0:
                rec.sudo().write({'validated_overtime_hours': 0.0})
            elif ot > 0.0 and val > ot:
                rec.sudo().write({'validated_overtime_hours': ot})
        return records

    def write(self, vals):
        res = super(HrAttendance, self).write(vals)
        for rec in self:
            ot = getattr(rec, 'overtime_hours', 0.0) or 0.0
            val = getattr(rec, 'validated_overtime_hours', 0.0) or 0.0
            if ot == 0.0 and val > 0.0:
                super(HrAttendance, rec).write({'validated_overtime_hours': 0.0})
            elif ot > 0.0 and val > ot:
                super(HrAttendance, rec).write({'validated_overtime_hours': ot})
        return res

    def _check_anomalies(self):
        if hasattr(super(HrAttendance, self), '_check_anomalies'):
            super(HrAttendance, self)._check_anomalies()
        for att in self:
            if att.check_in and att.check_out and att.employee_id.resource_calendar_id:
                calendar = att.employee_id.resource_calendar_id
                tz = pytz.timezone(calendar.tz or 'UTC')
                
                # Localize check-in date
                local_check_in = pytz.utc.localize(att.check_in).astimezone(tz)
                day = local_check_in.date()
                
                # Get scheduled hours for this day
                day_start = tz.localize(datetime.combine(day, time.min))
                day_end = tz.localize(datetime.combine(day, time.max))
                
                # Respect public holidays (leaves) when checking for shortfall
                is_public_holiday = bool(calendar.global_leave_ids.filtered(
                    lambda l: l.date_from.date() <= day <= l.date_to.date()
                ))
                scheduled_hours = 0.0 if is_public_holiday else calendar.get_work_hours_count(day_start, day_end, compute_leaves=False)
                
                if scheduled_hours > 0.0:
                    worked = att.worked_hours
                    if worked < (scheduled_hours - 0.25):
                        # Shortfall detected (worked hours less than scheduled minus 15 min tolerance)
                        existing = self.env['hudson.attendance.anomaly'].search([
                            ('attendance_id', '=', att.id),
                            ('anomaly_type', '=', 'hours_shortfall')
                        ])
                        if not existing:
                            anomaly = self.env['hudson.attendance.anomaly'].create({
                                'name': 'Hours Shortfall',
                                'anomaly_type': 'hours_shortfall',
                                'employee_id': att.employee_id.id,
                                'attendance_id': att.id,
                                'description': f"Employee worked {worked:.2f} hours, which falls short of scheduled {scheduled_hours:.2f} hours (tolerance 15 minutes)."
                            })
                            # Auto-create draft regularization request
                            self.env['hudson.attendance.regularization'].create({
                                'employee_id': att.employee_id.id,
                                'anomaly_id': anomaly.id,
                                'attendance_id': att.id,
                                'orig_check_in': att.check_in,
                                'orig_check_out': att.check_out,
                                'reason': 'Auto-generated for Hours Shortfall.',
                                'state': 'draft'
                            })

            # Missing Punch / Missing Check-out Anomaly & Regularization Check
            if att.check_in and not att.check_out:
                existing = self.env['hudson.attendance.anomaly'].search([
                    ('attendance_id', '=', att.id),
                    ('anomaly_type', '=', 'missing_punch')
                ])
                if not existing:
                    calendar = att.employee_id.resource_calendar_id
                    tz = pytz.timezone(calendar.tz or 'UTC') if calendar else pytz.UTC
                    local_check_in = pytz.utc.localize(att.check_in).astimezone(tz)
                    
                    anomaly = self.env['hudson.attendance.anomaly'].create({
                        'name': 'Missing Punch',
                        'anomaly_type': 'missing_punch',
                        'employee_id': att.employee_id.id,
                        'attendance_id': att.id,
                        'description': f"Employee checked in at {local_check_in.strftime('%Y-%m-%d %H:%M:%S')} but has no check-out."
                    })
                    self.env['hudson.attendance.regularization'].create({
                        'employee_id': att.employee_id.id,
                        'anomaly_id': anomaly.id,
                        'attendance_id': att.id,
                        'orig_check_in': att.check_in,
                        'orig_check_out': False,
                        'reason': 'Auto-generated for Missing Punch.',
                        'state': 'draft'
                    })

    @api.model
    def _cron_check_attendance_anomalies(self):
        """
        Daily cron to detect missing check-outs (Missing Punch) for past days.
        """
        # Find all open attendances (no check-out)
        open_attendances = self.search([('check_out', '=', False)])
        for att in open_attendances:
            if not att.check_in or not att.employee_id:
                continue
            calendar = att.employee_id.resource_calendar_id
            tz = pytz.timezone(calendar.tz or 'UTC') if calendar else pytz.UTC
            
            # Localize check-in and current time
            local_check_in = pytz.utc.localize(att.check_in).astimezone(tz)
            local_now = datetime.now(tz)
            
            # Calculate check-in age to avoid flagging active night shifts
            age_seconds = (datetime.now() - att.check_in).total_seconds()
            
            # If the check_in is older than 14 hours and its localized date is strictly before today
            if age_seconds > 14 * 3600 and local_check_in.date() < local_now.date():
                existing = self.env['hudson.attendance.anomaly'].search([
                    ('attendance_id', '=', att.id),
                    ('anomaly_type', '=', 'missing_punch')
                ])
                if not existing:
                    anomaly = self.env['hudson.attendance.anomaly'].create({
                        'name': 'Missing Punch',
                        'anomaly_type': 'missing_punch',
                        'employee_id': att.employee_id.id,
                        'attendance_id': att.id,
                        'description': f"Employee checked in at {local_check_in.strftime('%Y-%m-%d %H:%M:%S')} but has no check-out."
                    })
                    # Auto-create draft regularization request
                    self.env['hudson.attendance.regularization'].create({
                        'employee_id': att.employee_id.id,
                        'anomaly_id': anomaly.id,
                        'attendance_id': att.id,
                        'orig_check_in': att.check_in,
                        'orig_check_out': False,
                        'reason': 'Auto-generated for Missing Punch.',
                        'state': 'draft'
                    })
