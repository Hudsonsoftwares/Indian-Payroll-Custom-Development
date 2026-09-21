# -*- coding: utf-8 -*-
import logging
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    last_contract_expiry_notified_date = fields.Date(
        string='Last Contract Expiry Notified Date',
        copy=False,
        help="Tracks the contract end date for which an expiration notice was last sent, preventing duplicate daily notifications."
    )
    last_work_permit_expiry_notified_date = fields.Date(
        string='Last Work Permit Expiry Notified Date',
        copy=False,
        help="Tracks the work permit expiry date for which an expiration notice was last sent, preventing duplicate daily notifications."
    )

    contract_expiry_display_date = fields.Date(
        string='Contract Expiration Date',
        compute='_compute_expiry_display_dates',
        help="Resolved end date of employee contract."
    )
    work_permit_expiry_display_date = fields.Date(
        string='Work Permit Expiration Date',
        compute='_compute_expiry_display_dates',
        help="Resolved expiration date of employee work permit."
    )

    def _compute_expiry_display_dates(self):
        for emp in self:
            emp.contract_expiry_display_date = emp._get_contract_expiration_date()
            emp.work_permit_expiry_display_date = emp._get_work_permit_expiration_date()

    def _get_contract_expiration_date(self):
        """Resolves employee contract end date across Odoo 19 version_id and contract fields."""
        self.ensure_one()
        for fname in ('contract_date_end', 'date_end'):
            val = getattr(self, fname, False)
            if val:
                return val if isinstance(val, date) else fields.Date.from_string(val)
        if hasattr(self, 'version_id') and self.version_id:
            for fname in ('contract_date_end', 'date_end'):
                val = getattr(self.version_id, fname, False)
                if val:
                    return val if isinstance(val, date) else fields.Date.from_string(val)
        if hasattr(self, 'contract_id') and self.contract_id:
            val = getattr(self.contract_id, 'date_end', False)
            if val:
                return val if isinstance(val, date) else fields.Date.from_string(val)
        return False

    def _get_work_permit_expiration_date(self):
        """Resolves work permit expiry date across core and localization fields."""
        self.ensure_one()
        for fname in ('work_permit_expiration_date', 'work_permit_expiry_date'):
            val = getattr(self, fname, False)
            if val:
                return val if isinstance(val, date) else fields.Date.from_string(val)
        return False

    def _get_employee_notification_email(self):
        """Resolves best email address for the employee."""
        self.ensure_one()
        return (
            self.work_email or
            (self.user_id.email if self.user_id else False) or
            (self.work_contact_id.email if hasattr(self, 'work_contact_id') and self.work_contact_id else False) or
            getattr(self, 'private_email', False) or
            False
        )

    def _get_hr_notification_recipients(self, company):
        """
        Resolves HR / management users and partners to receive expiry alerts.
        Returns tuple of (user_records, partner_records, email_list).
        """
        self.ensure_one()
        users = self.env['res.users']

        # 1. Configured custom notification recipients on company
        if hasattr(company, 'expiry_notification_user_ids') and company.expiry_notification_user_ids:
            users |= company.expiry_notification_user_ids

        # 2. Employee designated HR Responsible
        if self.hr_responsible_id:
            users |= self.hr_responsible_id

        # 3. Direct Manager
        if self.parent_id and self.parent_id.user_id:
            users |= self.parent_id.user_id

        # 4. Fallback: Payroll Managers group if no specific users resolved
        if not users:
            manager_group = self.env.ref('hudson_payroll_base.group_payroll_manager', raise_if_not_found=False)
            if manager_group:
                users |= manager_group.users.filtered(lambda u: company.id in u.company_ids.ids)

        if not users:
            hr_group = self.env.ref('hr.group_hr_user', raise_if_not_found=False)
            if hr_group:
                users |= hr_group.users.filtered(lambda u: company.id in u.company_ids.ids)

        partners = users.mapped('partner_id').filtered(lambda p: bool(p.email))
        emails = [p.email for p in partners if p.email]
        return users, partners, emails

    @api.model
    def notify_expiring_contract_work_permit(self):
        """
        Scheduled Action & Manual Trigger API:
        Evaluates active employees against company contract and work permit notice periods.
        Sends:
        1. Email notification to the employee.
        2. In-App Activity & Discuss Chatter message to HR & applicable users.
        3. Email notification to HR & applicable users.
        Prevents duplicate alerts using last notified date tracking.
        """
        today = fields.Date.today()
        companies = self.env['res.company'].search([])
        contract_notified_count = 0
        permit_notified_count = 0

        # Load mail templates
        tmpl_contract_emp = self.env.ref('hudson_payroll_base.mail_template_contract_expiry_employee', raise_if_not_found=False)
        tmpl_contract_hr = self.env.ref('hudson_payroll_base.mail_template_contract_expiry_hr', raise_if_not_found=False)
        tmpl_permit_emp = self.env.ref('hudson_payroll_base.mail_template_work_permit_expiry_employee', raise_if_not_found=False)
        tmpl_permit_hr = self.env.ref('hudson_payroll_base.mail_template_work_permit_expiry_hr', raise_if_not_found=False)
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)

        for company in companies:
            c_notice_days = getattr(company, 'contract_expiration_notice_period', 0) or 0
            p_notice_days = getattr(company, 'work_permit_expiration_notice_period', 0) or 0
            c_enabled = getattr(company, 'enable_contract_expiry_notification', True)
            p_enabled = getattr(company, 'enable_work_permit_expiry_notification', True)

            employees = self.search([
                ('company_id', '=', company.id),
                ('active', '=', True),
            ])

            # -----------------------------------------------------------------
            # 1. CONTRACT EXPIRATION CHECK
            # -----------------------------------------------------------------
            if c_enabled and c_notice_days > 0:
                for emp in employees:
                    try:
                        c_end = emp._get_contract_expiration_date()
                        if not c_end or c_end < today:
                            continue

                        days_left = (c_end - today).days
                        if 0 <= days_left <= c_notice_days:
                            if emp.last_contract_expiry_notified_date != c_end:
                                emp._notify_contract_expiry(
                                    c_end=c_end,
                                    days_left=days_left,
                                    company=company,
                                    tmpl_emp=tmpl_contract_emp,
                                    tmpl_hr=tmpl_contract_hr,
                                    activity_type=activity_type
                                )
                                emp.write({'last_contract_expiry_notified_date': c_end})
                                contract_notified_count += 1
                    except Exception as e:
                        _logger.exception("Error processing contract expiry notification for employee %s (ID %s): %s", emp.name, emp.id, e)

            # -----------------------------------------------------------------
            # 2. WORK PERMIT EXPIRATION CHECK
            # -----------------------------------------------------------------
            if p_enabled and p_notice_days > 0:
                for emp in employees:
                    try:
                        p_end = emp._get_work_permit_expiration_date()
                        if not p_end or p_end < today:
                            continue

                        days_left = (p_end - today).days
                        if 0 <= days_left <= p_notice_days:
                            if emp.last_work_permit_expiry_notified_date != p_end:
                                emp._notify_work_permit_expiry(
                                    p_end=p_end,
                                    days_left=days_left,
                                    company=company,
                                    tmpl_emp=tmpl_permit_emp,
                                    tmpl_hr=tmpl_permit_hr,
                                    activity_type=activity_type
                                )
                                emp.write({'last_work_permit_expiry_notified_date': p_end})
                                permit_notified_count += 1
                    except Exception as e:
                        _logger.exception("Error processing work permit expiry notification for employee %s (ID %s): %s", emp.name, emp.id, e)

        _logger.info(
            "Expiry notification check completed: %s contract notifications, %s work permit notifications sent.",
            contract_notified_count, permit_notified_count
        )
        return {
            'contract_notified_count': contract_notified_count,
            'permit_notified_count': permit_notified_count,
        }

    def _notify_contract_expiry(self, c_end, days_left, company, tmpl_emp, tmpl_hr, activity_type):
        """Dispatches employee email, HR in-app activity, chatter message, and HR email for contract expiry."""
        self.ensure_one()
        hr_users, hr_partners, hr_emails = self._get_hr_notification_recipients(company)

        # 1. Email to Employee
        emp_email = self._get_employee_notification_email()
        if tmpl_emp and emp_email:
            try:
                tmpl_emp.send_mail(
                    self.id,
                    force_send=True,
                    email_values={'email_to': emp_email}
                )
                _logger.info("Contract expiry email sent to employee %s (%s)", self.name, emp_email)
            except Exception as e:
                _logger.warning("Failed sending contract expiry email to employee %s: %s", self.name, e)
        else:
            _logger.warning("Contract expiry email skipped for %s: missing email address or template.", self.name)

        # 2. In-App Activity for HR Responsible
        hr_assignee = self.hr_responsible_id or (hr_users[0] if hr_users else self.env.user)
        summary = _("Contract Expiring Soon: %s (%s days remaining)", self.name, days_left)
        note = _(
            "<p>The employment contract for <strong>%s</strong> expires on <strong>%s</strong> (%s days remaining).</p>"
            "<p>Please review and initiate contract extension, revision, or exit proceedings.</p>",
            self.name, c_end, days_left
        )

        existing_act = self.activity_ids.filtered(
            lambda a: a.activity_type_id == activity_type and a.summary and 'Contract Expiring Soon' in a.summary
        )
        if not existing_act and activity_type:
            try:
                self.activity_schedule(
                    activity_type_id=activity_type.id,
                    date_deadline=c_end,
                    summary=summary,
                    note=note,
                    user_id=hr_assignee.id
                )
                _logger.info("Contract expiry activity scheduled for HR user %s on employee %s", hr_assignee.name, self.name)
            except Exception as e:
                _logger.warning("Failed scheduling contract expiry activity for %s: %s", self.name, e)

        # 3. In-App Chatter Message for HR & Manager (lands in Discuss inbox)
        msg_body = _(
            "<div style='border-left: 3px solid #ea580c; padding-left: 8px;'>"
            "<strong>Upcoming Contract Expiry Notice:</strong><br/>"
            "Employee: <strong>%s</strong><br/>"
            "Contract End Date: <strong style='color: #ea580c;'>%s</strong> (%s days left)<br/>"
            "Automated notification sent to employee and HR team."
            "</div>",
            self.name, c_end, days_left
        )
        try:
            self.message_post(
                body=msg_body,
                subject=_("Contract Expiry Notice: %s", self.name),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                partner_ids=hr_partners.ids if hr_partners else False,
            )
        except Exception as e:
            _logger.warning("Failed posting contract expiry chatter message for %s: %s", self.name, e)

        # 4. Email to HR Team
        if tmpl_hr and hr_emails:
            try:
                tmpl_hr.send_mail(
                    self.id,
                    force_send=True,
                    email_values={'email_to': ', '.join(hr_emails)}
                )
                _logger.info("Contract expiry alert email sent to HR users: %s", hr_emails)
            except Exception as e:
                _logger.warning("Failed sending contract expiry HR alert email for %s: %s", self.name, e)

    def _notify_work_permit_expiry(self, p_end, days_left, company, tmpl_emp, tmpl_hr, activity_type):
        """Dispatches employee email, HR in-app activity, chatter message, and HR email for work permit expiry."""
        self.ensure_one()
        hr_users, hr_partners, hr_emails = self._get_hr_notification_recipients(company)

        # 1. Email to Employee
        emp_email = self._get_employee_notification_email()
        if tmpl_emp and emp_email:
            try:
                tmpl_emp.send_mail(
                    self.id,
                    force_send=True,
                    email_values={'email_to': emp_email}
                )
                _logger.info("Work permit expiry email sent to employee %s (%s)", self.name, emp_email)
            except Exception as e:
                _logger.warning("Failed sending work permit expiry email to employee %s: %s", self.name, e)
        else:
            _logger.warning("Work permit expiry email skipped for %s: missing email address or template.", self.name)

        # 2. In-App Activity for HR Responsible
        hr_assignee = self.hr_responsible_id or (hr_users[0] if hr_users else self.env.user)
        summary = _("Work Permit Expiring Soon: %s (%s days remaining)", self.name, days_left)
        note = _(
            "<p>The work permit / visa for <strong>%s</strong> expires on <strong>%s</strong> (%s days remaining).</p>"
            "<p>Please ensure required renewal documents are requested and submitted.</p>",
            self.name, p_end, days_left
        )

        existing_act = self.activity_ids.filtered(
            lambda a: a.activity_type_id == activity_type and a.summary and 'Work Permit Expiring Soon' in a.summary
        )
        if not existing_act and activity_type:
            try:
                self.activity_schedule(
                    activity_type_id=activity_type.id,
                    date_deadline=p_end,
                    summary=summary,
                    note=note,
                    user_id=hr_assignee.id
                )
                _logger.info("Work permit expiry activity scheduled for HR user %s on employee %s", hr_assignee.name, self.name)
            except Exception as e:
                _logger.warning("Failed scheduling work permit expiry activity for %s: %s", self.name, e)

        # 3. In-App Chatter Message for HR & Manager
        msg_body = _(
            "<div style='border-left: 3px solid #7c3aed; padding-left: 8px;'>"
            "<strong>Upcoming Work Permit Expiry Notice:</strong><br/>"
            "Employee: <strong>%s</strong><br/>"
            "Work Permit Expiry Date: <strong style='color: #7c3aed;'>%s</strong> (%s days left)<br/>"
            "Automated notification sent to employee and HR compliance team."
            "</div>",
            self.name, p_end, days_left
        )
        try:
            self.message_post(
                body=msg_body,
                subject=_("Work Permit Expiry Notice: %s", self.name),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                partner_ids=hr_partners.ids if hr_partners else False,
            )
        except Exception as e:
            _logger.warning("Failed posting work permit expiry chatter message for %s: %s", self.name, e)

        # 4. Email to HR Team
        if tmpl_hr and hr_emails:
            try:
                tmpl_hr.send_mail(
                    self.id,
                    force_send=True,
                    email_values={'email_to': ', '.join(hr_emails)}
                )
                _logger.info("Work permit expiry alert email sent to HR users: %s", hr_emails)
            except Exception as e:
                _logger.warning("Failed sending work permit expiry HR alert email for %s: %s", self.name, e)
