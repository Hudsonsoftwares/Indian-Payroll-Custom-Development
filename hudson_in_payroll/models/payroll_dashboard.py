# -*- coding: utf-8 -*-
import calendar
from datetime import datetime, date
from odoo import api, fields, models, _

class HdsPayrollDashboard(models.Model):
    """
    Enterprise Indian HR & Payroll Dashboard Model.
    Provides real-time company-wide metrics, period controls, statutory compliance tracking,
    action required alerts, employee data health, and historical payroll cost trends.
    """
    _name = 'hds.payroll.dashboard'
    _description = 'Indian HR & Payroll Dashboard'

    name = fields.Char(string="Dashboard Name", default="Payroll Dashboard")
    financial_year_id = fields.Many2one('tds.financial.year', string="Financial Year", default=lambda self: self._default_financial_year())
    payroll_month_num = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string="Payroll Month", default=lambda self: str(fields.Date.today().month))

    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id)

    # 1. Primary KPI Metrics
    total_payroll_cost = fields.Monetary(string="Total Payroll Cost", currency_field='currency_id', compute='_compute_dashboard_metrics')
    total_net_pay = fields.Monetary(string="Total Net Wage", currency_field='currency_id', compute='_compute_dashboard_metrics')
    total_basic_wage = fields.Monetary(string="Total Basic Wage", currency_field='currency_id', compute='_compute_dashboard_metrics')
    avg_net_wage = fields.Monetary(string="Avg Net Wage", currency_field='currency_id', compute='_compute_dashboard_metrics')
    avg_basic_wage = fields.Monetary(string="Avg Basic Wage", currency_field='currency_id', compute='_compute_dashboard_metrics')
    avg_hours_per_day = fields.Float(string="Avg Hours/Day", compute='_compute_dashboard_metrics')
    fte_count = fields.Float(string="FTE", compute='_compute_dashboard_metrics')
    active_employee_count = fields.Integer(string="Active Employees", compute='_compute_dashboard_metrics')
    tds_this_month = fields.Monetary(string="TDS This Month", currency_field='currency_id', compute='_compute_dashboard_metrics')
    pending_actions_count = fields.Integer(string="Pending Actions", compute='_compute_dashboard_metrics')

    # 2. Action Required Counters
    missing_pan_count = fields.Integer(string="Missing PAN Count", compute='_compute_dashboard_metrics')
    missing_bank_count = fields.Integer(string="Missing Bank Count", compute='_compute_dashboard_metrics')
    pending_declarations_count = fields.Integer(string="Pending Declarations Count", compute='_compute_dashboard_metrics')
    attendance_pending_count = fields.Integer(string="Attendance Pending Count", compute='_compute_dashboard_metrics')
    missing_salary_count = fields.Integer(string="Missing Salary Info Count", compute='_compute_dashboard_metrics')

    # 3. Employee Data Health Percentages
    pan_health_pct = fields.Float(string="PAN Completeness %", compute='_compute_dashboard_metrics')
    bank_health_pct = fields.Float(string="Bank Details Completeness %", compute='_compute_dashboard_metrics')
    aadhaar_health_pct = fields.Float(string="Aadhaar Completeness %", compute='_compute_dashboard_metrics')
    contact_health_pct = fields.Float(string="Emergency Contact Completeness %", compute='_compute_dashboard_metrics')

    # 4. Tax Regime Distribution
    old_regime_count = fields.Integer(string="Old Regime Employees", compute='_compute_dashboard_metrics')
    new_regime_count = fields.Integer(string="New Regime Employees", compute='_compute_dashboard_metrics')
    tds_ytd_total = fields.Monetary(string="TDS YTD Total", currency_field='currency_id', compute='_compute_dashboard_metrics')

    # 5. Statutory Liabilities
    epf_total_liability = fields.Monetary(string="EPF Total Liability", currency_field='currency_id', compute='_compute_dashboard_metrics')
    esic_total_liability = fields.Monetary(string="ESIC Total Liability", currency_field='currency_id', compute='_compute_dashboard_metrics')
    pt_total_liability = fields.Monetary(string="Professional Tax Liability", currency_field='currency_id', compute='_compute_dashboard_metrics')

    # 6. Statutory Compliance & Identifier Status
    epf_complete_count = fields.Integer(string="EPF Complete UAN Count", compute='_compute_dashboard_metrics')
    epf_missing_count = fields.Integer(string="EPF Missing UAN Count", compute='_compute_dashboard_metrics')
    esic_complete_count = fields.Integer(string="ESIC Complete IP Count", compute='_compute_dashboard_metrics')
    esic_missing_count = fields.Integer(string="ESIC Missing IP Count", compute='_compute_dashboard_metrics')
    lwf_complete_count = fields.Integer(string="LWF Complete Number Count", compute='_compute_dashboard_metrics')
    lwf_missing_count = fields.Integer(string="LWF Missing Number Count", compute='_compute_dashboard_metrics')
    statutory_data_errors_count = fields.Integer(string="Statutory Data Errors Count", compute='_compute_dashboard_metrics')
    statutory_ready_count = fields.Integer(string="Statutory Ready Count", compute='_compute_dashboard_metrics')

    # 7. Workforce Movement
    new_joiners_count = fields.Integer(string="New Joiners Count", compute='_compute_dashboard_metrics')
    exits_count = fields.Integer(string="Exits Count", compute='_compute_dashboard_metrics')

    # 8. Final Settlements Due KPI & Status Breakdown
    final_settlements_due_count = fields.Integer(string="Final Settlements Due This Month", compute='_compute_dashboard_metrics')
    final_settlement_draft_count = fields.Integer(string="Draft Settlements", compute='_compute_dashboard_metrics')
    final_settlement_review_count = fields.Integer(string="Under Review Settlements", compute='_compute_dashboard_metrics')
    final_settlement_approved_count = fields.Integer(string="Approved Settlements", compute='_compute_dashboard_metrics')
    final_settlement_paid_count = fields.Integer(string="Paid Settlements", compute='_compute_dashboard_metrics')

    # 9. Rich HTML Dashboard Canvas
    dashboard_html = fields.Html(string="Dashboard Canvas", compute='_compute_dashboard_html', sanitize=False)

    @api.model
    def _default_financial_year(self):
        today = fields.Date.today()
        fy = self.env['tds.financial.year'].search([
            ('start_date', '<=', today), ('end_date', '>=', today)
        ], limit=1)
        if not fy:
            fy = self.env['tds.financial.year'].search([], order='id desc', limit=1)
        return fy.id if fy else False

    @staticmethod
    def _has_bank_account(emp):
        if getattr(emp, 'bank_account_id', False):
            return True
        if getattr(emp, 'primary_bank_account_id', False):
            return True
        if getattr(emp, 'bank_account_ids', False):
            return bool(emp.bank_account_ids)
        if getattr(getattr(emp, 'work_contact_id', None), 'bank_account_id', False):
            return True
        if getattr(getattr(emp, 'address_home_id', None), 'bank_account_id', False):
            return True
        return False

    @api.depends('financial_year_id', 'payroll_month_num')
    def _compute_dashboard_metrics(self):
        for rec in self:
            if not rec.financial_year_id:
                rec.financial_year_id = rec._default_financial_year()
            today = fields.Date.today()
            m_num = int(rec.payroll_month_num or today.month)
            year = today.year
            try:
                if rec.financial_year_id and getattr(rec.financial_year_id, 'start_date', False):
                    fy_s_year = rec.financial_year_id.start_date.year
                    fy_e_year = rec.financial_year_id.end_date.year
                    year = fy_s_year if m_num >= 4 else fy_e_year
            except Exception as err:
                _logger.warning("Safely handled Financial Year date resolution error in dashboard compute: %s", err)
                year = today.year

            month_start = date(year, m_num, 1)
            month_end = date(year, m_num, calendar.monthrange(year, m_num)[1])

            # Active Employees & Data Health
            emp_model = self.env['hr.employee']
            active_emps = emp_model.search([('active', '=', True)])
            tot_emp = len(active_emps) or 1
            rec.active_employee_count = len(active_emps)

            pan_count = len(active_emps.filtered(lambda e: bool(getattr(e, 'hds_in_pan', False) or getattr(e, 'pan_no', False) or getattr(e, 'pan', False))))
            bank_count = len(active_emps.filtered(lambda e: self._has_bank_account(e)))
            aadhaar_count = len(active_emps.filtered(lambda e: bool(getattr(e, 'identification_id', False) or getattr(e, 'aadhaar_no', False))))
            contact_count = len(active_emps.filtered(lambda e: bool(getattr(e, 'emergency_contact', False) or getattr(e, 'mobile_phone', False) or getattr(e, 'work_phone', False))))

            rec.missing_pan_count = len(active_emps.filtered(lambda e: not (getattr(e, 'hds_in_pan', False) or getattr(e, 'pan_no', False) or getattr(e, 'pan', False))))
            rec.missing_bank_count = len(active_emps.filtered(lambda e: not self._has_bank_account(e)))
            rec.pan_health_pct = round((pan_count / tot_emp) * 100.0, 1)
            rec.bank_health_pct = round((bank_count / tot_emp) * 100.0, 1)
            rec.aadhaar_health_pct = round((aadhaar_count / tot_emp) * 100.0, 1)
            rec.contact_health_pct = round((contact_count / tot_emp) * 100.0, 1)

            # Statutory Compliance & Identifier Evaluation
            from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
            comp_service = StatutoryComplianceValidationService(self.env)

            epf_complete = 0
            epf_missing = 0
            esic_complete = 0
            esic_missing = 0
            lwf_complete = 0
            lwf_missing = 0
            stat_errors = set()
            stat_ready = set()

            for emp in active_emps:
                res = comp_service.validate_employee_all(emp)
                if getattr(emp, 'hds_in_epf_applicable', False):
                    if res['epf_valid']:
                        epf_complete += 1
                    else:
                        epf_missing += 1
                        stat_errors.add(emp.id)

                if getattr(emp, 'hds_in_esic_applicable', False):
                    if res['esic_valid']:
                        esic_complete += 1
                    else:
                        esic_missing += 1
                        stat_errors.add(emp.id)

                if getattr(emp, 'hds_in_lwf_applicable', False):
                    if res['lwf_valid']:
                        lwf_complete += 1
                    else:
                        lwf_missing += 1
                        stat_errors.add(emp.id)

                if not res['pan_valid'] or not res['bank_valid']:
                    stat_errors.add(emp.id)

                if res['is_compliant']:
                    stat_ready.add(emp.id)

            rec.epf_complete_count = epf_complete
            rec.epf_missing_count = epf_missing
            rec.esic_complete_count = esic_complete
            rec.esic_missing_count = esic_missing
            rec.lwf_complete_count = lwf_complete
            rec.lwf_missing_count = lwf_missing
            rec.statutory_data_errors_count = len(stat_errors)
            rec.statutory_ready_count = len(stat_ready)

            # Contract & Salary info missing count (safely guarded)
            rec.missing_salary_count = len(active_emps.filtered(lambda e: not getattr(e, 'contract_id', False) or float(getattr(getattr(e, 'contract_id', None), 'wage', 0.0) or 0.0) <= 0.0))

            # New Joiners & Exits for period (safely checking field existence)
            emp_fields = emp_model._fields
            join_field = next((f for f in ('first_contract_date', 'hds_in_doj', 'joining_date') if f in emp_fields), None)
            if join_field:
                rec.new_joiners_count = emp_model.search_count([
                    (join_field, '>=', month_start),
                    (join_field, '<=', month_end),
                ])
            else:
                rec.new_joiners_count = 0

            exit_field = next((f for f in ('departure_date', 'hds_in_dol', 'resign_date') if f in emp_fields), None)
            if exit_field:
                rec.exits_count = emp_model.search_count([
                    (exit_field, '>=', month_start),
                    (exit_field, '<=', month_end),
                ])
            else:
                rec.exits_count = 0

            # Final Settlements Due for period (dynamically calculated if final.settlement model present)
            if 'final.settlement' in self.env:
                settlement_model = self.env['final.settlement']
                settlement_domain = [
                    ('state', '!=', 'cancel'),
                    ('last_working_day', '>=', month_start),
                    ('last_working_day', '<=', month_end),
                ]
                rec.final_settlements_due_count = settlement_model.search_count(settlement_domain)
                rec.final_settlement_draft_count = settlement_model.search_count(settlement_domain + [('state', '=', 'draft')])
                rec.final_settlement_review_count = settlement_model.search_count(settlement_domain + [('state', '=', 'under_review')])
                rec.final_settlement_approved_count = settlement_model.search_count(settlement_domain + [('state', '=', 'approved')])
                rec.final_settlement_paid_count = settlement_model.search_count(settlement_domain + [('state', '=', 'paid')])
            else:
                rec.final_settlements_due_count = 0
                rec.final_settlement_draft_count = 0
                rec.final_settlement_review_count = 0
                rec.final_settlement_approved_count = 0
                rec.final_settlement_paid_count = 0

            # Payslips and Payroll Financial Metrics for period (Company-aware, Non-cancelled & Deduplicated)
            company_domain = [('company_id', 'in', self.env.companies.ids)]
            period_domain = [
                ('date_from', '<=', month_end),
                ('date_to', '>=', month_start),
                ('state', '!=', 'cancel'),
            ] + company_domain
            all_slips = self.env['hr.payslip'].search(period_domain)

            # Deduplicate by employee so multiple draft or re-computed slips don't double count
            state_priority = {'paid': 4, 'done': 3, 'verify': 2, 'draft': 1}
            latest_slips_by_emp = {}
            for slip in all_slips.sorted(key=lambda s: (state_priority.get(s.state, 0), s.id), reverse=True):
                if slip.employee_id.id not in latest_slips_by_emp:
                    latest_slips_by_emp[slip.employee_id.id] = slip
            slips = self.env['hr.payslip'].browse([s.id for s in latest_slips_by_emp.values()])

            rec.attendance_pending_count = len(slips.filtered(lambda s: getattr(s, 'has_attendance_discrepancy', False) or s.state in ('draft', 'verify')))

            tot_gross = 0.0
            tot_net = 0.0
            tot_basic = 0.0
            tot_tds = 0.0
            tot_epf = 0.0
            tot_esi = 0.0
            tot_pt = 0.0
            tot_hours = 0.0
            tot_days = 0.0

            for slip in slips:
                gross_val = float(getattr(slip, 'gross_amount', None) or getattr(slip, 'gross_wage', 0.0) or 0.0)
                net_val = float(getattr(slip, 'net_amount', None) or getattr(slip, 'net_wage', 0.0) or 0.0)
                if not gross_val:
                    for line in slip.line_ids:
                        if (line.code or '').upper() == 'GROSS':
                            gross_val = abs(float(line.total or 0.0))
                            break
                if not net_val:
                    for line in slip.line_ids:
                        if (line.code or '').upper() == 'NET':
                            net_val = abs(float(line.total or 0.0))
                            break

                tot_gross += gross_val
                tot_net += net_val

                for line in slip.line_ids:
                    code = (line.code or '').upper()
                    amt = float(line.total or 0.0)
                    if code == 'BASIC':
                        tot_basic += abs(amt)
                    elif code in ('TDS', 'INCOME_TAX', 'IT', 'HDS_IN_TDS'):
                        tot_tds += abs(amt)
                    elif code in ('PF', 'EPF', 'EE_PF', 'ER_PF', 'EMPLOYER_EPF', 'EPS', 'EPF_SHARE', 'EDLI', 'EPF_ADMIN', 'EDLI_ADMIN'):
                        tot_epf += abs(amt)
                    elif code in ('ESI', 'ESIC', 'ESIC_EE', 'ESIC_ER', 'EE_ESI', 'ER_ESI'):
                        tot_esi += abs(amt)
                    elif code in ('PT', 'PROF_TAX'):
                        tot_pt += abs(amt)

                for wd in slip.worked_days_line_ids:
                    tot_hours += float(wd.number_of_hours or 0.0)
                    tot_days += float(wd.number_of_days or 0.0)

            rec.total_payroll_cost = tot_gross if tot_gross > 0 else tot_net
            rec.total_net_pay = tot_net
            rec.total_basic_wage = tot_basic
            rec.avg_net_wage = (tot_net / len(slips)) if slips else 0.0
            rec.avg_basic_wage = (tot_basic / len(slips)) if slips else 0.0
            rec.avg_hours_per_day = round(tot_hours / tot_days, 1) if tot_days > 0 else 8.0
            rec.fte_count = float(len(slips)) if slips else float(tot_emp)
            rec.tds_this_month = tot_tds
            rec.epf_total_liability = tot_epf
            rec.esic_total_liability = tot_esi
            rec.pt_total_liability = tot_pt

            # YTD TDS computation for FY
            fy_start = rec.financial_year_id.start_date if rec.financial_year_id else date(year, 4, 1)
            ytd_slips = self.env['hr.payslip'].search([
                ('date_from', '>=', fy_start),
                ('date_to', '<=', month_end),
                ('state', 'in', ('done', 'paid'))
            ])
            ytd_tds_val = 0.0
            for ys in ytd_slips:
                for line in ys.line_ids:
                    if (line.code or '').upper() in ('TDS', 'INCOME_TAX', 'IT'):
                        ytd_tds_val += abs(float(line.total or 0.0))
            rec.tds_ytd_total = ytd_tds_val

            # Tax Declarations & Regime Distribution
            decl_model = self.env['tds.employee.declaration']
            rec.pending_declarations_count = decl_model.search_count([
                ('state', 'in', ('submitted', 'proof_submitted', 'proof_under_review'))
            ])
            rec.old_regime_count = decl_model.search_count([('regime_code', '=', 'old')])
            rec.new_regime_count = decl_model.search_count([('regime_code', '=', 'new')])

            # Total Action Required Items
            rec.pending_actions_count = rec.missing_pan_count + rec.missing_bank_count + rec.pending_declarations_count + rec.attendance_pending_count + rec.missing_salary_count

    @api.depends('financial_year_id', 'payroll_month_num', 'active_employee_count', 'total_payroll_cost', 'total_net_pay', 'tds_this_month', 'pending_actions_count', 'final_settlements_due_count')
    def _compute_dashboard_html(self):
        for rec in self:
            currency_symbol = rec.currency_id.symbol or '₹'
            month_name = dict(rec._fields['payroll_month_num'].selection).get(rec.payroll_month_num, 'August')
            fy_name = rec.financial_year_id.name if rec.financial_year_id else 'FY 2026-27'

            # Fetch New Joiners for selected month
            today = fields.Date.today()
            m_num = int(rec.payroll_month_num or today.month)
            year = today.year
            if rec.financial_year_id and rec.financial_year_id.start_date:
                fy_s_year = rec.financial_year_id.start_date.year
                fy_e_year = rec.financial_year_id.end_date.year
                year = fy_s_year if m_num >= 4 else fy_e_year

            month_start = date(year, m_num, 1)
            month_end = date(year, m_num, calendar.monthrange(year, m_num)[1])

            emp_fields = self.env['hr.employee']._fields
            join_field = next((f for f in ('joining_date', 'date_of_joining', 'hds_in_doj', 'first_contract_date', 'contract_date_start', 'create_date') if f in emp_fields), None)

            joiners = self.env['hr.employee']
            if join_field:
                joiners = self.env['hr.employee'].search([
                    (join_field, '>=', month_start),
                    (join_field, '<=', month_end),
                ], limit=5, order=f'{join_field} desc')

            joiner_rows_html = ""
            if joiners:
                for j in joiners:
                    j_date_val = getattr(j, join_field, False) if join_field else False
                    j_date = j_date_val.strftime('%d %b') if (j_date_val and hasattr(j_date_val, 'strftime')) else 'N/A'
                    dept = j.department_id.name if j.department_id else 'General'
                    has_pan = bool(getattr(j, 'hds_in_pan', False) or getattr(j, 'pan_no', False) or getattr(j, 'pan', False))
                    has_bank = self._has_bank_account(j)

                    if not has_pan:
                        status_chip = f'<a href="/odoo/hr.employee/{j.id}" class="o_hds_dashboard_card_clickable" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">🔴 PAN Missing &rarr; Fix</a>'
                    elif not has_bank:
                        status_chip = f'<a href="/odoo/hr.employee/{j.id}" class="o_hds_dashboard_card_clickable" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">🟠 Bank Missing &rarr; Fix</a>'
                    else:
                        status_chip = f'<a href="/odoo/hr.employee/{j.id}" class="o_hds_dashboard_card_clickable" style="background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">🟢 Payroll Ready</a>'

                    joiner_rows_html += f"""
                    <tr style="border-bottom: 1px solid var(--hds-row-border); transition: background-color 0.15s ease;">
                        <td style="padding: 10px 8px; font-weight: 600;">
                            <a href="/odoo/hr.employee/{j.id}" class="o_hds_dashboard_card_clickable" style="color: #818cf8; text-decoration: none; font-weight: 700;">
                                {j.name}
                            </a>
                        </td>
                        <td class="hds-text-secondary" style="padding: 10px 8px;">{j_date}</td>
                        <td class="hds-text-secondary" style="padding: 10px 8px;">{dept}</td>
                        <td style="padding: 10px 8px;">{status_chip}</td>
                    </tr>
                    """
            else:
                joiner_rows_html = """
                <tr>
                    <td colspan="4" class="hds-text-muted" style="padding: 18px; text-align: center; font-style: italic;">
                        No new joiners recorded for this payroll period.
                    </td>
                </tr>
                """

            # 6-Month Payroll Trend Visualizer Data (Payrun Styled)
            trend_bars_html = ""
            for i in range(5, -1, -1):
                t_month = (m_num - i - 1) % 12 + 1
                t_year = year if (m_num - i) > 0 else year - 1
                t_m_name = calendar.month_abbr[t_month]
                t_start = date(t_year, t_month, 1)
                t_end = date(t_year, t_month, calendar.monthrange(t_year, t_month)[1])

                t_slips = self.env['hr.payslip'].search([
                    ('date_from', '>=', t_start), ('date_to', '<=', t_end)
                ])
                t_cost = sum(float(getattr(s, 'gross_amount', None) or getattr(s, 'gross_wage', None) or getattr(s, 'net_amount', None) or getattr(s, 'net_wage', 0.0) or 0.0) for s in t_slips)
                bar_height = min(100, max(15, int((t_cost / (rec.total_payroll_cost or 1.0)) * 70))) if rec.total_payroll_cost > 0 else 20
                cost_lbl = f"{currency_symbol} {t_cost/100000:.1f}L" if t_cost >= 100000 else f"{currency_symbol} {t_cost:,.0f}"

                trend_bars_html += f"""
                <div style="display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1;">
                    <div class="hds-text-primary" style="font-size: 11px; font-weight: 700;">{cost_lbl}</div>
                    <div style="width: 100%; max-width: 36px; background: linear-gradient(180deg, #c084fc 0%, #7c3aed 100%); height: {bar_height}px; border-radius: 6px 6px 0 0; box-shadow: 0 2px 8px rgba(124, 58, 237, 0.25);"></div>
                    <div class="hds-text-muted" style="font-size: 10px; font-weight: 600;">{t_m_name}</div>
                </div>
                """

            rec.dashboard_html = f"""
            <style>
                :root, body:not(.o_dark_mode) {{
                    --hds-dash-bg: transparent;
                    --hds-card-bg: #ffffff;
                    --hds-card-border: #e2e8f0;
                    --hds-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
                    --hds-card-hover-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
                    --hds-subcard-bg: #f8fafc;
                    --hds-subcard-border: #cbd5e1;
                    --hds-subcard-hover-bg: #f1f5f9;
                    --hds-text-primary: #0f172a;
                    --hds-text-secondary: #475569;
                    --hds-text-muted: #64748b;
                    --hds-table-head: #f8fafc;
                    --hds-row-border: #f1f5f9;
                    --hds-row-hover: #f8fafc;
                    --hds-track-bg: #e2e8f0;
                    --hds-alert-bg: #fff1f2;
                    --hds-alert-border: #fecdd3;
                    --hds-alert-header: #9f1239;
                }}

                .o_dark_mode,
                [data-color-mode="dark"],
                .o_web_client.o_dark_mode,
                body.o_dark_mode {{
                    --hds-dash-bg: transparent;
                    --hds-card-bg: #1e293b;
                    --hds-card-border: rgba(255, 255, 255, 0.12);
                    --hds-card-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
                    --hds-card-hover-shadow: 0 8px 24px rgba(0, 0, 0, 0.55);
                    --hds-subcard-bg: rgba(15, 23, 42, 0.65);
                    --hds-subcard-border: rgba(255, 255, 255, 0.14);
                    --hds-subcard-hover-bg: rgba(255, 255, 255, 0.06);
                    --hds-text-primary: #f8fafc;
                    --hds-text-secondary: #cbd5e1;
                    --hds-text-muted: #94a3b8;
                    --hds-table-head: rgba(15, 23, 42, 0.85);
                    --hds-row-border: rgba(255, 255, 255, 0.08);
                    --hds-row-hover: rgba(255, 255, 255, 0.04);
                    --hds-track-bg: rgba(255, 255, 255, 0.12);
                    --hds-alert-bg: rgba(225, 29, 72, 0.12);
                    --hds-alert-border: rgba(225, 29, 72, 0.32);
                    --hds-alert-header: #fda4af;
                }}

                @media (prefers-color-scheme: dark) {{
                    :root:not(.o_light_mode) {{
                        --hds-dash-bg: transparent;
                        --hds-card-bg: #1e293b;
                        --hds-card-border: rgba(255, 255, 255, 0.12);
                        --hds-card-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
                        --hds-card-hover-shadow: 0 8px 24px rgba(0, 0, 0, 0.55);
                        --hds-subcard-bg: rgba(15, 23, 42, 0.65);
                        --hds-subcard-border: rgba(255, 255, 255, 0.14);
                        --hds-subcard-hover-bg: rgba(255, 255, 255, 0.06);
                        --hds-text-primary: #f8fafc;
                        --hds-text-secondary: #cbd5e1;
                        --hds-text-muted: #94a3b8;
                        --hds-table-head: rgba(15, 23, 42, 0.85);
                        --hds-row-border: rgba(255, 255, 255, 0.08);
                        --hds-row-hover: rgba(255, 255, 255, 0.04);
                        --hds-track-bg: rgba(255, 255, 255, 0.12);
                        --hds-alert-bg: rgba(225, 29, 72, 0.12);
                        --hds-alert-border: rgba(225, 29, 72, 0.32);
                        --hds-alert-header: #fda4af;
                    }}
                }}

                .hds-dash-card {{
                    background-color: var(--hds-card-bg) !important;
                    border: 1px solid var(--hds-card-border) !important;
                    border-radius: 12px !important;
                    box-shadow: var(--hds-card-shadow) !important;
                    transition: transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.18s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.18s ease !important;
                }}
                .hds-dash-card:hover {{
                    transform: translateY(-2px) !important;
                    box-shadow: var(--hds-card-hover-shadow) !important;
                }}

                .hds-subcard {{
                    background-color: var(--hds-subcard-bg) !important;
                    border: 1px solid var(--hds-subcard-border) !important;
                    border-radius: 8px !important;
                    transition: all 0.15s ease-in-out !important;
                }}
                .hds-subcard:hover {{
                    background-color: var(--hds-subcard-hover-bg) !important;
                    transform: translateY(-1px) !important;
                }}

                .hds-text-primary {{
                    color: var(--hds-text-primary) !important;
                }}
                .hds-text-secondary {{
                    color: var(--hds-text-secondary) !important;
                }}
                .hds-text-muted {{
                    color: var(--hds-text-muted) !important;
                }}
            </style>

            <div style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; width: 100%; box-sizing: border-box;">

                <!-- 1. PRIMARY KPI CARDS GRID (PAYRUN PALETTE) -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 22px;">

                    <!-- Card 1: Total Payroll Cost (Payrun Employer Cost - Purple) -->
                    <a href="/odoo/action-hudson_payroll_base.action_hr_payslip" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #c084fc !important;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #c084fc !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-briefcase me-1"/> Total Payroll Cost
                            </span>
                            <span style="font-size: 11px; color: #c084fc; font-weight: 600;">View Slips &rarr;</span>
                        </div>
                        <div class="hds-text-primary" style="font-size: 24px; font-weight: 800; margin: 8px 0; letter-spacing: -0.5px;">
                            {currency_symbol} {rec.total_payroll_cost:,.2f}
                        </div>
                        <div class="hds-text-muted" style="font-size: 11px; font-weight: 500;">
                            Period: {month_name} ({fy_name})
                        </div>
                    </a>

                    <!-- Card 2: Net Salary Payable (Payrun Net - Emerald Green) -->
                    <a href="/odoo/action-hudson_payroll_base.action_hr_payslip" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #4ade80 !important;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #4ade80 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-credit-card me-1"/> Net Salary Payable
                            </span>
                            <span style="font-size: 11px; color: #4ade80; font-weight: 600;">Disbursement &rarr;</span>
                        </div>
                        <div class="hds-text-primary" style="font-size: 24px; font-weight: 800; margin: 8px 0; letter-spacing: -0.5px;">
                            {currency_symbol} {rec.total_net_pay:,.2f}
                        </div>
                        <div style="font-size: 11px; color: #4ade80; font-weight: 600;">
                            Disbursable Amount
                        </div>
                    </a>

                    <!-- Card 3: Active Employees (Payrun Gross / Workforce - Sky Blue) -->
                    <a href="/odoo/action-hr.open_view_employee_list_my" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #38bdf8 !important;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #38bdf8 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-users me-1"/> Active Employees
                            </span>
                            <span style="font-size: 11px; color: #38bdf8; font-weight: 600;">Employees &rarr;</span>
                        </div>
                        <div class="hds-text-primary" style="font-size: 24px; font-weight: 800; margin: 8px 0; letter-spacing: -0.5px;">
                            {rec.active_employee_count}
                        </div>
                        <div style="font-size: 11px; color: #38bdf8; font-weight: 600;">
                            Active Workforce
                        </div>
                    </a>

                    <!-- Card 4: TDS This Month (Payrun TDS - Indigo) -->
                    <a href="/odoo/action-hudson_in_payroll.action_dashboard_pending_declarations" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #818cf8 !important;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #818cf8 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-shield me-1"/> TDS This Month
                            </span>
                            <span style="font-size: 11px; color: #818cf8; font-weight: 600;">Declarations &rarr;</span>
                        </div>
                        <div class="hds-text-primary" style="font-size: 24px; font-weight: 800; margin: 8px 0; letter-spacing: -0.5px;">
                            {currency_symbol} {rec.tds_this_month:,.2f}
                        </div>
                        <div style="font-size: 11px; color: #818cf8; font-weight: 600;">
                            YTD: {currency_symbol} {rec.tds_ytd_total:,.2f}
                        </div>
                    </a>

                    <!-- Card 5: Pending Actions (Payrun Anomaly / Shortage - Amber) -->
                    <a href="/odoo/action-hudson_in_payroll.action_dashboard_missing_pan_employees" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #fbbf24 !important;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #fbbf24 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-exclamation-circle me-1"/> Pending Actions
                            </span>
                            <span style="font-size: 11px; color: #fbbf24; font-weight: 600;">Fix Now &rarr;</span>
                        </div>
                        <div style="font-size: 24px; font-weight: 800; margin: 8px 0; color: #fbbf24; letter-spacing: -0.5px;">
                            {rec.pending_actions_count}
                        </div>
                        <div style="font-size: 11px; color: #fbbf24; font-weight: 600;">
                            Requires HR Attention
                        </div>
                    </a>

                    <!-- Card 6: Final Settlements Due (Payrun Danger / Settlements - Rose) -->
                    <a href="/odoo/action-hudson_in_final_settlement.action_dashboard_final_settlements_due" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #f87171 !important;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #f87171 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-user-times me-1"/> Final Settlements Due
                            </span>
                            <span style="font-size: 11px; color: #f87171; font-weight: 600;">View Due &rarr;</span>
                        </div>
                        <div style="font-size: 24px; font-weight: 800; margin: 8px 0; color: #f87171; letter-spacing: -0.5px;">
                            {rec.final_settlements_due_count}
                        </div>
                        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; font-size: 10px;">
                            <span style="background: rgba(148, 163, 184, 0.15); color: var(--hds-text-secondary); border: 1px solid rgba(148, 163, 184, 0.3); padding: 2px 7px; border-radius: 10px; font-weight: 600;">📝 Draft: {rec.final_settlement_draft_count}</span>
                            <span style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); padding: 2px 7px; border-radius: 10px; font-weight: 600;">🔍 Review: {rec.final_settlement_review_count}</span>
                            <span style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 7px; border-radius: 10px; font-weight: 600;">✅ Appr: {rec.final_settlement_approved_count}</span>
                            <span style="background: rgba(74, 222, 128, 0.15); color: #4ade80; border: 1px solid rgba(74, 222, 128, 0.3); padding: 2px 7px; border-radius: 10px; font-weight: 600;">💰 Paid: {rec.final_settlement_paid_count}</span>
                        </div>
                    </a>
                </div>

                <!-- 2. ACTION REQUIRED SECTION (HIGH VISIBILITY ALERTS) -->
                <div class="hds-dash-card" style="padding: 18px; margin-bottom: 22px; background-color: var(--hds-alert-bg) !important; border: 1px solid var(--hds-alert-border) !important;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
                        <div style="font-size: 15px; font-weight: 700; color: var(--hds-alert-header); display: flex; align-items: center; gap: 8px;">
                            <i class="fa fa-exclamation-triangle" style="color: #f87171;"/> Action Required
                        </div>
                        <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">Immediate HR Verification Required (Click card to fix)</div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
                        <!-- Missing PAN -->
                        <a href="/odoo/action-hudson_in_payroll.action_dashboard_missing_pan_employees" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px 14px; border-left: 4px solid #ef4444 !important;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="font-size: 12px; font-weight: 700; color: #f87171;">
                                    <i class="fa fa-id-card me-1"/> {rec.missing_pan_count} Employees Missing PAN
                                </div>
                                <span style="font-size: 12px; color: #ef4444; font-weight: 700;">&rarr;</span>
                            </div>
                            <div class="hds-text-muted" style="font-size: 11px; margin-top: 4px;">Impacts 20% flat TDS rate u/s 206AA &bull; <u style="color: #f87171;">Click to fix</u></div>
                        </a>

                        <!-- Missing Bank -->
                        <a href="/odoo/action-hudson_in_payroll.action_dashboard_missing_bank_employees" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px 14px; border-left: 4px solid #f97316 !important;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="font-size: 12px; font-weight: 700; color: #fb923c;">
                                    <i class="fa fa-university me-1"/> {rec.missing_bank_count} Employees Missing Bank
                                </div>
                                <span style="font-size: 12px; color: #f97316; font-weight: 700;">&rarr;</span>
                            </div>
                            <div class="hds-text-muted" style="font-size: 11px; margin-top: 4px;">Blocks automated salary advice file &bull; <u style="color: #fb923c;">Click to fix</u></div>
                        </a>

                        <!-- Pending Declarations -->
                        <a href="/odoo/action-hudson_in_payroll.action_dashboard_pending_declarations" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px 14px; border-left: 4px solid #f59e0b !important;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="font-size: 12px; font-weight: 700; color: #fbbf24;">
                                    <i class="fa fa-file-text-o me-1"/> {rec.pending_declarations_count} Declarations Pending
                                </div>
                                <span style="font-size: 12px; color: #f59e0b; font-weight: 700;">&rarr;</span>
                            </div>
                            <div class="hds-text-muted" style="font-size: 11px; margin-top: 4px;">Pending Tax Firm / HR verification &bull; <u style="color: #fbbf24;">Click to review</u></div>
                        </a>

                        <!-- Attendance / Payslip Exceptions -->
                        <a href="/odoo/action-hudson_in_payroll.action_dashboard_attendance_exceptions" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px 14px; border-left: 4px solid #8b5cf6 !important;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="font-size: 12px; font-weight: 700; color: #c084fc;">
                                    <i class="fa fa-clock-o me-1"/> {rec.attendance_pending_count} Slip Exceptions
                                </div>
                                <span style="font-size: 12px; color: #8b5cf6; font-weight: 700;">&rarr;</span>
                            </div>
                            <div class="hds-text-muted" style="font-size: 11px; margin-top: 4px;">Draft status or discrepancy pending &bull; <u style="color: #c084fc;">Click to view</u></div>
                        </a>
                    </div>
                </div>

                <!-- 3. MIDDLE ROW: NEW JOINERS & EMPLOYEE DATA HEALTH -->
                <div style="display: grid; grid-template-columns: 3fr 2fr; gap: 18px; margin-bottom: 22px;">

                    <!-- New Joiners Card -->
                    <div class="hds-dash-card" style="padding: 18px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid var(--hds-row-border); padding-bottom: 8px;">
                            <div class="hds-text-primary" style="font-size: 14px; font-weight: 700; display: flex; align-items: center; gap: 8px;">
                                <i class="fa fa-user-plus" style="color: #818cf8;"/> New Joiners ({month_name})
                            </div>
                            <a href="/odoo/action-hudson_in_payroll.action_dashboard_new_joiners" class="o_hds_dashboard_card_clickable" style="text-decoration: none; font-size: 11px; font-weight: 700; color: #818cf8; background: rgba(129, 140, 248, 0.15); border: 1px solid rgba(129, 140, 248, 0.3); padding: 4px 10px; border-radius: 12px; display: inline-flex; align-items: center; gap: 4px;">
                                Count: {rec.new_joiners_count} &rarr;
                            </a>
                        </div>
                        <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                            <thead>
                                <tr style="background: var(--hds-table-head); color: var(--hds-text-muted); text-align: left; font-size: 11px;">
                                    <th style="padding: 8px 10px; border-radius: 6px 0 0 6px;">Employee Name</th>
                                    <th style="padding: 8px 10px;">Joining Date</th>
                                    <th style="padding: 8px 10px;">Department</th>
                                    <th style="padding: 8px 10px; border-radius: 0 6px 6px 0;">Readiness</th>
                                </tr>
                            </thead>
                            <tbody>
                                {joiner_rows_html}
                            </tbody>
                        </table>
                    </div>

                    <!-- Employee Data Health Card -->
                    <div class="hds-dash-card" style="padding: 18px;">
                        <div class="hds-text-primary" style="font-size: 14px; font-weight: 700; margin-bottom: 15px; border-bottom: 1px solid var(--hds-row-border); padding-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <i class="fa fa-heartbeat" style="color: #4ade80;"/> Employee Data Health
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 14px;">

                            <!-- PAN Completeness (Indigo) -->
                            <a href="/odoo/action-hudson_in_payroll.action_dashboard_missing_pan_employees" class="o_hds_dashboard_card_clickable" style="text-decoration: none; color: inherit; display: block; padding: 2px 4px;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; margin-bottom: 5px;">
                                    <span class="hds-text-secondary">PAN Completeness</span>
                                    <span style="color: #818cf8;">{rec.pan_health_pct}% &bull; <u>Fix</u></span>
                                </div>
                                <div style="width: 100%; background: var(--hds-track-bg); height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="width: {rec.pan_health_pct}%; background: #818cf8; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </a>

                            <!-- Bank Details Completeness (Emerald) -->
                            <a href="/odoo/action-hudson_in_payroll.action_dashboard_missing_bank_employees" class="o_hds_dashboard_card_clickable" style="text-decoration: none; color: inherit; display: block; padding: 2px 4px;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; margin-bottom: 5px;">
                                    <span class="hds-text-secondary">Bank Details Completeness</span>
                                    <span style="color: #34d399;">{rec.bank_health_pct}% &bull; <u>Fix</u></span>
                                </div>
                                <div style="width: 100%; background: var(--hds-track-bg); height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="width: {rec.bank_health_pct}%; background: #34d399; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </a>

                            <!-- Aadhaar Completeness (Sky Blue) -->
                            <a href="/odoo/action-hr.open_view_employee_list_my" class="o_hds_dashboard_card_clickable" style="text-decoration: none; color: inherit; display: block; padding: 2px 4px;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; margin-bottom: 5px;">
                                    <span class="hds-text-secondary">Aadhaar / ID Completeness</span>
                                    <span style="color: #38bdf8;">{rec.aadhaar_health_pct}%</span>
                                </div>
                                <div style="width: 100%; background: var(--hds-track-bg); height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="width: {rec.aadhaar_health_pct}%; background: #38bdf8; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </a>

                            <!-- Emergency Contact Completeness (Amber) -->
                            <a href="/odoo/action-hr.open_view_employee_list_my" class="o_hds_dashboard_card_clickable" style="text-decoration: none; color: inherit; display: block; padding: 2px 4px;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; margin-bottom: 5px;">
                                    <span class="hds-text-secondary">Emergency Contact Completeness</span>
                                    <span style="color: #fbbf24;">{rec.contact_health_pct}%</span>
                                </div>
                                <div style="width: 100%; background: var(--hds-track-bg); height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="width: {rec.contact_health_pct}%; background: #fbbf24; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </a>

                        </div>
                    </div>
                </div>

                <!-- 4. STATUTORY NUMBER VALIDATION & COMPLIANCE SECTION -->
                <div class="hds-dash-card" style="padding: 18px; margin-bottom: 22px;">
                    <div style="font-size: 14px; font-weight: 700; margin-bottom: 12px; border-bottom: 1px solid var(--hds-row-border); padding-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <span class="hds-text-primary">
                            <i class="fa fa-shield me-1" style="color: #38bdf8;"/> Statutory Identifier Compliance &amp; Readiness
                        </span>
                        <span class="hds-text-muted" style="font-size: 12px; font-weight: 600;">Active Workforce: {rec.active_employee_count} Employees</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; font-size: 12px;">

                        <!-- EPF Tile -->
                        <a href="/odoo/action-hudson_in_payroll.action_dashboard_epf_employees" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                            <div class="hds-text-primary" style="font-size: 12px; font-weight: 700; border-bottom: 1px dashed var(--hds-row-border); padding-bottom: 4px; margin-bottom: 6px; display: flex; justify-content: space-between;">
                                <span>EPF (UAN / PF No)</span>
                                <span style="font-size: 10px; color: #818cf8;">&rarr;</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span style="color: #4ade80; font-weight: 600;">Complete UAN:</span>
                                <span style="font-weight: 700; color: #4ade80;">{rec.epf_complete_count}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: #f87171; font-weight: 600;">Missing UAN:</span>
                                <span style="font-weight: 700; color: #f87171;">{rec.epf_missing_count}</span>
                            </div>
                        </a>

                        <!-- ESIC Tile -->
                        <a href="/odoo/action-hudson_in_payroll.action_dashboard_esic_employees" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                            <div class="hds-text-primary" style="font-size: 12px; font-weight: 700; border-bottom: 1px dashed var(--hds-row-border); padding-bottom: 4px; margin-bottom: 6px; display: flex; justify-content: space-between;">
                                <span>ESIC (IP Number)</span>
                                <span style="font-size: 10px; color: #818cf8;">&rarr;</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span style="color: #4ade80; font-weight: 600;">Complete IP:</span>
                                <span style="font-weight: 700; color: #4ade80;">{rec.esic_complete_count}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: #f87171; font-weight: 600;">Missing IP:</span>
                                <span style="font-weight: 700; color: #f87171;">{rec.esic_missing_count}</span>
                            </div>
                        </a>

                        <!-- LWF Tile -->
                        <a href="/odoo/action-hr.open_view_employee_list_my" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                            <div class="hds-text-primary" style="font-size: 12px; font-weight: 700; border-bottom: 1px dashed var(--hds-row-border); padding-bottom: 4px; margin-bottom: 6px; display: flex; justify-content: space-between;">
                                <span>LWF Registration</span>
                                <span style="font-size: 10px; color: #818cf8;">&rarr;</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span style="color: #4ade80; font-weight: 600;">Complete Number:</span>
                                <span style="font-weight: 700; color: #4ade80;">{rec.lwf_complete_count}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: #f87171; font-weight: 600;">Missing Number:</span>
                                <span style="font-weight: 700; color: #f87171;">{rec.lwf_missing_count}</span>
                            </div>
                        </a>

                        <!-- Overall Readiness Tile -->
                        <a href="/odoo/action-hudson_in_payroll.action_dashboard_missing_pan_employees" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                            <div class="hds-text-primary" style="font-size: 12px; font-weight: 700; border-bottom: 1px dashed var(--hds-row-border); padding-bottom: 4px; margin-bottom: 6px; display: flex; justify-content: space-between;">
                                <span>Data Readiness</span>
                                <span style="font-size: 10px; color: #818cf8;">&rarr;</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span style="color: #4ade80; font-weight: 600;">Processing Ready:</span>
                                <span style="font-weight: 700; color: #4ade80;">{rec.statutory_ready_count}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: #f87171; font-weight: 600;">Data Errors:</span>
                                <span style="font-weight: 700; color: #f87171;">{rec.statutory_data_errors_count}</span>
                            </div>
                        </a>

                    </div>
                </div>

                <!-- 5. STATUTORY & TAX CARD SECTION -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 22px;">

                    <!-- Statutory Compliance Card -->
                    <div class="hds-dash-card" style="padding: 18px;">
                        <div class="hds-text-primary" style="font-size: 14px; font-weight: 700; margin-bottom: 12px; border-bottom: 1px solid var(--hds-row-border); padding-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <i class="fa fa-check-circle" style="color: #4ade80;"/> Statutory Compliance Summary
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
                            <a href="/odoo/action-hudson_in_payroll.action_dashboard_epf_employees" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">EPF / PF Liability</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.epf_total_liability:,.2f}</div>
                                <div style="color: #4ade80; font-size: 10px; font-weight: 600; margin-top: 4px;">🟢 ECR Ready &bull; <u>View</u></div>
                            </a>
                            <a href="/odoo/action-hudson_in_payroll.action_dashboard_esic_employees" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">ESIC Liability</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.esic_total_liability:,.2f}</div>
                                <div style="color: #4ade80; font-size: 10px; font-weight: 600; margin-top: 4px;">🟢 Ready for Filing &bull; <u>View</u></div>
                            </a>
                            <div class="hds-subcard" style="padding: 12px;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">Professional Tax (PT)</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.pt_total_liability:,.2f}</div>
                                <div style="color: #4ade80; font-size: 10px; font-weight: 600; margin-top: 4px;">🟢 State Slabs Applied</div>
                            </div>
                            <a href="/odoo/action-hudson_payroll_base.action_hr_payslip" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">TDS Withholding</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.tds_this_month:,.2f}</div>
                                <div style="color: #4ade80; font-size: 10px; font-weight: 600; margin-top: 4px;">🟢 Form 24Q Ready &bull; <u>View</u></div>
                            </a>
                        </div>
                    </div>

                    <!-- Tax & TDS Card -->
                    <div class="hds-dash-card" style="padding: 18px;">
                        <div class="hds-text-primary" style="font-size: 14px; font-weight: 700; margin-bottom: 12px; border-bottom: 1px solid var(--hds-row-border); padding-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <i class="fa fa-calculator" style="color: #818cf8;"/> Tax Regime &amp; Declarations Breakdown
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
                            <a href="/odoo/action-hudson_in_payroll.action_dashboard_old_regime_employees" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">Old Regime Opted</div>
                                <div style="font-weight: 700; font-size: 14px; color: #818cf8; margin-top: 2px;">{rec.old_regime_count} Employees &rarr;</div>
                            </a>
                            <a href="/odoo/action-hudson_in_payroll.action_dashboard_new_regime_employees" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">New Regime (115BAC)</div>
                                <div style="font-weight: 700; font-size: 14px; color: #38bdf8; margin-top: 2px;">{rec.new_regime_count} Employees &rarr;</div>
                            </a>
                            <a href="/odoo/action-hudson_payroll_base.action_hr_payslip" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">TDS YTD Total</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.tds_ytd_total:,.2f} &rarr;</div>
                            </a>
                            <a href="/odoo/action-hudson_in_payroll.action_dashboard_pending_declarations" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">Pending Declarations</div>
                                <div style="font-weight: 700; font-size: 14px; color: #fbbf24; margin-top: 2px;">{rec.pending_declarations_count} Pending &rarr;</div>
                            </a>
                        </div>
                    </div>
                </div>

                <!-- 6. HISTORICAL PAYROLL COST TREND CHART (PAYRUN PALETTE) -->
                <div class="hds-dash-card" style="padding: 18px;">
                    <div class="hds-text-primary" style="font-size: 14px; font-weight: 700; margin-bottom: 15px; border-bottom: 1px solid var(--hds-row-border); padding-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                        <i class="fa fa-line-chart" style="color: #c084fc;"/> Historical Payroll Cost Trend (Last 6 Months)
                    </div>
                    <div style="display: flex; align-items: flex-end; justify-content: space-around; height: 110px; padding: 0 20px;">
                        {trend_bars_html}
                    </div>
                </div>

            </div>
            """

    def action_refresh_dashboard(self):
        self.ensure_one()
        self._compute_dashboard_metrics()
        return True

    def action_view_missing_pan_employees(self):
        self.ensure_one()
        return {
            'name': _('Employees Missing PAN'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': ['&', ('active', '=', True), '|', ('hds_in_pan', '=', False), ('hds_in_pan', '=', '')],
            'target': 'current',
        }

    def action_view_missing_bank_employees(self):
        self.ensure_one()
        active_emps = self.env['hr.employee'].search([('active', '=', True)])
        missing_ids = [e.id for e in active_emps if not self._has_bank_account(e)]
        return {
            'name': _('Employees Missing Bank Account'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', missing_ids)],
            'target': 'current',
        }

    def action_view_epf_missing_employees(self):
        self.ensure_one()
        active_emps = self.env['hr.employee'].search([('active', '=', True), ('hds_in_epf_applicable', '=', True)])
        from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        comp_service = StatutoryComplianceValidationService(self.env)
        missing_ids = [e.id for e in active_emps if not comp_service.validate_employee_epf(e)[0]]
        return {
            'name': _('EPF: Employees Missing UAN / Invalid UAN'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', missing_ids)],
            'target': 'current',
        }

    def action_view_epf_complete_employees(self):
        self.ensure_one()
        active_emps = self.env['hr.employee'].search([('active', '=', True), ('hds_in_epf_applicable', '=', True)])
        from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        comp_service = StatutoryComplianceValidationService(self.env)
        complete_ids = [e.id for e in active_emps if comp_service.validate_employee_epf(e)[0]]
        return {
            'name': _('EPF: Employees with Complete UAN'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', complete_ids)],
            'target': 'current',
        }

    def action_view_esic_missing_employees(self):
        self.ensure_one()
        active_emps = self.env['hr.employee'].search([('active', '=', True), ('hds_in_esic_applicable', '=', True)])
        from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        comp_service = StatutoryComplianceValidationService(self.env)
        missing_ids = [e.id for e in active_emps if not comp_service.validate_employee_esic(e)[0]]
        return {
            'name': _('ESIC: Employees Missing IP Number / Invalid IP'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', missing_ids)],
            'target': 'current',
        }

    def action_view_esic_complete_employees(self):
        self.ensure_one()
        active_emps = self.env['hr.employee'].search([('active', '=', True), ('hds_in_esic_applicable', '=', True)])
        from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        comp_service = StatutoryComplianceValidationService(self.env)
        complete_ids = [e.id for e in active_emps if comp_service.validate_employee_esic(e)[0]]
        return {
            'name': _('ESIC: Employees with Complete IP Number'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', complete_ids)],
            'target': 'current',
        }

    def action_view_lwf_missing_employees(self):
        self.ensure_one()
        active_emps = self.env['hr.employee'].search([('active', '=', True), ('hds_in_lwf_applicable', '=', True)])
        from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        comp_service = StatutoryComplianceValidationService(self.env)
        missing_ids = [e.id for e in active_emps if not comp_service.validate_employee_lwf(e)[0]]
        return {
            'name': _('LWF: Employees Missing Registration Number'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', missing_ids)],
            'target': 'current',
        }

    def action_view_lwf_complete_employees(self):
        self.ensure_one()
        active_emps = self.env['hr.employee'].search([('active', '=', True), ('hds_in_lwf_applicable', '=', True)])
        from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        comp_service = StatutoryComplianceValidationService(self.env)
        complete_ids = [e.id for e in active_emps if comp_service.validate_employee_lwf(e)[0]]
        return {
            'name': _('LWF: Employees with Complete Number'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', complete_ids)],
            'target': 'current',
        }

    def action_view_statutory_error_employees(self):
        self.ensure_one()
        active_emps = self.env['hr.employee'].search([('active', '=', True)])
        from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        comp_service = StatutoryComplianceValidationService(self.env)
        error_ids = [e.id for e in active_emps if not comp_service.validate_employee_all(e)['is_compliant']]
        return {
            'name': _('Employees with Statutory Data Errors'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', error_ids)],
            'target': 'current',
        }

    def action_view_statutory_ready_employees(self):
        self.ensure_one()
        active_emps = self.env['hr.employee'].search([('active', '=', True)])
        from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
        comp_service = StatutoryComplianceValidationService(self.env)
        ready_ids = [e.id for e in active_emps if comp_service.validate_employee_all(e)['is_compliant']]
        return {
            'name': _('Employees Ready for Statutory Payroll Processing'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', ready_ids)],
            'target': 'current',
        }

    def action_view_pending_declarations(self):
        self.ensure_one()
        return {
            'name': _('Pending Tax Declarations'),
            'type': 'ir.actions.act_window',
            'res_model': 'tds.employee.declaration',
            'view_mode': 'list,form',
            'domain': [('state', 'in', ('submitted', 'proof_submitted', 'proof_under_review'))],
            'target': 'current',
        }

    def action_view_new_joiners(self):
        self.ensure_one()
        today = fields.Date.today()
        m_num = int(self.payroll_month_num or today.month)
        year = today.year
        if self.financial_year_id and self.financial_year_id.start_date:
            fy_s_year = self.financial_year_id.start_date.year
            fy_e_year = self.financial_year_id.end_date.year
            year = fy_s_year if m_num >= 4 else fy_e_year
        month_start = date(year, m_num, 1)
        month_end = date(year, m_num, calendar.monthrange(year, m_num)[1])

        emp_fields = self.env['hr.employee']._fields
        join_field = next((f for f in ('joining_date', 'date_of_joining', 'hds_in_doj', 'first_contract_date', 'contract_date_start', 'create_date') if f in emp_fields), None)

        domain = [(join_field, '>=', month_start), (join_field, '<=', month_end)] if join_field else []

        return {
            'name': _('New Joiners'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
        }

    def action_view_final_settlements_due(self):
        self.ensure_one()
        today = fields.Date.today()
        m_num = int(self.payroll_month_num or today.month)
        year = today.year
        if self.financial_year_id and self.financial_year_id.start_date:
            fy_s_year = self.financial_year_id.start_date.year
            fy_e_year = self.financial_year_id.end_date.year
            year = fy_s_year if m_num >= 4 else fy_e_year
        month_start = date(year, m_num, 1)
        month_end = date(year, m_num, calendar.monthrange(year, m_num)[1])

        month_name = dict(self._fields['payroll_month_num'].selection).get(self.payroll_month_num, '')
        return {
            'name': _('Final Settlements Due (%s)') % month_name,
            'type': 'ir.actions.act_window',
            'res_model': 'final.settlement',
            'view_mode': 'list,form',
            'domain': [
                ('state', '!=', 'cancel'),
                ('last_working_day', '>=', month_start),
                ('last_working_day', '<=', month_end)
            ],
            'target': 'current',
        }
