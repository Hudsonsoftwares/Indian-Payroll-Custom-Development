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
    total_gross_pay = fields.Monetary(string="Total Gross Pay", currency_field='currency_id', compute='_compute_dashboard_metrics')
    total_net_pay = fields.Monetary(string="Total Net Wage (Payable)", currency_field='currency_id', compute='_compute_dashboard_metrics')
    total_net_paid = fields.Monetary(string="Disbursed Net Pay", currency_field='currency_id', compute='_compute_dashboard_metrics')
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
    draft_slips_count = fields.Integer(string="Draft Payslips Count", compute='_compute_dashboard_metrics')
    verify_slips_count = fields.Integer(string="To Validate Payslips Count", compute='_compute_dashboard_metrics')
    unconfirmed_slips_count = fields.Integer(string="Unconfirmed Payslips Count", compute='_compute_dashboard_metrics')
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
    dashboard_html = fields.Html(string="Dashboard Canvas", compute='_compute_dashboard_html', store=False, sanitize=False)

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
    def _has_pan(emp):
        for f in ('hds_in_pan', 'pan_no', 'pan'):
            val = getattr(emp, f, False)
            if val and str(val).strip():
                return True
        partner = getattr(emp, 'work_contact_id', False) or getattr(emp, 'address_home_id', False)
        if partner:
            p_pan = getattr(partner, 'pan', False) or getattr(partner, 'vat', False)
            if p_pan and str(p_pan).strip():
                return True
        return False

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

    @staticmethod
    def _has_aadhaar(emp):
        for f in ('hds_in_aadhaar', 'aadhaar_no', 'identification_id'):
            val = getattr(emp, f, False)
            if val and str(val).strip():
                return True
        return False

    @staticmethod
    def _has_emergency_contact(emp):
        for f in ('emergency_contact', 'emergency_phone'):
            val = getattr(emp, f, False)
            if val and str(val).strip():
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

            pan_count = len(active_emps.filtered(lambda e: self._has_pan(e)))
            bank_count = len(active_emps.filtered(lambda e: self._has_bank_account(e)))
            aadhaar_count = len(active_emps.filtered(lambda e: self._has_aadhaar(e)))
            contact_count = len(active_emps.filtered(lambda e: self._has_emergency_contact(e)))

            rec.missing_pan_count = len(active_emps.filtered(lambda e: not self._has_pan(e)))
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

            # Unconfirmed slips (Draft & To Validate) - count actual payslips requiring validation for selected month
            unconfirmed_domain = [
                ('date_from', '<=', month_end),
                ('date_to', '>=', month_start),
                ('state', 'in', ('draft', 'verify')),
            ] + company_domain
            unconfirmed_slips = self.env['hr.payslip'].search(unconfirmed_domain)

            rec.draft_slips_count = len(unconfirmed_slips.filtered(lambda s: s.state == 'draft'))
            rec.verify_slips_count = len(unconfirmed_slips.filtered(lambda s: s.state == 'verify'))
            rec.unconfirmed_slips_count = rec.draft_slips_count + rec.verify_slips_count
            rec.attendance_pending_count = rec.unconfirmed_slips_count

            tot_gross = 0.0
            tot_net = 0.0
            tot_net_payable = 0.0
            tot_net_paid = 0.0
            tot_basic = 0.0
            tot_tds = 0.0
            tot_epf = 0.0
            tot_esi = 0.0
            tot_pt = 0.0
            tot_employer_cost = 0.0
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
                if slip.state == 'paid':
                    tot_net_paid += net_val
                else:
                    tot_net_payable += net_val

                codes = set((l.code or '').upper() for l in slip.line_ids)
                has_er_epf = 'EMPLOYER_EPF' in codes or 'ER_PF' in codes

                slip_employer_contrib = 0.0
                for line in slip.line_ids:
                    code = (line.code or '').upper()
                    amt = float(line.total or 0.0)
                    rule = line.salary_rule_id

                    if code == 'BASIC':
                        tot_basic += abs(amt)
                    elif code in ('TDS', 'INCOME_TAX', 'IT', 'HDS_IN_TDS'):
                        tot_tds += abs(amt)
                    elif code in ('PT', 'PROF_TAX'):
                        tot_pt += abs(amt)

                    # EPF Statutory Liabilities (avoid double-counting EPS + EPF_SHARE when EMPLOYER_EPF is present)
                    if code in ('PF', 'EPF', 'EE_PF'):
                        tot_epf += abs(amt)
                    elif code in ('EMPLOYER_EPF', 'ER_PF'):
                        tot_epf += abs(amt)
                    elif not has_er_epf and code in ('EPS', 'EPF_SHARE'):
                        tot_epf += abs(amt)
                    elif code in ('EDLI', 'EPF_ADMIN', 'EDLI_ADMIN'):
                        tot_epf += abs(amt)

                    # ESIC Statutory Liabilities
                    if code in ('ESIC_EE', 'EE_ESI'):
                        tot_esi += abs(amt)
                    elif code in ('ESIC_ER', 'ER_ESI'):
                        tot_esi += abs(amt)
                    elif code == 'ESI' and 'ESIC_EE' not in codes and 'ESIC_ER' not in codes:
                        tot_esi += abs(amt)

                    # Employer Cost Contribution (Employer EPF, EDLI, EPF Admin, Employer ESIC, Employer LWF)
                    if getattr(rule, 'hds_in_contributes_to_employer_cost', False):
                        slip_employer_contrib += abs(amt)
                    elif code in ('EMPLOYER_EPF', 'EDLI', 'EPF_ADMIN', 'EDLI_ADMIN', 'ESIC_ER', 'LWF_ER'):
                        slip_employer_contrib += abs(amt)
                    elif not has_er_epf and code in ('EPS', 'EPF_SHARE'):
                        slip_employer_contrib += abs(amt)

                tot_employer_cost += slip_employer_contrib

                for wd in slip.worked_days_line_ids:
                    tot_hours += float(wd.number_of_hours or 0.0)
                    tot_days += float(wd.number_of_days or 0.0)

            rec.total_payroll_cost = (tot_gross + tot_employer_cost) if (tot_gross > 0 or tot_employer_cost > 0) else tot_net
            rec.total_gross_pay = tot_gross
            rec.total_net_pay = tot_net_payable
            rec.total_net_paid = tot_net_paid
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
            rec.old_regime_count = self.env['hr.employee'].search_count([
                ('active', '=', True),
                ('hds_in_tax_regime', '=', 'old')
            ])
            rec.new_regime_count = self.env['hr.employee'].search_count([
                ('active', '=', True),
                ('hds_in_tax_regime', '=', 'new')
            ])

            # Total Action Required Items
            rec.pending_actions_count = rec.missing_pan_count + rec.missing_bank_count + rec.pending_declarations_count + rec.attendance_pending_count + rec.missing_salary_count

    def _compute_dashboard_html(self):
        for rec in self:
            rec._compute_dashboard_metrics()
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
                    has_pan = self._has_pan(j)
                    has_bank = self._has_bank_account(j)

                    if not has_pan:
                        status_chip = f'<span role="button" tabindex="0" onclick="window.hdsRecordClick &amp;&amp; window.hdsRecordClick(this, \'{j.id}\', \'hr.employee\')" data-card-type="hr_employee_record" data-record-id="{j.id}" data-record-model="hr.employee" class="o_hds_dashboard_card_clickable" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; gap: 4px; cursor: pointer;">🔴 PAN Missing &rarr; Fix</span>'
                    elif not has_bank:
                        status_chip = f'<span role="button" tabindex="0" onclick="window.hdsRecordClick &amp;&amp; window.hdsRecordClick(this, \'{j.id}\', \'hr.employee\')" data-card-type="hr_employee_record" data-record-id="{j.id}" data-record-model="hr.employee" class="o_hds_dashboard_card_clickable" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; gap: 4px; cursor: pointer;">🟠 Bank Missing &rarr; Fix</span>'
                    else:
                        status_chip = f'<span role="button" tabindex="0" onclick="window.hdsRecordClick &amp;&amp; window.hdsRecordClick(this, \'{j.id}\', \'hr.employee\')" data-card-type="hr_employee_record" data-record-id="{j.id}" data-record-model="hr.employee" class="o_hds_dashboard_card_clickable" style="background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; gap: 4px; cursor: pointer;">🟢 Payroll Ready</span>'

                    joiner_rows_html += f"""
                    <tr style="border-bottom: 1px solid var(--hds-row-border); transition: background-color 0.15s ease;">
                        <td style="padding: 10px 8px; font-weight: 600;">
                            <span role="button" tabindex="0" onclick="window.hdsRecordClick &amp;&amp; window.hdsRecordClick(this, '{j.id}', 'hr.employee')" data-card-type="hr_employee_record" data-record-id="{j.id}" data-record-model="hr.employee" class="o_hds_dashboard_card_clickable" style="color: #818cf8; font-weight: 700; cursor: pointer;">
                                {j.name}
                            </span>
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
            state_priority = {'paid': 4, 'done': 3, 'verify': 2, 'draft': 1}
            company_domain = [('company_id', 'in', self.env.companies.ids)]
            trend_data = []
            for i in range(5, -1, -1):
                t_month = (m_num - i - 1) % 12 + 1
                t_year = year if (m_num - i) > 0 else year - 1
                t_m_name = calendar.month_abbr[t_month]
                t_start = date(t_year, t_month, 1)
                t_end = date(t_year, t_month, calendar.monthrange(t_year, t_month)[1])

                t_domain = [
                    ('date_from', '<=', t_end),
                    ('date_to', '>=', t_start),
                    ('state', '!=', 'cancel'),
                ] + company_domain
                t_all_slips = self.env['hr.payslip'].search(t_domain)
                t_latest = {}
                for s in t_all_slips.sorted(key=lambda s: (state_priority.get(s.state, 0), s.id), reverse=True):
                    if s.employee_id.id not in t_latest:
                        t_latest[s.employee_id.id] = s

                t_gross = 0.0
                t_er_epf = 0.0
                t_er_esic = 0.0
                t_admin = 0.0
                t_er_lwf = 0.0
                t_worked_days = 0.0

                for s in t_latest.values():
                    gross_val = float(getattr(s, 'gross_amount', None) or getattr(s, 'gross_wage', 0.0) or 0.0)
                    if not gross_val:
                        for line in s.line_ids:
                            if (line.code or '').upper() == 'GROSS':
                                gross_val = abs(float(line.total or 0.0))
                                break
                    if not gross_val:
                        net_val = float(getattr(s, 'net_amount', None) or getattr(s, 'net_wage', 0.0) or 0.0)
                        if not net_val:
                            for line in s.line_ids:
                                if (line.code or '').upper() == 'NET':
                                    net_val = abs(float(line.total or 0.0))
                                    break
                        gross_val = net_val

                    t_gross += gross_val

                    for wd in s.worked_days_line_ids:
                        code = (wd.code or '').upper()
                        if 'SHORT' not in code and 'UNPAID' not in code and 'LOP' not in code:
                            t_worked_days += float(wd.number_of_days or 0.0)

                    codes = set((l.code or '').upper() for l in s.line_ids)
                    has_er_epf = 'EMPLOYER_EPF' in codes or 'ER_PF' in codes

                    for line in s.line_ids:
                        code = (line.code or '').upper()
                        amt = abs(float(line.total or 0.0))
                        if code in ('EMPLOYER_EPF', 'ER_PF'):
                            t_er_epf += amt
                        elif not has_er_epf and code in ('EPS', 'EPF_SHARE'):
                            t_er_epf += amt
                        elif code == 'ESIC_ER':
                            t_er_esic += amt
                        elif code in ('EDLI', 'EPF_ADMIN', 'EDLI_ADMIN'):
                            t_admin += amt
                        elif code == 'LWF_ER':
                            t_er_lwf += amt

                t_cost = t_gross + t_er_epf + t_er_esic + t_admin + t_er_lwf

                trend_data.append({
                    'month_num': t_month,
                    'year': t_year,
                    'month_name': t_m_name,
                    'gross': t_gross,
                    'er_epf': t_er_epf,
                    'er_esic': t_er_esic,
                    'admin': t_admin,
                    'er_lwf': t_er_lwf,
                    'emp_count': len(t_latest),
                    'worked_days': t_worked_days,
                    'avg_days': round(t_worked_days / len(t_latest), 1) if t_latest else 0.0,
                    'cost': t_cost,
                    'is_current': (t_month == m_num and t_year == year),
                    'date_from': str(t_start),
                    'date_to': str(t_end),
                })

            max_trend_cost = max([d['cost'] for d in trend_data] or [0.0])
            trend_bars_html = ""
            for d in trend_data:
                t_cost = d['cost']
                t_m_name = d['month_name']
                is_curr = d['is_current']
                t_gross = d['gross']
                t_er_epf = d['er_epf']
                t_er_esic = d['er_esic']
                t_admin = d['admin']
                t_wd = d['worked_days']
                t_avg_d = d['avg_days']

                if max_trend_cost > 0 and t_cost > 0:
                    bar_height = max(18, min(85, int((t_cost / max_trend_cost) * 85)))
                    pct_g = (t_gross / t_cost) * 100.0
                    pct_p = (t_er_epf / t_cost) * 100.0
                    pct_e = (t_er_esic / t_cost) * 100.0
                    pct_a = (t_admin / t_cost) * 100.0

                    bar_inner = f"""
                    <div style="height: {pct_g:.1f}%; width: 100%; background: #7c3aed;"></div>
                    """
                    if t_er_epf > 0:
                        bar_inner += f"""<div style="height: {pct_p:.1f}%; width: 100%; background: #38bdf8;"></div>"""
                    if t_er_esic > 0:
                        bar_inner += f"""<div style="height: {pct_e:.1f}%; width: 100%; background: #34d399;"></div>"""
                    if t_admin > 0:
                        bar_inner += f"""<div style="height: {pct_a:.1f}%; width: 100%; background: #fbbf24;"></div>"""

                    bar_container_style = f"width: 100%; max-width: 38px; height: {bar_height}px; border-radius: 6px 6px 0 0; overflow: hidden; display: flex; flex-direction: column-reverse; box-shadow: 0 2px 8px rgba(124, 58, 237, 0.25); transition: height 0.3s ease;"
                else:
                    bar_height = 6
                    bar_inner = ""
                    bar_container_style = "width: 100%; max-width: 38px; background: var(--hds-track-bg, #374151); height: 6px; border-radius: 4px;"

                cost_lbl = f"{currency_symbol} {t_cost/100000:.1f}L" if t_cost >= 100000 else f"{currency_symbol} {t_cost:,.0f}"
                curr_style = 'color: #c084fc; font-weight: 800;' if is_curr else 'color: var(--hds-text-secondary, #94a3b8); font-weight: 600;'
                badge_curr = ' <span style="font-size: 8px; background: rgba(192, 132, 252, 0.2); color: #c084fc; padding: 1px 4px; border-radius: 4px; margin-left: 2px;">Active</span>' if is_curr else ''
                days_lbl = f'<div style="font-size: 9px; color: #38bdf8; font-weight: 600; margin-top: 1px;">{t_wd:.0f}d worked</div>' if t_wd > 0 else ''

                tooltip = f"{t_m_name} {d['year']} Cost Breakdown:&#10;&bull; Attendance: {t_wd:.0f} Worked Days (Avg {t_avg_d} Days/Emp)&#10;&bull; Gross Salary ({d['emp_count']} Emps): {currency_symbol} {t_gross:,.2f}&#10;&bull; Employer EPF: {currency_symbol} {t_er_epf:,.2f}&#10;&bull; Employer ESIC: {currency_symbol} {t_er_esic:,.2f}&#10;&bull; EDLI &amp; Admin: {currency_symbol} {t_admin:,.2f}&#10;━━━━━━━━━━━━━━━━━━━━&#10;Total Cost to Company (CTC): {currency_symbol} {t_cost:,.2f}&#10;(Click to view payslips)"

                trend_bars_html += f"""
                <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'total_payroll_cost')" data-card-type="total_payroll_cost" data-date-from="{d['date_from']}" data-date-to="{d['date_to']}" class="o_hds_dashboard_card_clickable" title="{tooltip}" style="display: flex; flex-direction: column; align-items: center; gap: 4px; flex: 1; cursor: pointer; padding: 4px; border-radius: 6px; transition: transform 0.15s ease;">
                    <div class="hds-text-primary" style="font-size: 11px; font-weight: 700;">{cost_lbl}</div>
                    <div style="{bar_container_style}">
                        {bar_inner}
                    </div>
                    <div style="font-size: 10px; {curr_style} display: flex; align-items: center;">{t_m_name}{badge_curr}</div>
                    {days_lbl}
                </div>
                """

            # Detailed Cost Component Breakdown for Active Month
            active_item = next((d for d in trend_data if d['is_current'] and d['cost'] > 0), None)
            if not active_item:
                active_item = next((d for d in reversed(trend_data) if d['cost'] > 0), None)

            if active_item and active_item['cost'] > 0:
                act_cost = active_item['cost']
                act_gross = active_item['gross']
                act_epf = active_item['er_epf']
                act_esic = active_item['er_esic']
                act_admin = active_item['admin']
                act_m_name = active_item['month_name']
                act_year = active_item['year']
                act_emp_count = active_item['emp_count']
                act_worked_days = active_item['worked_days']
                act_avg_days = active_item['avg_days']

                pct_gross = (act_gross / act_cost) * 100.0
                pct_epf = (act_epf / act_cost) * 100.0
                pct_esic = (act_esic / act_cost) * 100.0
                pct_admin = (act_admin / act_cost) * 100.0

                trend_breakdown_html = f"""
                <div style="margin-top: 18px; padding-top: 14px; border-top: 1px dashed var(--hds-row-border);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span class="hds-text-primary" style="font-size: 12px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
                            <i class="fa fa-pie-chart" style="color: #c084fc;"/> {act_m_name} {act_year} Employer Cost Breakdown (CTC)
                        </span>
                        <span style="font-size: 11px; font-weight: 700; color: #c084fc;">
                            Total Payroll Cost: {currency_symbol} {act_cost:,.2f}
                        </span>
                    </div>

                    <!-- Visual Segmented Ratio Bar -->
                    <div style="width: 100%; height: 8px; border-radius: 4px; overflow: hidden; display: flex; margin-bottom: 12px; background: var(--hds-track-bg, #374151);">
                        <div style="width: {pct_gross:.1f}%; background: #7c3aed;" title="Gross Salary: {pct_gross:.1f}%"></div>
                        <div style="width: {pct_epf:.1f}%; background: #38bdf8;" title="Employer EPF: {pct_epf:.1f}%"></div>
                        <div style="width: {pct_esic:.1f}%; background: #34d399;" title="Employer ESIC: {pct_esic:.1f}%"></div>
                        <div style="width: {pct_admin:.1f}%; background: #fbbf24;" title="EDLI &amp; Admin: {pct_admin:.1f}%"></div>
                    </div>

                    <!-- Breakdown Grid Cards (including Attendance Base) -->
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; font-size: 12px;">
                        
                        <!-- 1. Gross Salary -->
                        <div style="background: rgba(124, 58, 237, 0.08); border-left: 3px solid #8b5cf6; padding: 10px 12px; border-radius: 6px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 11px; color: var(--hds-text-secondary); font-weight: 600;">Gross Salary ({act_emp_count} Emps)</span>
                                <span style="font-size: 10px; font-weight: 700; color: #8b5cf6;">{pct_gross:.1f}%</span>
                            </div>
                            <div style="font-size: 14px; font-weight: 700; color: #a78bfa; margin-top: 3px;">{currency_symbol} {act_gross:,.2f}</div>
                            <div style="font-size: 10px; color: var(--hds-text-muted); margin-top: 2px;">Basic + HRA + Allowances</div>
                        </div>

                        <!-- 2. Attendance Base Card -->
                        <div style="background: rgba(14, 165, 233, 0.08); border-left: 3px solid #0284c7; padding: 10px 12px; border-radius: 6px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 11px; color: var(--hds-text-secondary); font-weight: 600;">Attendance Base</span>
                                <span style="font-size: 10px; font-weight: 700; color: #0284c7;">{act_avg_days}d / Emp</span>
                            </div>
                            <div style="font-size: 14px; font-weight: 700; color: #0284c7; margin-top: 3px;">{act_worked_days:.0f} Worked Days</div>
                            <div style="font-size: 10px; color: var(--hds-text-muted); margin-top: 2px;">Salaries prorated on worked days</div>
                        </div>

                        <!-- 3. Employer EPF -->
                        <div style="background: rgba(56, 189, 248, 0.08); border-left: 3px solid #38bdf8; padding: 10px 12px; border-radius: 6px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 11px; color: var(--hds-text-secondary); font-weight: 600;">Employer EPF Share</span>
                                <span style="font-size: 10px; font-weight: 700; color: #38bdf8;">{pct_epf:.1f}%</span>
                            </div>
                            <div style="font-size: 14px; font-weight: 700; color: #38bdf8; margin-top: 3px;">{currency_symbol} {act_epf:,.2f}</div>
                            <div style="font-size: 10px; color: var(--hds-text-muted); margin-top: 2px;">PF &amp; Pension Contribution (EPS)</div>
                        </div>

                        <!-- 4. Employer ESIC -->
                        <div style="background: rgba(52, 211, 153, 0.08); border-left: 3px solid #34d399; padding: 10px 12px; border-radius: 6px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 11px; color: var(--hds-text-secondary); font-weight: 600;">Employer ESIC Share</span>
                                <span style="font-size: 10px; font-weight: 700; color: #34d399;">{pct_esic:.1f}%</span>
                            </div>
                            <div style="font-size: 14px; font-weight: 700; color: #34d399; margin-top: 3px;">{currency_symbol} {act_esic:,.2f}</div>
                            <div style="font-size: 10px; color: var(--hds-text-muted); margin-top: 2px;">3.25% Statutory Contribution</div>
                        </div>

                        <!-- 5. EDLI & Admin -->
                        <div style="background: rgba(245, 158, 11, 0.08); border-left: 3px solid #f59e0b; padding: 10px 12px; border-radius: 6px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 11px; color: var(--hds-text-secondary); font-weight: 600;">EDLI &amp; Admin Charges</span>
                                <span style="font-size: 10px; font-weight: 700; color: #f59e0b;">{pct_admin:.1f}%</span>
                            </div>
                            <div style="font-size: 14px; font-weight: 700; color: #fbbf24; margin-top: 3px;">{currency_symbol} {act_admin:,.2f}</div>
                            <div style="font-size: 10px; color: var(--hds-text-muted); margin-top: 2px;">Admin (0.5%) + EDLI (0.5%)</div>
                        </div>

                    </div>
                </div>
                """
            else:
                trend_breakdown_html = ""

            rec.dashboard_html = f"""
            <div class="o_hds_dashboard_root" data-hds-dashboard-root="true" style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; width: 100%; box-sizing: border-box;">

                <!-- 1. PRIMARY KPI CARDS GRID (PAYRUN PALETTE) -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 22px;">

                    <!-- Card 1: Total Payroll Cost (Payrun Employer Cost - Purple) -->
                    <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'total_payroll_cost')" data-card-type="total_payroll_cost" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #c084fc !important; cursor: pointer;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #c084fc !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-briefcase me-1"/> Total Payroll Cost
                            </span>
                            <span style="font-size: 11px; color: #c084fc; font-weight: 600;">View Details &darr;</span>
                        </div>
                        <div class="hds-text-primary" style="font-size: 24px; font-weight: 800; margin: 8px 0; letter-spacing: -0.5px;">
                            {currency_symbol} {rec.total_payroll_cost:,.2f}
                        </div>
                        <div class="hds-text-muted" style="font-size: 11px; font-weight: 500;">
                            Period: {month_name} ({fy_name})
                        </div>
                    </div>

                    <!-- Card 2: Net Salary Payable (Payrun Net - Emerald Green) -->
                    <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'total_net_pay')" data-card-type="total_net_pay" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #4ade80 !important; cursor: pointer;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #4ade80 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-credit-card me-1"/> Net Salary Payable
                            </span>
                            <span style="font-size: 11px; color: #4ade80; font-weight: 600;">Disbursement &darr;</span>
                        </div>
                        <div class="hds-text-primary" style="font-size: 24px; font-weight: 800; margin: 8px 0; letter-spacing: -0.5px;">
                            {currency_symbol} {rec.total_net_pay:,.2f}
                        </div>
                        <div style="font-size: 11px; color: #4ade80; font-weight: 600;">
                            Disbursable Amount
                        </div>
                    </div>

                    <!-- Card 3: Active Employees (Payrun Gross / Workforce - Sky Blue) -->
                    <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'active_employee_count')" data-card-type="active_employee_count" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #38bdf8 !important; cursor: pointer;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #38bdf8 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-users me-1"/> Active Employees
                            </span>
                            <span style="font-size: 11px; color: #38bdf8; font-weight: 600;">Workforce &darr;</span>
                        </div>
                        <div class="hds-text-primary" style="font-size: 24px; font-weight: 800; margin: 8px 0; letter-spacing: -0.5px;">
                            {rec.active_employee_count}
                        </div>
                        <div style="font-size: 11px; color: #38bdf8; font-weight: 600;">
                            Active Workforce
                        </div>
                    </div>

                    <!-- Card 4: TDS This Month (Payrun TDS - Indigo) -->
                    <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'tds_this_month')" data-card-type="tds_this_month" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #818cf8 !important; cursor: pointer;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #818cf8 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-shield me-1"/> TDS This Month
                            </span>
                            <span style="font-size: 11px; color: #818cf8; font-weight: 600;">TDS Details &darr;</span>
                        </div>
                        <div class="hds-text-primary" style="font-size: 24px; font-weight: 800; margin: 8px 0; letter-spacing: -0.5px;">
                            {currency_symbol} {rec.tds_this_month:,.2f}
                        </div>
                        <div style="font-size: 11px; color: #818cf8; font-weight: 600;">
                            YTD: {currency_symbol} {rec.tds_ytd_total:,.2f}
                        </div>
                    </div>

                    <!-- Card 5: Pending Actions (Payrun Anomaly / Shortage - Amber) -->
                    <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'pending_actions')" data-card-type="pending_actions" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #fbbf24 !important; cursor: pointer;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #fbbf24 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-exclamation-circle me-1"/> Pending Actions
                            </span>
                            <span style="font-size: 11px; color: #fbbf24; font-weight: 600;">View Issues &darr;</span>
                        </div>
                        <div style="font-size: 24px; font-weight: 800; margin: 8px 0; color: #fbbf24; letter-spacing: -0.5px;">
                            {rec.pending_actions_count}
                        </div>
                        <div style="font-size: 11px; color: #fbbf24; font-weight: 600;">
                            Requires HR Attention
                        </div>
                    </div>

                    <!-- Card 6: Final Settlements Due (Payrun Danger / Settlements - Rose) -->
                    <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'final_settlements_due')" data-card-type="final_settlements_due" class="hds-dash-card o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 18px; border-top: 4px solid #f87171 !important; cursor: pointer;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="small fw-semibold text-uppercase" style="color: #f87171 !important; font-size: 11px; letter-spacing: 0.5px;">
                                <i class="fa fa-user-times me-1"/> Final Settlements Due
                            </span>
                            <span style="font-size: 11px; color: #f87171; font-weight: 600;">View Due &darr;</span>
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
                    </div>
                </div>

                <!-- 2. ACTION REQUIRED SECTION (HIGH VISIBILITY ALERTS) -->
                <div class="hds-dash-card" style="padding: 18px; margin-bottom: 22px; background-color: var(--hds-alert-bg) !important; border: 1px solid var(--hds-alert-border) !important;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
                        <div style="font-size: 15px; font-weight: 700; color: var(--hds-alert-header); display: flex; align-items: center; gap: 8px;">
                            <i class="fa fa-exclamation-triangle" style="color: #f87171;"/> Action Required
                        </div>
                        <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">Immediate HR Verification Required (Click card to view records below)</div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
                        <!-- Missing PAN -->
                        <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'missing_pan')" data-card-type="missing_pan" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px 14px; border-left: 4px solid #ef4444 !important; cursor: pointer;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="font-size: 12px; font-weight: 700; color: #f87171;">
                                    <i class="fa fa-id-card me-1"/> {rec.missing_pan_count} Employees Missing PAN
                                </div>
                                <span style="font-size: 12px; color: #ef4444; font-weight: 700;">&darr;</span>
                            </div>
                            <div class="hds-text-muted" style="font-size: 11px; margin-top: 4px;">Impacts 20% flat TDS rate u/s 206AA &bull; <u style="color: #f87171;">Click to view</u></div>
                        </div>

                        <!-- Missing Bank -->
                        <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'missing_bank')" data-card-type="missing_bank" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px 14px; border-left: 4px solid #f97316 !important; cursor: pointer;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="font-size: 12px; font-weight: 700; color: #fb923c;">
                                    <i class="fa fa-university me-1"/> {rec.missing_bank_count} Employees Missing Bank
                                </div>
                                <span style="font-size: 12px; color: #f97316; font-weight: 700;">&darr;</span>
                            </div>
                            <div class="hds-text-muted" style="font-size: 11px; margin-top: 4px;">Blocks automated salary advice file &bull; <u style="color: #fb923c;">Click to view</u></div>
                        </div>

                        <!-- Pending Declarations -->
                        <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'pending_declarations')" data-card-type="pending_declarations" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px 14px; border-left: 4px solid #f59e0b !important; cursor: pointer;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="font-size: 12px; font-weight: 700; color: #fbbf24;">
                                    <i class="fa fa-file-text-o me-1"/> {rec.pending_declarations_count} Declarations Pending
                                </div>
                                <span style="font-size: 12px; color: #f59e0b; font-weight: 700;">&darr;</span>
                            </div>
                            <div class="hds-text-muted" style="font-size: 11px; margin-top: 4px;">Pending Tax Firm / HR verification &bull; <u style="color: #fbbf24;">Click to view</u></div>
                        </div>

                        <!-- Payslips Pending Validation (Draft & To Validate) -->
                        <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'attendance_exceptions')" data-card-type="attendance_exceptions" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px 14px; border-left: 4px solid #8b5cf6 !important; cursor: pointer;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="font-size: 12px; font-weight: 700; color: #c084fc;">
                                    <i class="fa fa-file-text-o me-1"/> {rec.unconfirmed_slips_count} Payslips to Validate
                                </div>
                                <span style="font-size: 12px; color: #8b5cf6; font-weight: 700;">&darr;</span>
                            </div>
                            <div style="margin-top: 6px; display: flex; align-items: center; gap: 8px;">
                                <span style="background: rgba(148, 163, 184, 0.2); color: var(--hds-text-primary); border: 1px solid rgba(148, 163, 184, 0.35); padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600;">Draft: <b style="color: #38bdf8;">{rec.draft_slips_count}</b></span>
                                <span style="background: rgba(192, 132, 252, 0.2); color: var(--hds-text-primary); border: 1px solid rgba(192, 132, 252, 0.35); padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600;">To Validate: <b style="color: #c084fc;">{rec.verify_slips_count}</b></span>
                            </div>
                            <div class="hds-text-muted" style="font-size: 10.5px; margin-top: 4px;">Pending verification / confirmation &bull; <u style="color: #c084fc;">Click to view</u></div>
                        </div>
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
                            <span role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'new_joiners')" data-card-type="new_joiners" class="o_hds_dashboard_card_clickable" style="font-size: 11px; font-weight: 700; color: #818cf8; background: rgba(129, 140, 248, 0.15); border: 1px solid rgba(129, 140, 248, 0.3); padding: 4px 10px; border-radius: 12px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer;">
                                Count: {rec.new_joiners_count} &darr;
                            </span>
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
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'missing_pan')" data-card-type="missing_pan" class="o_hds_dashboard_card_clickable" style="text-decoration: none; color: inherit; display: block; padding: 2px 4px; cursor: pointer;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; margin-bottom: 5px;">
                                    <span class="hds-text-secondary">PAN Completeness</span>
                                    <span style="color: #818cf8;">{rec.pan_health_pct}% &bull; <u>View</u></span>
                                </div>
                                <div style="width: 100%; background: var(--hds-track-bg); height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="width: {rec.pan_health_pct}%; background: #818cf8; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>

                            <!-- Bank Details Completeness (Emerald) -->
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'missing_bank')" data-card-type="missing_bank" class="o_hds_dashboard_card_clickable" style="text-decoration: none; color: inherit; display: block; padding: 2px 4px; cursor: pointer;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; margin-bottom: 5px;">
                                    <span class="hds-text-secondary">Bank Details Completeness</span>
                                    <span style="color: #34d399;">{rec.bank_health_pct}% &bull; <u>View</u></span>
                                </div>
                                <div style="width: 100%; background: var(--hds-track-bg); height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="width: {rec.bank_health_pct}%; background: #34d399; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>

                            <!-- Aadhaar Completeness (Sky Blue) -->
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'aadhaar_health')" data-card-type="aadhaar_health" class="o_hds_dashboard_card_clickable" style="text-decoration: none; color: inherit; display: block; padding: 2px 4px; cursor: pointer;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; margin-bottom: 5px;">
                                    <span class="hds-text-secondary">Aadhaar / ID Completeness</span>
                                    <span style="color: #38bdf8;">{rec.aadhaar_health_pct}% &bull; <u>View</u></span>
                                </div>
                                <div style="width: 100%; background: var(--hds-track-bg); height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="width: {rec.aadhaar_health_pct}%; background: #38bdf8; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>

                            <!-- Emergency Contact Completeness (Amber) -->
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'contact_health')" data-card-type="contact_health" class="o_hds_dashboard_card_clickable" style="text-decoration: none; color: inherit; display: block; padding: 2px 4px; cursor: pointer;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; margin-bottom: 5px;">
                                    <span class="hds-text-secondary">Emergency Contact Completeness</span>
                                    <span style="color: #fbbf24;">{rec.contact_health_pct}% &bull; <u>View</u></span>
                                </div>
                                <div style="width: 100%; background: var(--hds-track-bg); height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="width: {rec.contact_health_pct}%; background: #fbbf24; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>

                        </div>
                    </div>
                </div>

                <!-- 4. STATUTORY NUMBER VALIDATION & COMPLIANCE SECTION -->
                <div class="hds-dash-card" style="padding: 18px; margin-bottom: 22px;">
                    <div style="font-size: 14px; font-weight: 700; margin-bottom: 12px; border-bottom: 1px solid var(--hds-row-border); padding-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <span class="hds-text-primary">
                            <i class="fa fa-shield me-1" style="color: #38bdf8;"/> Statutory Identifier Compliance
                        </span>
                        <span class="hds-text-muted" style="font-size: 12px; font-weight: 600;">Active Workforce: {rec.active_employee_count} Employees</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; font-size: 12px;">

                        <!-- EPF Tile -->
                        <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'epf_status')" data-card-type="epf_status" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                            <div class="hds-text-primary" style="font-size: 12px; font-weight: 700; border-bottom: 1px dashed var(--hds-row-border); padding-bottom: 4px; margin-bottom: 6px; display: flex; justify-content: space-between;">
                                <span>EPF (UAN / PF No)</span>
                                <span style="font-size: 10px; color: #818cf8;">&darr;</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span style="color: #4ade80; font-weight: 600;">Complete UAN:</span>
                                <span style="font-weight: 700; color: #4ade80;">{rec.epf_complete_count}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: #f87171; font-weight: 600;">Missing UAN:</span>
                                <span style="font-weight: 700; color: #f87171;">{rec.epf_missing_count}</span>
                            </div>
                        </div>

                        <!-- ESIC Tile -->
                        <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'esic_status')" data-card-type="esic_status" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                            <div class="hds-text-primary" style="font-size: 12px; font-weight: 700; border-bottom: 1px dashed var(--hds-row-border); padding-bottom: 4px; margin-bottom: 6px; display: flex; justify-content: space-between;">
                                <span>ESIC (IP Number)</span>
                                <span style="font-size: 10px; color: #818cf8;">&darr;</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span style="color: #4ade80; font-weight: 600;">Complete IP:</span>
                                <span style="font-weight: 700; color: #4ade80;">{rec.esic_complete_count}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: #f87171; font-weight: 600;">Missing IP:</span>
                                <span style="font-weight: 700; color: #f87171;">{rec.esic_missing_count}</span>
                            </div>
                        </div>

                        <!-- LWF Tile -->
                        <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'lwf_status')" data-card-type="lwf_status" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                            <div class="hds-text-primary" style="font-size: 12px; font-weight: 700; border-bottom: 1px dashed var(--hds-row-border); padding-bottom: 4px; margin-bottom: 6px; display: flex; justify-content: space-between;">
                                <span>LWF Registration</span>
                                <span style="font-size: 10px; color: #818cf8;">&darr;</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span style="color: #4ade80; font-weight: 600;">Complete Number:</span>
                                <span style="font-weight: 700; color: #4ade80;">{rec.lwf_complete_count}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: #f87171; font-weight: 600;">Missing Number:</span>
                                <span style="font-weight: 700; color: #f87171;">{rec.lwf_missing_count}</span>
                            </div>
                        </div>

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
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'epf_liability')" data-card-type="epf_liability" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">EPF / PF Liability</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.epf_total_liability:,.2f}</div>
                                <div style="color: #4ade80; font-size: 10px; font-weight: 600; margin-top: 4px;">🟢 ECR Ready &bull; <u>View</u></div>
                            </div>
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'esic_liability')" data-card-type="esic_liability" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">ESIC Liability</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.esic_total_liability:,.2f}</div>
                                <div style="color: #4ade80; font-size: 10px; font-weight: 600; margin-top: 4px;">🟢 Ready for Filing &bull; <u>View</u></div>
                            </div>
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'pt_liability')" data-card-type="pt_liability" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">Professional Tax (PT)</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.pt_total_liability:,.2f}</div>
                                <div style="color: #4ade80; font-size: 10px; font-weight: 600; margin-top: 4px;">🟢 State Slabs Applied &bull; <u>View</u></div>
                            </div>
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'tds_withholding')" data-card-type="tds_withholding" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">TDS Withholding</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.tds_this_month:,.2f}</div>
                                <div style="color: #4ade80; font-size: 10px; font-weight: 600; margin-top: 4px;">🟢 Form 24Q Ready &bull; <u>View</u></div>
                            </div>
                        </div>
                    </div>

                    <!-- Tax & TDS Card -->
                    <div class="hds-dash-card" style="padding: 18px;">
                        <div class="hds-text-primary" style="font-size: 14px; font-weight: 700; margin-bottom: 12px; border-bottom: 1px solid var(--hds-row-border); padding-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                            <i class="fa fa-calculator" style="color: #818cf8;"/> Tax Regime &amp; Declarations Breakdown
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'old_regime')" data-card-type="old_regime" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">Old Regime Opted</div>
                                <div style="font-weight: 700; font-size: 14px; color: #818cf8; margin-top: 2px;">{rec.old_regime_count} Employees &darr;</div>
                            </div>
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'new_regime')" data-card-type="new_regime" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">New Regime (115BAC)</div>
                                <div style="font-weight: 700; font-size: 14px; color: #38bdf8; margin-top: 2px;">{rec.new_regime_count} Employees &darr;</div>
                            </div>
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'tds_ytd')" data-card-type="tds_ytd" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">TDS YTD Total</div>
                                <div class="hds-text-primary" style="font-weight: 700; font-size: 14px; margin-top: 2px;">{currency_symbol} {rec.tds_ytd_total:,.2f} &darr;</div>
                            </div>
                            <div role="button" tabindex="0" onclick="window.hdsCardClick &amp;&amp; window.hdsCardClick(this, 'pending_declarations')" data-card-type="pending_declarations" class="hds-subcard o_hds_dashboard_card_clickable" style="text-decoration: none; display: block; padding: 12px; cursor: pointer;">
                                <div class="hds-text-muted" style="font-size: 11px; font-weight: 600;">Pending Declarations</div>
                                <div style="font-weight: 700; font-size: 14px; color: #fbbf24; margin-top: 2px;">{rec.pending_declarations_count} Pending &darr;</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 6. HISTORICAL PAYROLL COST TREND CHART (PAYRUN PALETTE) -->
                <div class="hds-dash-card" style="padding: 18px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid var(--hds-row-border); padding-bottom: 8px;">
                        <span class="hds-text-primary" style="font-size: 14px; font-weight: 700; display: flex; align-items: center; gap: 8px;">
                            <i class="fa fa-line-chart" style="color: #c084fc;"/> Historical Payroll Cost Trend (Last 6 Months)
                        </span>
                        <span class="hds-text-muted" style="font-size: 11px; font-weight: 600;">
                            Stacked by Cost Component &bull; Hover for details &bull; Click to view slips
                        </span>
                    </div>
                    <div style="display: flex; align-items: flex-end; justify-content: space-around; height: 115px; padding: 0 20px;">
                        {trend_bars_html}
                    </div>
                    {trend_breakdown_html}
                </div>

                <!-- 7. INLINE DETAILS CONTAINER (LOADS ON CURRENT PAGE) -->
                <div id="hds_dashboard_inline_details" class="hds-inline-panel" style="display: none; margin-top: 24px;"></div>

            </div>
            """

    def action_refresh_dashboard(self):
        self.ensure_one()
        self.env.invalidate_all()
        self._compute_dashboard_metrics()
        self._compute_dashboard_html()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def web_read(self, specification: dict) -> list[dict]:
        self.env.invalidate_all()
        for rec in self:
            rec._compute_dashboard_metrics()
            rec._compute_dashboard_html()
        return super().web_read(specification)

    def read(self, fields=None, load='_classic_read'):
        self.env.invalidate_all()
        for rec in self:
            rec._compute_dashboard_metrics()
            rec._compute_dashboard_html()
        return super().read(fields=fields, load=load)

    @api.model
    def get_card_action(self, dashboard_id=None, card_type=None, month_num=None, fy_id=None):
        """
        Returns an ir.actions.act_window action dict for Odoo web client
        to navigate to the corresponding list view in the current window.
        Odoo breadcrumbs will allow returning to the Payroll Dashboard smoothly.
        """
        rec = self.browse(dashboard_id) if dashboard_id else self.search([], limit=1)
        today = fields.Date.today()
        m_num = int(month_num or (rec.payroll_month_num if rec else today.month) or today.month)

        fy = rec.financial_year_id if (rec and rec.financial_year_id) else (self.env['tds.financial.year'].browse(fy_id) if fy_id else None)
        if not fy:
            fy = self.env['tds.financial.year'].search([('start_date', '<=', today), ('end_date', '>=', today)], limit=1)
        if not fy:
            fy = self.env['tds.financial.year'].search([], order='id desc', limit=1)

        year = today.year
        if fy and getattr(fy, 'start_date', False):
            year = fy.start_date.year if m_num >= 4 else fy.end_date.year

        month_start = date(year, m_num, 1)
        month_end = date(year, m_num, calendar.monthrange(year, m_num)[1])
        month_name = calendar.month_name[m_num]
        active_emps = self.env['hr.employee'].search([('active', '=', True)])

        # 1. Payslips / Total Payroll Cost / Net Salary / TDS This Month / Liabilities
        if card_type in ('total_payroll_cost', 'total_net_pay', 'tds_this_month', 'tds_withholding', 'epf_liability', 'esic_liability', 'pt_liability'):
            title_map = {
                'total_payroll_cost': f"Total Payroll Cost Slips — {month_name} {year}",
                'total_net_pay': f"Net Salary Disbursement — {month_name} {year}",
                'tds_this_month': f"TDS Withholding Slips — {month_name} {year}",
                'tds_withholding': f"TDS Withholding Slips — {month_name} {year}",
                'epf_liability': f"EPF Liability Slips — {month_name} {year}",
                'esic_liability': f"ESIC Liability Slips — {month_name} {year}",
                'pt_liability': f"Professional Tax Slips — {month_name} {year}",
            }
            period_domain = [
                ('date_from', '<=', month_end),
                ('date_to', '>=', month_start),
                ('state', '!=', 'cancel'),
            ]
            if 'company_id' in self.env['hr.payslip']._fields:
                period_domain.append(('company_id', 'in', self.env.companies.ids))
            return {
                'type': 'ir.actions.act_window',
                'name': title_map.get(card_type, 'Payslips'),
                'res_model': 'hr.payslip',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': period_domain,
                'target': 'current',
            }

        # 2. Draft / Attendance Exceptions -> Payslips to Validate
        if card_type == 'attendance_exceptions':
            company_filter = [('company_id', 'in', self.env.companies.ids)] if 'company_id' in self.env['hr.payslip']._fields else []
            slips = self.env['hr.payslip'].search([('date_from', '<=', month_end), ('date_to', '>=', month_start), ('state', 'in', ('draft', 'verify'))] + company_filter)
            domain = [('date_from', '<=', month_end), ('date_to', '>=', month_start), ('state', 'in', ('draft', 'verify'))] if slips else [('state', 'in', ('draft', 'verify'))]
            return {
                'type': 'ir.actions.act_window',
                'name': f"Payslips to Validate — {month_name} {year}",
                'res_model': 'hr.payslip',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': domain,
                'target': 'current',
            }

        # 3. Missing PAN
        if card_type in ('missing_pan', 'pan_health'):
            missing_emps = active_emps.filtered(lambda e: not self._has_pan(e))
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees Missing PAN',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', missing_emps.ids)],
                'target': 'current',
            }

        # 4. Missing Bank
        if card_type in ('missing_bank', 'bank_health'):
            missing_emps = active_emps.filtered(lambda e: not self._has_bank_account(e))
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees Missing Bank Details',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', missing_emps.ids)],
                'target': 'current',
            }

        # 5. Pending Declarations / TDS YTD
        if card_type in ('pending_declarations', 'tds_ytd'):
            return {
                'type': 'ir.actions.act_window',
                'name': 'Pending Tax Declarations',
                'res_model': 'tds.employee.declaration',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('state', 'in', ('submitted', 'proof_submitted', 'proof_under_review'))],
                'target': 'current',
            }

        # 6. New Joiners
        if card_type == 'new_joiners':
            emp_fields = self.env['hr.employee']._fields
            join_field = next((f for f in ('joining_date', 'date_of_joining', 'hds_in_doj', 'first_contract_date', 'contract_date_start', 'create_date') if f in emp_fields), None)
            joiner_domain = [('active', '=', True)]
            if join_field:
                joiner_domain.extend([(join_field, '>=', month_start), (join_field, '<=', month_end)])
            return {
                'type': 'ir.actions.act_window',
                'name': f"New Joiners — {month_name} {year}",
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': joiner_domain,
                'target': 'current',
            }

        # 7. Final Settlements
        if card_type == 'final_settlements_due':
            if 'hds.final.settlement' in self.env:
                return {
                    'type': 'ir.actions.act_window',
                    'name': f"Final Settlements Due — {month_name} {year}",
                    'res_model': 'hds.final.settlement',
                    'view_mode': 'list,form',
                    'views': [[False, 'list'], [False, 'form']],
                    'domain': [('state', 'in', ('draft', 'review', 'approved'))],
                    'target': 'current',
                }
            return {
                'type': 'ir.actions.act_window',
                'name': 'Exited / Inactive Employees',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('active', '=', False)],
                'target': 'current',
            }

        # 8. Tax Regimes
        if card_type == 'old_regime':
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees in Old Tax Regime',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': ['&', ('active', '=', True), ('hds_in_tax_regime', '=', 'old')],
                'target': 'current',
            }
        if card_type == 'new_regime':
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees in New Tax Regime (115BAC)',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': ['&', ('active', '=', True), ('hds_in_tax_regime', '=', 'new')],
                'target': 'current',
            }

        # 9. Statutory Applicability (EPF / ESIC / LWF / Readiness - Filter Missing Only)
        if card_type == 'epf_status':
            from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
            comp_service = StatutoryComplianceValidationService(self.env)
            epf_missing = active_emps.filtered(lambda e: getattr(e, 'hds_in_epf_applicable', False) and not comp_service.validate_employee_epf(e)[0])
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees Missing EPF UAN',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', epf_missing.ids)],
                'target': 'current',
            }
        if card_type == 'esic_status':
            from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
            comp_service = StatutoryComplianceValidationService(self.env)
            esic_missing = active_emps.filtered(lambda e: getattr(e, 'hds_in_esic_applicable', False) and not comp_service.validate_employee_esic(e)[0])
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees Missing ESIC IP Number',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', esic_missing.ids)],
                'target': 'current',
            }
        if card_type == 'lwf_status':
            from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
            comp_service = StatutoryComplianceValidationService(self.env)
            lwf_missing = active_emps.filtered(lambda e: getattr(e, 'hds_in_lwf_applicable', False) and not comp_service.validate_employee_lwf(e)[0])
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees Missing LWF Registration',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', lwf_missing.ids)],
                'target': 'current',
            }
        if card_type in ('readiness_status', 'statutory_errors'):
            from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
            comp_service = StatutoryComplianceValidationService(self.env)
            error_emps = active_emps.filtered(lambda e: not comp_service.validate_employee_all(e)['is_compliant'])
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees with Statutory Data Errors',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', error_emps.ids)],
                'target': 'current',
            }

        # 10. Aadhaar / Emergency Contact Health
        if card_type == 'aadhaar_health':
            missing_emps = active_emps.filtered(lambda e: not self._has_aadhaar(e))
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees Missing Aadhaar',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', missing_emps.ids)],
                'target': 'current',
            }
        if card_type == 'contact_health':
            missing_emps = active_emps.filtered(lambda e: not self._has_emergency_contact(e))
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employees Missing Emergency Contact',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', missing_emps.ids)],
                'target': 'current',
            }

        # 11. General pending actions / Default Active Employees
        return {
            'type': 'ir.actions.act_window',
            'name': 'Active Employees',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('active', '=', True)],
            'target': 'current',
        }

    @api.model
    def get_card_details(self, dashboard_id=None, card_type=None, month_num=None, fy_id=None):
        """
        Fetches structured records for the clicked dashboard card to display inline
        on the current page without navigating to a new page.
        """
        rec = self.browse(dashboard_id) if dashboard_id else self.search([], limit=1)
        today = fields.Date.today()
        m_num = int(month_num or (rec.payroll_month_num if rec else today.month) or today.month)

        fy = rec.financial_year_id if (rec and rec.financial_year_id) else (self.env['tds.financial.year'].browse(fy_id) if fy_id else None)
        if not fy:
            fy = self.env['tds.financial.year'].search([('start_date', '<=', today), ('end_date', '>=', today)], limit=1)
        if not fy:
            fy = self.env['tds.financial.year'].search([], order='id desc', limit=1)

        year = today.year
        if fy and getattr(fy, 'start_date', False):
            year = fy.start_date.year if m_num >= 4 else fy.end_date.year

        month_start = date(year, m_num, 1)
        month_end = date(year, m_num, calendar.monthrange(year, m_num)[1])
        month_name = calendar.month_name[m_num]
        currency_symbol = (rec.currency_id.symbol if rec and rec.currency_id else self.env.company.currency_id.symbol) or '₹'

        emp_model = self.env['hr.employee']
        active_emps = emp_model.search([('active', '=', True)])

        columns = []
        rows = []
        title = "Details"
        badge = ""

        # 1. Payslips / Total Payroll Cost / Net Salary
        if card_type in ('total_payroll_cost', 'total_net_pay', 'payslips'):
            title = f"Total Payroll Cost Slips — {month_name} {year}" if card_type == 'total_payroll_cost' else f"Net Salary Disbursement — {month_name} {year}"
            period_domain = [
                ('date_from', '<=', month_end),
                ('date_to', '>=', month_start),
                ('state', '!=', 'cancel'),
            ]
            if 'company_id' in self.env['hr.payslip']._fields:
                period_domain.append(('company_id', 'in', self.env.companies.ids))
            slips = self.env['hr.payslip'].search(period_domain, order='date_to desc, id desc')
            badge = f"{len(slips)} Payslips"
            columns = [
                {'key': 'employee', 'label': 'Employee'},
                {'key': 'number', 'label': 'Slip Ref'},
                {'key': 'period', 'label': 'Period'},
                {'key': 'basic', 'label': 'Basic'},
                {'key': 'gross', 'label': 'Gross Wage'},
                {'key': 'net', 'label': 'Net Wage'},
                {'key': 'state', 'label': 'State'},
                {'key': 'action', 'label': 'Action'}
            ]
            for s in slips[:100]:
                basic_val = float(getattr(s, 'basic_wage', 0.0) or 0.0)
                gross_val = float(getattr(s, 'gross_amount', None) or getattr(s, 'gross_wage', 0.0) or 0.0)
                net_val = float(getattr(s, 'net_amount', None) or getattr(s, 'net_wage', 0.0) or 0.0)
                state_lbl = dict(s._fields['state'].selection).get(s.state, s.state) if 'state' in s._fields else s.state
                rows.append({
                    'id': s.id,
                    'model': 'hr.payslip',
                    'cells': {
                        'employee': s.employee_id.name if s.employee_id else 'N/A',
                        'number': s.number or s.name or 'Draft',
                        'period': f"{s.date_from.strftime('%d %b')} - {s.date_to.strftime('%d %b')}" if s.date_from and s.date_to else '',
                        'basic': f"{currency_symbol} {basic_val:,.2f}",
                        'gross': f"{currency_symbol} {gross_val:,.2f}",
                        'net': f"<b>{currency_symbol} {net_val:,.2f}</b>",
                        'state': f"<span class='badge bg-secondary'>{state_lbl}</span>",
                        'action': 'View Slip'
                    },
                    'action_label': 'View Slip'
                })

        # 2. Active Workforce
        elif card_type in ('active_employee_count', 'workforce'):
            title = "Active Workforce Overview"
            badge = f"{len(active_emps)} Employees"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'dept', 'label': 'Department'},
                {'key': 'job', 'label': 'Job Position'},
                {'key': 'pan', 'label': 'PAN Status'},
                {'key': 'bank', 'label': 'Bank Status'},
                {'key': 'action', 'label': 'Action'}
            ]
            for e in active_emps[:100]:
                has_pan = bool(getattr(e, 'hds_in_pan', False) or getattr(e, 'pan_no', False) or getattr(e, 'pan', False))
                has_bank = self._has_bank_account(e)
                rows.append({
                    'id': e.id,
                    'model': 'hr.employee',
                    'cells': {
                        'name': e.name,
                        'dept': e.department_id.name if e.department_id else '-',
                        'job': e.job_id.name if e.job_id else '-',
                        'pan': '<span class="text-success fw-semibold">✔ Valid</span>' if has_pan else '<span class="text-danger fw-semibold">✖ Missing</span>',
                        'bank': '<span class="text-success fw-semibold">✔ Registered</span>' if has_bank else '<span class="text-warning fw-semibold">✖ Missing</span>',
                        'action': 'View Profile'
                    },
                    'action_label': 'View Profile'
                })

        # 3. Missing PAN
        elif card_type in ('missing_pan', 'pan_health'):
            missing = active_emps.filtered(lambda e: not self._has_pan(e))
            title = "Employees Missing PAN (Action Required)"
            badge = f"{len(missing)} Employees"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'dept', 'label': 'Department'},
                {'key': 'job', 'label': 'Job Position'},
                {'key': 'impact', 'label': 'Statutory Impact'},
                {'key': 'action', 'label': 'Action'}
            ]
            rows = [{
                'id': e.id,
                'model': 'hr.employee',
                'cells': {
                    'name': e.name,
                    'dept': e.department_id.name if e.department_id else '-',
                    'job': e.job_id.name if e.job_id else '-',
                    'impact': '<span class="text-danger fw-bold">20% Flat TDS (u/s 206AA)</span>',
                    'action': 'Add PAN'
                },
                'action_label': 'Add PAN'
            } for e in missing]

        # 4. Missing Bank Details
        elif card_type in ('missing_bank', 'bank_health'):
            missing = active_emps.filtered(lambda e: not self._has_bank_account(e))
            title = "Employees Missing Bank Details (Action Required)"
            badge = f"{len(missing)} Employees"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'dept', 'label': 'Department'},
                {'key': 'job', 'label': 'Job Position'},
                {'key': 'impact', 'label': 'Disbursement Impact'},
                {'key': 'action', 'label': 'Action'}
            ]
            rows = [{
                'id': e.id,
                'model': 'hr.employee',
                'cells': {
                    'name': e.name,
                    'dept': e.department_id.name if e.department_id else '-',
                    'job': e.job_id.name if e.job_id else '-',
                    'impact': '<span class="text-warning fw-bold">Salary Advice Batch Blocked</span>',
                    'action': 'Add Bank Details'
                },
                'action_label': 'Add Bank Details'
            } for e in missing]

        # 5. Pending Declarations
        elif card_type == 'pending_declarations':
            title = "Pending Tax Declarations"
            decls = self.env['tds.employee.declaration'].search([
                ('state', 'in', ('submitted', 'proof_submitted', 'proof_under_review'))
            ], order='id desc')
            badge = f"{len(decls)} Pending"
            columns = [
                {'key': 'employee', 'label': 'Employee'},
                {'key': 'fy', 'label': 'Financial Year'},
                {'key': 'regime', 'label': 'Regime'},
                {'key': 'total', 'label': 'Total Declared'},
                {'key': 'state', 'label': 'Status'},
                {'key': 'action', 'label': 'Action'}
            ]
            rows = [{
                'id': d.id,
                'model': 'tds.employee.declaration',
                'cells': {
                    'employee': d.employee_id.name if d.employee_id else '-',
                    'fy': d.financial_year_id.name if d.financial_year_id else '-',
                    'regime': (dict(d._fields['tax_regime'].selection).get(d.tax_regime) if 'tax_regime' in d._fields else d.tax_regime) or 'N/A',
                    'total': f"{currency_symbol} {float(getattr(d, 'total_declared_amount', 0.0) or getattr(d, 'total_verified_amount', 0.0) or 0.0):,.2f}",
                    'state': f"<span class='badge bg-warning text-dark'>{d.state}</span>",
                    'action': 'Review Declaration'
                },
                'action_label': 'Review Declaration'
            } for d in decls]

        # 6. Payslips Pending Validation (Draft & To Validate)
        elif card_type == 'attendance_exceptions':
            title = f"Payslips to Validate — {month_name} {year}"
            company_filter = [('company_id', 'in', self.env.companies.ids)] if 'company_id' in self.env['hr.payslip']._fields else []
            slips = self.env['hr.payslip'].search([
                ('date_from', '<=', month_end),
                ('date_to', '>=', month_start),
                ('state', 'in', ('draft', 'verify')),
            ] + company_filter)
            if not slips:
                slips = self.env['hr.payslip'].search([('state', 'in', ('draft', 'verify'))] + company_filter)

            draft_count = len(slips.filtered(lambda s: s.state == 'draft'))
            verify_count = len(slips.filtered(lambda s: s.state == 'verify'))
            badge = f"Draft: {draft_count} | To Validate: {verify_count}"
            columns = [
                {'key': 'employee', 'label': 'Employee'},
                {'key': 'number', 'label': 'Slip Ref'},
                {'key': 'period', 'label': 'Period'},
                {'key': 'status', 'label': 'Stage'},
                {'key': 'action', 'label': 'Action'}
            ]
            rows = [{
                'id': s.id,
                'model': 'hr.payslip',
                'cells': {
                    'employee': s.employee_id.name if s.employee_id else '-',
                    'number': s.number or s.name or 'Draft',
                    'period': f"{s.date_from.strftime('%d %b')} - {s.date_to.strftime('%d %b')}" if s.date_from and s.date_to else '',
                    'status': f"<span class='badge' style='background: {'#64748b' if s.state == 'draft' else '#8b5cf6'}; color: #fff; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600;'>{'Draft' if s.state == 'draft' else 'To Validate'}</span>",
                    'action': 'Verify / Confirm'
                },
                'action_label': 'Verify / Confirm'
            } for s in slips]

        # 7. Final Settlements Due
        elif card_type == 'final_settlements_due':
            title = f"Final Settlements Due — {month_name} {year}"
            settlements = self.env['final.settlement'] if 'final.settlement' in self.env else []
            if 'final.settlement' in self.env:
                settlements = self.env['final.settlement'].search([
                    ('state', '!=', 'cancel'),
                    ('last_working_day', '>=', month_start),
                    ('last_working_day', '<=', month_end),
                ], order='last_working_day desc')
            badge = f"{len(settlements)} Settlements Due"
            columns = [
                {'key': 'employee', 'label': 'Employee'},
                {'key': 'lwd', 'label': 'Last Working Day'},
                {'key': 'net', 'label': 'Net Settlement'},
                {'key': 'state', 'label': 'Status'},
                {'key': 'action', 'label': 'Action'}
            ]
            for fs in settlements:
                net_amt = float(getattr(fs, 'net_payable', None) or getattr(fs, 'total_settlement', 0.0) or 0.0)
                st = dict(fs._fields['state'].selection).get(fs.state, fs.state) if 'state' in fs._fields else fs.state
                rows.append({
                    'id': fs.id,
                    'model': 'final.settlement',
                    'cells': {
                        'employee': fs.employee_id.name if fs.employee_id else '-',
                        'lwd': fs.last_working_day.strftime('%d %b %Y') if fs.last_working_day else '-',
                        'net': f"<b>{currency_symbol} {net_amt:,.2f}</b>",
                        'state': f"<span class='badge bg-secondary'>{st}</span>",
                        'action': 'Review Settlement'
                    },
                    'action_label': 'Review Settlement'
                })

        # 8. New Joiners
        elif card_type == 'new_joiners':
            title = f"New Joiners — {month_name} {year}"
            emp_fields = emp_model._fields
            join_field = next((f for f in ('joining_date', 'date_of_joining', 'hds_in_doj', 'first_contract_date', 'contract_date_start', 'create_date') if f in emp_fields), None)
            joiners = emp_model.search([
                (join_field, '>=', month_start),
                (join_field, '<=', month_end),
            ], order=f'{join_field} desc') if join_field else emp_model
            badge = f"{len(joiners)} Joiners"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'doj', 'label': 'Joining Date'},
                {'key': 'dept', 'label': 'Department'},
                {'key': 'pan', 'label': 'PAN Status'},
                {'key': 'bank', 'label': 'Bank Status'},
                {'key': 'action', 'label': 'Action'}
            ]
            for j in joiners:
                j_date_val = getattr(j, join_field, False) if join_field else False
                j_date = j_date_val.strftime('%d %b %Y') if (j_date_val and hasattr(j_date_val, 'strftime')) else '-'
                has_pan = bool(getattr(j, 'hds_in_pan', False) or getattr(j, 'pan_no', False) or getattr(j, 'pan', False))
                has_bank = self._has_bank_account(j)
                rows.append({
                    'id': j.id,
                    'model': 'hr.employee',
                    'cells': {
                        'name': j.name,
                        'doj': j_date,
                        'dept': j.department_id.name if j.department_id else '-',
                        'pan': '<span class="text-success">✔ Complete</span>' if has_pan else '<span class="text-danger fw-bold">✖ Missing</span>',
                        'bank': '<span class="text-success">✔ Complete</span>' if has_bank else '<span class="text-warning fw-bold">✖ Missing</span>',
                        'action': 'View Profile'
                    },
                    'action_label': 'View Profile'
                })

        # 9. All Pending Actions
        elif card_type == 'pending_actions':
            title = "All Pending Verification & Compliance Issues"
            for e in active_emps:
                issues = []
                has_pan = bool(getattr(e, 'hds_in_pan', False) or getattr(e, 'pan_no', False) or getattr(e, 'pan', False))
                has_bank = self._has_bank_account(e)
                if not has_pan:
                    issues.append('Missing PAN')
                if not has_bank:
                    issues.append('Missing Bank Details')
                if issues:
                    rows.append({
                        'id': e.id,
                        'model': 'hr.employee',
                        'cells': {
                            'name': e.name,
                            'dept': e.department_id.name if e.department_id else '-',
                            'issues': ", ".join(issues),
                            'severity': '<span class="badge bg-danger">High</span>' if 'Missing PAN' in issues else '<span class="badge bg-warning text-dark">Medium</span>',
                            'action': 'Fix Now'
                        },
                        'action_label': 'Fix Now'
                    })
            badge = f"{len(rows)} Issues Pending"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'dept', 'label': 'Department'},
                {'key': 'issues', 'label': 'Pending Issue(s)'},
                {'key': 'severity', 'label': 'Severity'},
                {'key': 'action', 'label': 'Action'}
            ]

        # 10. EPF Status / Missing / Liability
        elif card_type in ('epf_status', 'epf_missing', 'epf_complete', 'epf_liability'):
            from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
            comp_service = StatutoryComplianceValidationService(self.env)
            epf_emps = active_emps.filtered(lambda e: getattr(e, 'hds_in_epf_applicable', False))
            title = "Employees Missing EPF (UAN / PF No)"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'uan', 'label': 'UAN Number'},
                {'key': 'pf_no', 'label': 'PF Code / No'},
                {'key': 'validity', 'label': 'Status'},
                {'key': 'action', 'label': 'Action'}
            ]
            for e in epf_emps:
                valid, reason = comp_service.validate_employee_epf(e)
                if valid:
                    continue
                uan = getattr(e, 'hds_in_uan', '') or getattr(e, 'uan', '') or '-'
                pf = getattr(e, 'hds_in_pf_no', '') or getattr(e, 'pf_no', '') or '-'
                rows.append({
                    'id': e.id,
                    'model': 'hr.employee',
                    'cells': {
                        'name': e.name,
                        'uan': uan,
                        'pf_no': pf,
                        'validity': f'<span class="text-danger fw-bold">✖ {reason}</span>',
                        'action': 'Update EPF'
                    },
                    'action_label': 'Update EPF'
                })
            badge = f"{len(rows)} Employees Missing UAN"

        # 11. ESIC Status / Missing / Liability
        elif card_type in ('esic_status', 'esic_missing', 'esic_complete', 'esic_liability'):
            from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
            comp_service = StatutoryComplianceValidationService(self.env)
            esic_emps = active_emps.filtered(lambda e: getattr(e, 'hds_in_esic_applicable', False))
            title = "Employees Missing ESIC (IP Number)"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'ip_no', 'label': 'ESIC IP Number'},
                {'key': 'dispensary', 'label': 'Dispensary'},
                {'key': 'validity', 'label': 'Status'},
                {'key': 'action', 'label': 'Action'}
            ]
            for e in esic_emps:
                valid, reason = comp_service.validate_employee_esic(e)
                if valid:
                    continue
                ip = getattr(e, 'hds_in_esic_ip', '') or getattr(e, 'esic_no', '') or '-'
                disp = getattr(e, 'hds_in_esic_dispensary', '') or '-'
                rows.append({
                    'id': e.id,
                    'model': 'hr.employee',
                    'cells': {
                        'name': e.name,
                        'ip_no': ip,
                        'dispensary': disp,
                        'validity': f'<span class="text-danger fw-bold">✖ {reason}</span>',
                        'action': 'Update ESIC'
                    },
                    'action_label': 'Update ESIC'
                })
            badge = f"{len(rows)} Employees Missing IP"

        # 12. LWF Status
        elif card_type in ('lwf_status', 'lwf_missing', 'lwf_complete'):
            from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
            comp_service = StatutoryComplianceValidationService(self.env)
            lwf_emps = active_emps.filtered(lambda e: getattr(e, 'hds_in_lwf_applicable', False))
            title = "Employees Missing LWF Registration"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'state', 'label': 'State'},
                {'key': 'validity', 'label': 'Status'},
                {'key': 'action', 'label': 'Action'}
            ]
            for e in lwf_emps:
                valid, reason = comp_service.validate_employee_lwf(e)
                if valid:
                    continue
                st = getattr(e, 'hds_in_lwf_state_id', None)
                st_name = st.name if st else '-'
                rows.append({
                    'id': e.id,
                    'model': 'hr.employee',
                    'cells': {
                        'name': e.name,
                        'state': st_name,
                        'validity': f'<span class="text-danger fw-bold">✖ {reason}</span>',
                        'action': 'Update LWF'
                    },
                    'action_label': 'Update LWF'
                })
            badge = f"{len(rows)} Employees Missing LWF"

        # 13. Data Readiness & Compliance Issues
        elif card_type in ('readiness_status', 'statutory_errors'):
            from ..services.compliance.statutory_compliance_service import StatutoryComplianceValidationService
            comp_service = StatutoryComplianceValidationService(self.env)
            title = "Employees with Incomplete Compliance Data"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'pan', 'label': 'PAN'},
                {'key': 'bank', 'label': 'Bank'},
                {'key': 'epf', 'label': 'EPF'},
                {'key': 'esic', 'label': 'ESIC'},
                {'key': 'issues', 'label': 'Missing Information / Action Needed'},
                {'key': 'action', 'label': 'Action'}
            ]
            for e in active_emps:
                res = comp_service.validate_employee_all(e)
                if res['is_compliant']:
                    continue
                err_badges = []
                if not res['pan_valid']:
                    err_badges.append("<span class='badge' style='background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; font-size: 10.5px; margin-right: 4px; padding: 2px 7px; border-radius: 4px; font-weight: 600;'>Missing PAN</span>")
                if not res['bank_valid']:
                    err_badges.append("<span class='badge' style='background: #ffedd5; color: #ea580c; border: 1px solid #fdba74; font-size: 10.5px; margin-right: 4px; padding: 2px 7px; border-radius: 4px; font-weight: 600;'>Missing Bank</span>")
                if not res['epf_valid'] and getattr(e, 'hds_in_epf_applicable', False):
                    err_badges.append("<span class='badge' style='background: #f3e8ff; color: #9333ea; border: 1px solid #d8b4fe; font-size: 10.5px; margin-right: 4px; padding: 2px 7px; border-radius: 4px; font-weight: 600;'>Missing UAN</span>")
                if not res['esic_valid'] and getattr(e, 'hds_in_esic_applicable', False):
                    err_badges.append("<span class='badge' style='background: #e0e7ff; color: #4f46e5; border: 1px solid #c7d2fe; font-size: 10.5px; margin-right: 4px; padding: 2px 7px; border-radius: 4px; font-weight: 600;'>Missing IP</span>")
                if not res['lwf_valid'] and getattr(e, 'hds_in_lwf_applicable', False):
                    err_badges.append("<span class='badge' style='background: #e0f2fe; color: #0284c7; border: 1px solid #bae6fd; font-size: 10.5px; margin-right: 4px; padding: 2px 7px; border-radius: 4px; font-weight: 600;'>Missing LWF</span>")
                issues_html = "".join(err_badges) if err_badges else "<span class='text-muted'>-</span>"

                rows.append({
                    'id': e.id,
                    'model': 'hr.employee',
                    'cells': {
                        'name': e.name,
                        'pan': '<span class="text-success fw-bold">✔</span>' if res['pan_valid'] else '<span class="text-danger fw-bold">✖</span>',
                        'bank': '<span class="text-success fw-bold">✔</span>' if res['bank_valid'] else '<span class="text-danger fw-bold">✖</span>',
                        'epf': '<span class="text-success fw-bold">✔</span>' if res['epf_valid'] else '<span class="text-danger fw-bold">✖</span>',
                        'esic': '<span class="text-success fw-bold">✔</span>' if res['esic_valid'] else '<span class="text-danger fw-bold">✖</span>',
                        'issues': issues_html,
                        'action': 'Fix Profile'
                    },
                    'action_label': 'Fix Profile'
                })
            badge = f"{len(rows)} Employees with Incomplete Info"

        # 14. Old / New Tax Regimes
        elif card_type in ('old_regime', 'new_regime'):
            regime = 'old' if card_type == 'old_regime' else 'new'
            regime_title = "Old Tax Regime (With Exemptions)" if regime == 'old' else "New Tax Regime (Section 115BAC)"
            reg_emps = active_emps.filtered(lambda e: getattr(e, 'hds_in_tax_regime', 'new') == regime)
            title = f"Employees in {regime_title}"
            badge = f"{len(reg_emps)} Employees"
            columns = [
                {'key': 'name', 'label': 'Employee'},
                {'key': 'dept', 'label': 'Department'},
                {'key': 'pan', 'label': 'PAN'},
                {'key': 'action', 'label': 'Action'}
            ]
            rows = [{
                'id': e.id,
                'model': 'hr.employee',
                'cells': {
                    'name': e.name,
                    'dept': e.department_id.name if e.department_id else '-',
                    'pan': getattr(e, 'hds_in_pan', False) or getattr(e, 'pan_no', False) or '-',
                    'action': 'View Profile'
                },
                'action_label': 'View Profile'
            } for e in reg_emps]

        # 15. Aadhaar / Emergency Contact
        elif card_type == 'aadhaar_health':
            missing = active_emps.filtered(lambda e: not self._has_aadhaar(e))
            title = "Employees Missing Aadhaar"
            badge = f"{len(missing)} Employees"
            columns = [{'key': 'name', 'label': 'Employee'}, {'key': 'dept', 'label': 'Department'}, {'key': 'action', 'label': 'Action'}]
            rows = [{'id': e.id, 'model': 'hr.employee', 'cells': {'name': e.name, 'dept': e.department_id.name if e.department_id else '-', 'action': 'Add Aadhaar'}, 'action_label': 'Add Aadhaar'} for e in missing]

        elif card_type == 'contact_health':
            missing = active_emps.filtered(lambda e: not self._has_emergency_contact(e))
            title = "Employees Missing Emergency Contact"
            badge = f"{len(missing)} Employees"
            columns = [{'key': 'name', 'label': 'Employee'}, {'key': 'dept', 'label': 'Department'}, {'key': 'action', 'label': 'Action'}]
            rows = [{'id': e.id, 'model': 'hr.employee', 'cells': {'name': e.name, 'dept': e.department_id.name if e.department_id else '-', 'action': 'Add Contact'}, 'action_label': 'Add Contact'} for e in missing]

        # 16. TDS Withholding / YTD / PT Liability
        elif card_type in ('tds_this_month', 'tds_withholding', 'tds_ytd', 'pt_liability'):
            title = "TDS Withholding Slips" if 'tds' in card_type else f"Professional Tax (PT) Liabilities — {month_name} {year}"
            slips = self.env['hr.payslip'].search([
                ('date_from', '<=', month_end),
                ('date_to', '>=', month_start),
                ('state', '!=', 'cancel'),
            ], order='id desc')
            badge = f"{len(slips)} Payslips"
            columns = [
                {'key': 'employee', 'label': 'Employee'},
                {'key': 'number', 'label': 'Slip Ref'},
                {'key': 'gross', 'label': 'Gross Wage'},
                {'key': 'net', 'label': 'Net Wage'},
                {'key': 'state', 'label': 'State'},
                {'key': 'action', 'label': 'Action'}
            ]
            rows = [{
                'id': s.id,
                'model': 'hr.payslip',
                'cells': {
                    'employee': s.employee_id.name if s.employee_id else '-',
                    'number': s.number or s.name or 'Draft',
                    'gross': f"{currency_symbol} {float(getattr(s, 'gross_amount', None) or getattr(s, 'gross_wage', 0.0) or 0.0):,.2f}",
                    'net': f"<b>{currency_symbol} {float(getattr(s, 'net_amount', None) or getattr(s, 'net_wage', 0.0) or 0.0):,.2f}</b>",
                    'state': s.state,
                    'action': 'View Payslip'
                },
                'action_label': 'View Payslip'
            } for s in slips]

        # Fallback
        else:
            title = f"Dashboard Metric Overview — {card_type or 'General'}"
            badge = f"{len(active_emps)} Employees"
            columns = [{'key': 'name', 'label': 'Name'}, {'key': 'action', 'label': 'Action'}]
            rows = [{'id': e.id, 'model': 'hr.employee', 'cells': {'name': e.name, 'action': 'View'}, 'action_label': 'View'} for e in active_emps[:50]]

        return {
            'card_type': card_type,
            'title': title,
            'badge': badge,
            'columns': columns,
            'rows': rows,
            'empty_message': f"No records found for {title}.",
        }


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
