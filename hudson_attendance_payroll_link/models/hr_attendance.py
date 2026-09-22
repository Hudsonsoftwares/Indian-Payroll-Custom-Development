import pytz
from datetime import datetime, time, timedelta
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

            # When attendance is auto-checked out (either via native _cron_auto_check_out or custom cron)
            if vals.get('out_mode') == 'auto_check_out' or (vals.get('check_out') and rec.out_mode == 'auto_check_out'):
                rec._handle_auto_checkout_missing_punch()
        return res

    def _handle_auto_checkout_missing_punch(self):
        """
        When an employee is automatically checked out due to missing punch at shift end,
        automatically generate a Missing Punch anomaly and a Draft Regularization Request.
        """
        for att in self:
            if not att.check_in or not att.check_out:
                continue
            existing = self.env['hudson.attendance.anomaly'].search([
                ('attendance_id', '=', att.id),
                ('anomaly_type', '=', 'missing_punch')
            ], limit=1)
            if not existing:
                calendar = att.employee_id.resource_calendar_id
                tz = pytz.timezone(calendar.tz or 'UTC') if calendar else pytz.UTC
                local_check_in = pytz.utc.localize(att.check_in).astimezone(tz) if att.check_in.tzinfo is None else att.check_in.astimezone(tz)
                local_check_out = pytz.utc.localize(att.check_out).astimezone(tz) if att.check_out.tzinfo is None else att.check_out.astimezone(tz)

                anomaly = self.env['hudson.attendance.anomaly'].create({
                    'name': 'Missing Punch',
                    'anomaly_type': 'missing_punch',
                    'employee_id': att.employee_id.id,
                    'attendance_id': att.id,
                    'description': (
                        f"Employee checked in at {local_check_in.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"but missed check-out. Automatically checked out at {local_check_out.strftime('%H:%M:%S')} "
                        f"based on scheduled shift."
                    )
                })
                self.env['hudson.attendance.regularization'].create({
                    'employee_id': att.employee_id.id,
                    'anomaly_id': anomaly.id,
                    'attendance_id': att.id,
                    'orig_check_in': att.check_in,
                    'orig_check_out': False,
                    'corrected_check_in': att.check_in,
                    'corrected_check_out': att.check_out,
                    'reason': 'Auto-generated for Missing Punch. Auto-closed at scheduled shift end with tolerance.',
                    'state': 'draft'
                })

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

    @api.model
    def _cron_check_attendance_anomalies(self):
        """
        Daily cron to detect missing check-outs (Missing Punch) for past days.
        Automatically closes the open attendance at scheduled shift end so the employee
        is not locked out of check-in the next day, and generates a draft regularization.
        """
        # Find all open attendances (no check-out)
        open_attendances = self.search([('check_out', '=', False)])
        for att in open_attendances:
            if not att.check_in or not att.employee_id:
                continue
            calendar = att.employee_id.resource_calendar_id
            tz = pytz.timezone(calendar.tz or 'UTC') if calendar else pytz.UTC
            
            # Localize check-in and current time
            local_check_in = pytz.utc.localize(att.check_in).astimezone(tz) if att.check_in.tzinfo is None else att.check_in.astimezone(tz)
            local_now = datetime.now(tz)
            
            # Calculate check-in age in UTC to avoid flagging active night shifts
            age_seconds = (fields.Datetime.now() - att.check_in).total_seconds()
            
            # If the check_in is older than 14 hours and its localized date is strictly before today
            if age_seconds > 14 * 3600 and local_check_in.date() < local_now.date():
                # Compute scheduled shift end from calendar or fallback
                auto_checkout_dt = None
                if calendar:
                    day_start = tz.localize(datetime.combine(local_check_in.date(), time.min))
                    day_end = tz.localize(datetime.combine(local_check_in.date(), time.max))
                    intervals = calendar._work_intervals_batch(day_start, day_end).get(calendar.id, [])
                    if intervals:
                        last_interval = list(intervals)[-1]
                        auto_checkout_dt = last_interval[1].astimezone(pytz.UTC).replace(tzinfo=None)
                
                if not auto_checkout_dt:
                    end_local = tz.localize(datetime.combine(local_check_in.date(), time(18, 0, 0)))
                    auto_checkout_dt = end_local.astimezone(pytz.UTC).replace(tzinfo=None)
                    if auto_checkout_dt <= att.check_in:
                        auto_checkout_dt = att.check_in + timedelta(hours=8)

                # Close the attendance record safely with GPS validation bypassed
                att.with_context(disable_gps_validation=True, biometric_punch_processing=True).write({
                    'check_out': auto_checkout_dt,
                    'out_mode': 'auto_check_out',
                })
