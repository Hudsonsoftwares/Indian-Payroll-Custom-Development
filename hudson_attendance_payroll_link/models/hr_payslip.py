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
        calendar = contract.resource_calendar_id
        tz = pytz.timezone(calendar.tz or 'UTC') if calendar else pytz.UTC
        
        day_from = datetime.combine(fields.Date.from_string(date_from), time.min)
        day_to = datetime.combine(fields.Date.from_string(date_to), time.max)
        
        # 2. Query all attendances in the period
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', contract.employee_id.id),
            ('check_in', '>=', day_from),
            ('check_in', '<=', day_to),
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
            ('attendance_id.check_in', '>=', day_from),
            ('attendance_id.check_in', '<=', day_to),
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
                day_from, day_to, calendar=calendar
            )
            for day, hours, leave in day_leave_intervals:
                is_unpaid = False
                for l in leave:
                    if l.holiday_id and l.holiday_id.holiday_status_id.unpaid:
                        is_unpaid = True
                        break
                if is_unpaid:
                    unpaid_hours_by_date[day] = unpaid_hours_by_date.get(day, 0.0) + hours
                else:
                    paid_hours_by_date[day] = paid_hours_by_date.get(day, 0.0) + hours

        # 5. Day-by-day scheduled vs actual audit loop
        total_scheduled_hours = 0.0
        total_actual_hours = 0.0
        total_shortage_hours = 0.0
        total_unpaid_hours = 0.0
        total_unpaid_days = 0.0
        
        current_date = fields.Date.from_string(date_from)
        end_date = fields.Date.from_string(date_to)
        
        while current_date <= end_date:
            # Scheduled work hours for the day
            scheduled_hours = 0.0
            if calendar:
                day_start = tz.localize(datetime.combine(current_date, time.min))
                day_end = tz.localize(datetime.combine(current_date, time.max))
                scheduled_hours = calendar.get_work_hours_count(day_start, day_end, compute_leaves=False)
            
            total_scheduled_hours += scheduled_hours
            
            # Actual worked hours for the day
            day_atts = attendances_by_date.get(current_date, [])
            actual_hours = sum(att.worked_hours for att in day_atts)
            total_actual_hours += actual_hours
            
            unpaid_leave_hours = unpaid_hours_by_date.get(current_date, 0.0)
            paid_leave_hours = paid_hours_by_date.get(current_date, 0.0)
            
            # Unpaid leave accounting
            if unpaid_leave_hours > 0.0:
                total_unpaid_hours += unpaid_leave_hours
                std_hours = contract.standard_hours_per_day or 8.0
                denom = scheduled_hours if scheduled_hours > 0.0 else std_hours
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
            'actual_hours': total_actual_hours,
            'validated_overtime_hours': net_overtime_hours,
            'overtime_hours_delta': net_overtime_hours,
            'shortage_hours_delta': total_shortage_hours,
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
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '>=', datetime.combine(fields.Date.from_string(self.date_from), time.min)),
            ('check_in', '<=', datetime.combine(fields.Date.from_string(self.date_to), time.max)),
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
            if data.get('unpaid_days', 0.0) > 0.01:
                res.append({
                    'name': _('Unpaid Leave'),
                    'sequence': 4,
                    'code': 'UNPAID',
                    'number_of_days': data['unpaid_days'],
                    'number_of_hours': data['unpaid_hours'],
                    'contract_id': contract.id,
                })
            if data.get('shortage_hours_delta', 0.0) > 0.01:
                if not any(l.get('code') == 'SHORTAGE' for l in res):
                    res.append({
                        'name': _('Attendance Shortage'),
                        'sequence': 5,
                        'code': 'SHORTAGE',
                        'number_of_days': 0.0,
                        'number_of_hours': data['shortage_hours_delta'],
                        'contract_id': contract.id,
                    })
            if data.get('overtime_hours_delta', 0.0) > 0.01:
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
