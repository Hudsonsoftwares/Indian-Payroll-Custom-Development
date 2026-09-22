# -*- coding: utf-8 -*-
import pytz
from datetime import datetime, time
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_attendance_vs_schedule(self, contract, date_from, date_to):
        """
        Calculates scheduled, actual, shortage, and unpaid leave hours on a 
        day-by-day basis to reconcile shortages and unpaid leaves, 
        ensuring they are mutually exclusive.
        """
        if not hasattr(self.env, '_attendance_cache'):
            self.env._attendance_cache = {}
        cache_key = (contract.id, date_from, date_to)
        if cache_key in self.env._attendance_cache:
            return self.env._attendance_cache[cache_key]

        # 1. Setup timezone and datetime boundaries
        calendar = contract.resource_calendar_id or contract.employee_id.resource_calendar_id or contract.company_id.resource_calendar_id
        tz = pytz.timezone(calendar.tz or 'UTC') if calendar else pytz.UTC
        
        # Localize day boundaries to contract/calendar timezone
        dt_from_local = tz.localize(datetime.combine(fields.Date.from_string(date_from), time.min))
        dt_to_local = tz.localize(datetime.combine(fields.Date.from_string(date_to), time.max))
        
        # Convert to naive UTC datetimes for database queries (check_in stored in UTC in DB)
        utc_day_from = dt_from_local.astimezone(pytz.UTC).replace(tzinfo=None)
        utc_day_to = dt_to_local.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # 2. Query all attendances in the period (using UTC boundaries so early morning shifts on 1st are included)
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', contract.employee_id.id),
            ('check_in', '>=', utc_day_from),
            ('check_in', '<=', utc_day_to),
        ])
        
        # Group attendances by their local check_in date
        attendances_by_date = {}
        for att in attendances:
            local_check_in = pytz.utc.localize(att.check_in).astimezone(tz)
            att_date = local_check_in.date()
            attendances_by_date.setdefault(att_date, []).append(att)
            
        # 3. Query all applied regularizations in the period
        regularizations = self.env['hudson.attendance.regularization'].search([
            ('employee_id', '=', contract.employee_id.id),
            ('state', '=', 'applied'),
            ('attendance_id.check_in', '>=', utc_day_from),
            ('attendance_id.check_in', '<=', utc_day_to),
        ])
        
        regularized_dates = set()
        for reg in regularizations:
            if reg.attendance_id:
                local_check_in = pytz.utc.localize(reg.attendance_id.check_in).astimezone(tz)
                regularized_dates.add(local_check_in.date())

        # 4. Get leave intervals using Odoo's native list_leaves method
        unpaid_hours_by_date = {}
        paid_hours_by_date = {}
        
        if calendar:
            day_leave_intervals = contract.employee_id.list_leaves(
                dt_from_local, dt_to_local, calendar=calendar
            )
            for day, hours, leave in day_leave_intervals:
                # Only individual employee leaves (having holiday_id or resource_id) populate leave hours
                # Global calendar leaves are handled via mandatory_holiday_dates
                emp_leaves = [l for l in leave if l.holiday_id or l.resource_id]
                if not emp_leaves:
                    continue
                is_unpaid = any(l.holiday_id and l.holiday_id.holiday_status_id.unpaid for l in emp_leaves)
                if is_unpaid:
                    unpaid_hours_by_date[day] = unpaid_hours_by_date.get(day, 0.0) + hours
                else:
                    paid_hours_by_date[day] = paid_hours_by_date.get(day, 0.0) + hours

        # 4b. Pre-query mandatory public holidays from Time Off (resource.calendar.leaves)
        mandatory_holiday_dates = set()
        if calendar:
            holiday_leaves = self.env['resource.calendar.leaves'].search([
                ('calendar_id', 'in', [calendar.id, False]),
                ('resource_id', '=', False),
                ('date_from', '<=', utc_day_to),
                ('date_to', '>=', utc_day_from),
            ])
            for hl in holiday_leaves:
                if getattr(hl, 'is_mandatory', True):
                    hl_start = pytz.utc.localize(hl.date_from).astimezone(tz).date()
                    hl_end = pytz.utc.localize(hl.date_to).astimezone(tz).date()
                    cur_d = max(hl_start, fields.Date.from_string(date_from))
                    max_d = min(hl_end, fields.Date.from_string(date_to))
                    while cur_d <= max_d:
                        mandatory_holiday_dates.add(cur_d)
                        cur_d += relativedelta(days=1)

        # 5. Day-by-day scheduled vs actual audit loop
        total_scheduled_hours = 0.0
        total_scheduled_days = 0.0
        total_actual_hours = 0.0
        total_shortage_hours = 0.0
        total_shortage_days = 0.0
        total_unpaid_hours = 0.0
        total_unpaid_days = 0.0
        
        current_date = fields.Date.from_string(date_from)
        end_date = fields.Date.from_string(date_to)
        day_std_hours = (calendar.hours_per_day if calendar and calendar.hours_per_day else 8.0)
        
        while current_date <= end_date:
            # Scheduled work hours for the day (factoring in working schedule and mandatory holidays)
            scheduled_hours = 0.0
            if calendar:
                day_start = tz.localize(datetime.combine(current_date, time.min))
                day_end = tz.localize(datetime.combine(current_date, time.max))
                base_scheduled = calendar.get_work_hours_count(day_start, day_end, compute_leaves=False)
                if current_date in mandatory_holiday_dates:
                    # Mandatory Public Holiday: scheduled work is 0 for employee (paid holiday, no shortage)
                    scheduled_hours = 0.0
                else:
                    scheduled_hours = base_scheduled
            
            total_scheduled_hours += scheduled_hours
            if scheduled_hours > 0.0:
                total_scheduled_days += min(1.0, scheduled_hours / day_std_hours)
            
            # Actual worked hours for the day
            day_atts = attendances_by_date.get(current_date, [])
            actual_hours = sum(att.worked_hours for att in day_atts)
            total_actual_hours += actual_hours
            
            unpaid_leave_hours = unpaid_hours_by_date.get(current_date, 0.0)
            paid_leave_hours = paid_hours_by_date.get(current_date, 0.0)
            denom = scheduled_hours if scheduled_hours > 0.0 else day_std_hours
            
            # Unpaid leave accounting
            if unpaid_leave_hours > 0.0:
                total_unpaid_hours += unpaid_leave_hours
                total_unpaid_days += unpaid_leave_hours / denom
            
            # Shortage reconciliation
            is_regularized = current_date in regularized_dates
            if is_regularized:
                # Regularized day: no shortage is deducted
                shortage_hours = 0.0
            else:
                # Leave takes priority, subtract leave hours from scheduled hours for shortage calculation
                remaining_scheduled = max(scheduled_hours - paid_leave_hours - unpaid_leave_hours, 0.0)
                shortage_hours = max(remaining_scheduled - actual_hours, 0.0)
                
            total_shortage_hours += shortage_hours
            if shortage_hours > 0.0:
                total_shortage_days += min(1.0, shortage_hours / denom)
            current_date += relativedelta(days=1)

        # 6. Overtime calculation (Calculate net extra hours beyond shift, e.g. 1 hr)
        approved_attendances = attendances.filtered(lambda a: a.overtime_status == 'approved')
        net_overtime_hours = 0.0
        for att in approved_attendances:
            ot_hrs = getattr(att, 'overtime_hours', 0.0) or 0.0
            val_hrs = getattr(att, 'validated_overtime_hours', 0.0) or 0.0
            if ot_hrs > 0.0 and val_hrs > 0.0:
                # Use net overtime hours, capped if user manually set a lower validated amount
                effective_ot = min(ot_hrs, val_hrs)
            elif ot_hrs > 0.0:
                effective_ot = ot_hrs
            else:
                effective_ot = val_hrs
            net_overtime_hours += effective_ot

        data = {
            'scheduled_hours': total_scheduled_hours,
            'scheduled_days': total_scheduled_days,
            'actual_hours': total_actual_hours,
            'validated_overtime_hours': net_overtime_hours,
            'overtime_hours_delta': net_overtime_hours,
            'shortage_hours_delta': total_shortage_hours,
            'shortage_days': total_shortage_days,
            'unpaid_hours': total_unpaid_hours,
            'unpaid_days': total_unpaid_days,
        }
        
        self.env._attendance_cache[cache_key] = data
        return data

    def _get_period_shortage_rate(self, contract, date_from, date_to):
        """Calculates period-exact hourly rate for Fixed Salary mode based on real scheduled hours."""
        data = self._get_attendance_vs_schedule(contract, date_from, date_to)
        sched_hrs = data.get('scheduled_hours', 0.0)
        if contract.salary_calculation_type == 'fixed':
            return (contract.wage / sched_hrs) if sched_hrs > 0.0 else 0.0
        return contract.shortage_deduction_rate_per_hour

    attendance_discrepancy_hours = fields.Float(
        string='Attendance Discrepancy Hours',
        compute='_compute_attendance_discrepancy',
        store=True,
    )
    has_attendance_discrepancy = fields.Boolean(
        string='Has Attendance Discrepancy',
        compute='_compute_attendance_discrepancy',
        store=True,
    )
    attendance_discrepancy_string = fields.Char(
        string='Attendance Mismatch String',
        compute='_compute_attendance_discrepancy_string',
    )

    @api.depends('worked_days_line_ids', 'employee_id', 'date_from', 'date_to')
    def _compute_attendance_discrepancy(self):
        for payslip in self:
            if payslip.contract_id and payslip.date_from and payslip.date_to:
                data = payslip._get_attendance_vs_schedule(payslip.contract_id, payslip.date_from, payslip.date_to)
                ot = data.get('overtime_hours_delta', 0.0)
                st = data.get('shortage_hours_delta', 0.0)
                payslip.attendance_discrepancy_hours = ot - st
            else:
                payslip.attendance_discrepancy_hours = 0.0
            payslip.has_attendance_discrepancy = abs(payslip.attendance_discrepancy_hours) > 0.01

    @api.depends('attendance_discrepancy_hours')
    def _compute_attendance_discrepancy_string(self):
        for payslip in self:
            val = payslip.attendance_discrepancy_hours
            sign = "+" if val >= 0 else ""
            payslip.attendance_discrepancy_string = f"{sign}{val:.1f} hrs"

    def action_view_attendance_discrepancy(self):
        self.ensure_one()
        calendar = self.contract_id.resource_calendar_id or self.employee_id.resource_calendar_id or self.company_id.resource_calendar_id
        tz = pytz.timezone(calendar.tz or 'UTC') if calendar else pytz.UTC
        dt_from_local = tz.localize(datetime.combine(fields.Date.from_string(self.date_from), time.min))
        dt_to_local = tz.localize(datetime.combine(fields.Date.from_string(self.date_to), time.max))
        utc_day_from = dt_from_local.astimezone(pytz.UTC).replace(tzinfo=None)
        utc_day_to = dt_to_local.astimezone(pytz.UTC).replace(tzinfo=None)
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '>=', utc_day_from),
            ('check_in', '<=', utc_day_to),
        ]
        return {
            'name': _('Attendances'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'view_mode': 'list,form',
            'domain': domain,
        }

    def action_compute_sheet(self):
        for payslip in self:
            payslip.worked_days_line_ids.unlink()
            lines = [(0, 0, line) for line in self.get_worked_day_lines(payslip.contract_id, payslip.date_from, payslip.date_to)]
            payslip.write({'worked_days_line_ids': lines})
        return super(HrPayslip, self).action_compute_sheet()

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        res = super(HrPayslip, self).get_worked_day_lines(contracts, date_from, date_to)
        for contract in contracts:
            data = self._get_attendance_vs_schedule(contract, date_from, date_to)
            sched_days = data.get('scheduled_days', 0.0)
            sched_hours = data.get('scheduled_hours', 0.0)
            work100_found = False
            for line in res:
                if line.get('code') == 'WORK100' and line.get('contract_id') == contract.id:
                    line['number_of_days'] = sched_days
                    line['number_of_hours'] = sched_hours
                    work100_found = True
            if not work100_found and sched_days > 0.0:
                res.insert(0, {
                    'name': _('Normal Working Days'),
                    'sequence': 1,
                    'code': 'WORK100',
                    'number_of_days': sched_days,
                    'number_of_hours': sched_hours,
                    'contract_id': contract.id,
                })

            if data.get('unpaid_days', 0.0) > 0.01:
                res.append({
                    'name': _('Unpaid Leave'),
                    'sequence': 4,
                    'code': 'UNPAID',
                    'number_of_days': data['unpaid_days'],
                    'number_of_hours': data['unpaid_hours'],
                    'contract_id': contract.id,
                })
            if contract.pay_by_attendance and data.get('shortage_hours_delta', 0.0) > 0.01:
                if not any(l.get('code') == 'SHORTAGE' for l in res):
                    res.append({
                        'name': _('Attendance Shortage'),
                        'sequence': 5,
                        'code': 'SHORTAGE',
                        'number_of_days': data.get('shortage_days', 0.0),
                        'number_of_hours': data['shortage_hours_delta'],
                        'contract_id': contract.id,
                    })
            if contract.pay_by_attendance and data.get('overtime_hours_delta', 0.0) > 0.01:
                if not any(l.get('code') == 'OVERTIME' for l in res):
                    res.append({
                        'name': _('Overtime Hours'),
                        'sequence': 5,
                        'code': 'OVERTIME',
                        'number_of_days': 0.0,
                        'number_of_hours': data['overtime_hours_delta'],
                        'contract_id': contract.id,
                    })
        return res
