# -*- coding: utf-8 -*-
import pytz
from datetime import datetime, time, date as date_type
from dateutil.relativedelta import relativedelta
# pyrefly: ignore [missing-import]
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
        total_out_of_contract_hours = 0.0
        total_out_of_contract_days = 0.0
        total_actual_hours = 0.0
        total_shortage_hours = 0.0
        total_shortage_days = 0.0
        total_unpaid_hours = 0.0
        total_unpaid_days = 0.0
        
        current_date = fields.Date.from_string(date_from)
        end_date = fields.Date.from_string(date_to)
        day_std_hours = (calendar.hours_per_day if calendar and calendar.hours_per_day else 8.0)

        c_start = getattr(contract, 'contract_date_start', False) or getattr(contract, 'date_start', False)
        c_end = getattr(contract, 'contract_date_end', False) or getattr(contract, 'date_end', False)
        
        while current_date <= end_date:
            # Check if this day is outside contract bounds
            is_out_of_contract = False
            if c_start and current_date < c_start:
                is_out_of_contract = True
            elif c_end and current_date > c_end:
                is_out_of_contract = True

            if is_out_of_contract:
                # Scheduled hours for out-of-contract day
                out_day_hours = 0.0
                if calendar:
                    day_start = tz.localize(datetime.combine(current_date, time.min))
                    day_end = tz.localize(datetime.combine(current_date, time.max))
                    out_day_hours = calendar.get_work_hours_count(day_start, day_end, compute_leaves=False)
                else:
                    out_day_hours = day_std_hours
                
                if out_day_hours > 0.0:
                    total_out_of_contract_hours += out_day_hours
                    total_out_of_contract_days += min(1.0, out_day_hours / day_std_hours)
                
                current_date += relativedelta(days=1)
                continue

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

        # 6. Overtime calculation — reads from Standard Odoo 19 hr.attendance.overtime.line.
        #    Only lines that are:
        #      • status = 'approved'  (manager has validated them)
        #      • compensable_as_leave = False  (not converted to comp-off leave)
        #    are considered payable overtime for payroll.
        #    amount_rate on each line carries the rule rate (1.0, 1.5, 2.0 etc.) which
        #    the OT salary rule uses for weighted pay calculation.
        d_from = fields.Date.from_string(date_from) if not isinstance(date_from, date_type) else date_from
        d_to = fields.Date.from_string(date_to) if not isinstance(date_to, date_type) else date_to
        ot_lines = self.env['hr.attendance.overtime.line'].search([
            ('employee_id', '=', contract.employee_id.id),
            ('date', '>=', d_from),
            ('date', '<=', d_to),
            ('status', '=', 'approved'),
            ('compensable_as_leave', '=', False),
        ])
        net_overtime_hours = 0.0
        for ot_line in ot_lines:
            # manager_duration (manual_duration) > 0 means manager explicitly edited the approved amount
            approved_hrs = ot_line.manual_duration if ot_line.manual_duration > 0.0 else ot_line.duration
            net_overtime_hours += max(approved_hrs, 0.0)

        data = {
            'scheduled_hours': total_scheduled_hours,
            'scheduled_days': total_scheduled_days,
            'out_of_contract_hours': total_out_of_contract_hours,
            'out_of_contract_days': total_out_of_contract_days,
            'actual_hours': total_actual_hours,
            'validated_overtime_hours': net_overtime_hours,
            'overtime_hours_delta': net_overtime_hours,
            'overtime_lines': ot_lines,
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

    def _get_dynamic_overtime_values(self, contract, worked_days=None):
        """
        Dynamically calculates (base_hourly_wage, rate_percentage, total_hours)
        for draft payslips based on the live overtime rule/ruleset pay rates.
        Once payslip is validated, it uses the preserved rate on the line.
        """
        self.ensure_one()
        OtLine = self.env['hr.attendance.overtime.line']
        ot_lines = OtLine.search([
            ('employee_id', '=', contract.employee_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('status', '=', 'approved'),
            ('compensable_as_leave', '=', False),
        ])
        if not ot_lines:
            return 0.0, 100.0, 0.0

        # Base hourly wage from scheduled hours (WORK100 line)
        sched_hrs = 0.0
        if worked_days and hasattr(worked_days, 'WORK100') and worked_days.WORK100:
            sched_hrs = worked_days.WORK100.number_of_hours
        if not sched_hrs or sched_hrs <= 0.0:
            wd_line = self.worked_days_line_ids.filtered(lambda w: w.code == 'WORK100')
            if wd_line:
                sched_hrs = wd_line[0].number_of_hours
        if not sched_hrs or sched_hrs <= 0.0:
            cal = contract.resource_calendar_id
            sched_hrs = (cal.hours_per_day * 26.0) if cal and cal.hours_per_day else 208.0

        base_hourly = (contract.wage / sched_hrs) if sched_hrs > 0.0 else 0.0

        # Applicable ruleset
        ruleset = contract.ruleset_id or self.env['hr.attendance.overtime.ruleset'].search([
            ('company_id', 'in', [contract.company_id.id, False])
        ], limit=1)

        is_draft = (not self.state or self.state == 'draft')
        total_hours = 0.0
        weighted_rate_sum = 0.0

        for line in ot_lines:
            approved_hrs = line.manual_duration if line.manual_duration > 0.0 else line.duration
            if approved_hrs <= 0.0:
                continue

            if is_draft:
                # Draft stage: dynamically resolve CURRENT rule rate from applied rules or active ruleset
                paid_rules = line.rule_ids.filtered(lambda r: r.paid)
                if not paid_rules and ruleset:
                    paid_rules = ruleset.rule_ids.filtered(lambda r: r.paid)

                if paid_rules:
                    mode = ruleset.rate_combination_mode if ruleset else 'max'
                    if mode == 'sum':
                        current_rate = 1.0 + sum((r.amount_rate - 1.0) for r in paid_rules)
                    else:
                        current_rate = max(paid_rules.mapped('amount_rate'))
                else:
                    current_rate = line.amount_rate or 1.0

                # Synchronize line's stored amount_rate in DB so attendance records stay in sync
                if abs((line.amount_rate or 1.0) - current_rate) > 0.001:
                    line.sudo().write({'amount_rate': current_rate})

                rate_to_use = current_rate
            else:
                # Validated/Confirmed stage: keep preserved rate
                rate_to_use = line.amount_rate if line.amount_rate and line.amount_rate > 0.0 else 1.0

            total_hours += approved_hrs
            weighted_rate_sum += approved_hrs * rate_to_use

        if total_hours <= 0.0:
            return 0.0, 100.0, 0.0

        # Rate percentage to display on the payslip line (e.g. 1.5 -> 150.0%)
        effective_rate_pct = (weighted_rate_sum / total_hours) * 100.0

        return base_hourly, effective_rate_pct, total_hours

    def _get_dynamic_overtime_pay(self, contract, worked_days=None):
        """Returns total overtime pay amount."""
        base_hourly, rate_pct, hours = self._get_dynamic_overtime_values(contract, worked_days)
        return hours * base_hourly * (rate_pct / 100.0)

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
            out_days = data.get('out_of_contract_days', 0.0)
            out_hours = data.get('out_of_contract_hours', 0.0)

            # 1. Update or remove WORK100
            work100_found = False
            for line in list(res):
                if line.get('code') == 'WORK100' and line.get('contract_id') == contract.id:
                    if sched_days <= 0.01:
                        res.remove(line)
                    else:
                        line['number_of_days'] = sched_days
                        line['number_of_hours'] = sched_hours
                        work100_found = True
            if not work100_found and sched_days > 0.01:
                res.insert(0, {
                    'name': _('Normal Working Days'),
                    'sequence': 2,
                    'code': 'WORK100',
                    'description': _('Normal Working Days'),
                    'number_of_days': sched_days,
                    'number_of_hours': sched_hours,
                    'contract_id': contract.id,
                })

            # 2. Update or insert OUT_OF_CONTRACT
            if out_days > 0.01 or out_hours > 0.01:
                out_found = False
                for line in res:
                    if line.get('code') == 'OUT_OF_CONTRACT' and line.get('contract_id') == contract.id:
                        line['number_of_days'] = out_days
                        line['number_of_hours'] = out_hours
                        out_found = True
                if not out_found:
                    is_india = (getattr(contract, '_is_india_localization', None) and contract._is_india_localization()) or (contract.company_id and contract.company_id.country_id and contract.company_id.country_id.code == 'IN')
                    out_type_name = _('Out of Contract (India)') if is_india else _('Out of Contract')
                    res.insert(0, {
                        'name': out_type_name,
                        'sequence': 1,
                        'code': 'OUT_OF_CONTRACT',
                        'description': _('Out of Contract'),
                        'number_of_days': out_days,
                        'number_of_hours': out_hours,
                        'contract_id': contract.id,
                        'amount': 0.0,
                    })

            # 3. Leaves, Shortages, Overtime
            if data.get('unpaid_days', 0.0) > 0.01:
                res.append({
                    'name': _('Unpaid Leave'),
                    'sequence': 4,
                    'code': 'UNPAID',
                    'description': _('Unpaid Leave'),
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
                        'description': _('Attendance Shortage'),
                        'number_of_days': data.get('shortage_days', 0.0),
                        'number_of_hours': data['shortage_hours_delta'],
                        'contract_id': contract.id,
                    })
            # Overtime worked days line — uses Standard Odoo 19 overtime.line data.
            # Gate: any approved, payable OT lines exist for the period.
            # The salary rule OT reads rate-weighted pay directly from overtime.line,
            # so number_of_hours here is the total approved payable hours (informational).
            if data.get('overtime_hours_delta', 0.0) > 0.01:
                if not any(l.get('code') == 'OVERTIME' for l in res):
                    res.append({
                        'name': _('Overtime Hours'),
                        'sequence': 6,
                        'code': 'OVERTIME',
                        'description': _('Overtime Hours (Standard Odoo Ruleset)'),
                        'number_of_days': 0.0,
                        'number_of_hours': data['overtime_hours_delta'],
                        'contract_id': contract.id,
                    })
        return res
