from odoo import api, fields, models, _


class ResCompany(models.Model):
    """Extend company to store default payroll configuration settings."""
    _inherit = 'res.company'

    ytd_reset_date = fields.Selection([
        ('01-01', '1st of January (Calendar Year)'),
        ('04-01', '1st of April (Fiscal Year)'),
        ('07-01', '1st of July'),
        ('10-01', '1st of October'),
    ], string='YTD Reset Date', default='01-01',
       help="Date when Year-To-Date (YTD) accumulator totals reset to zero.")

    send_payslips = fields.Selection([
        ('draft', 'When Draft'),
        ('confirmed', 'When Confirmed'),
        ('paid', 'When Paid'),
        ('manual', 'Manual Only'),
    ], string='Send Payslips to Employees', default='confirmed',
       help="Define when payslips are printed and sent to employees.")

    deferred_time_off = fields.Boolean(
        string='Deferred Time Off',
        default=False,
        help="Postpone time off after payslip validation."
    )
    deferred_time_off_responsible_id = fields.Many2one(
        'res.users',
        string='Deferred Time Off Responsible',
        help="Responsible user for managing deferred time off."
    )
    payrun_accounting = fields.Boolean(
        string='Batch Accounting Entries',
        default=False,
        help="Create consolidated journal entries upon pay run confirmation."
    )
    enable_contract_expiry_notification = fields.Boolean(
        string='Enable Contract Expiry Notification',
        default=True,
        help="Send automated email and in-app notifications when contracts are nearing expiration."
    )
    enable_work_permit_expiry_notification = fields.Boolean(
        string='Enable Work Permit Expiry Notification',
        default=True,
        help="Send automated email and in-app notifications when work permits are nearing expiration."
    )
    expiry_notification_user_ids = fields.Many2many(
        'res.users',
        'company_expiry_notification_user_rel',
        'company_id',
        'user_id',
        string='Expiry Notification HR Recipients',
        help="Specific HR / Management users who should receive in-app and email notifications when contracts or work permits are expiring. If empty, defaults to employee's HR Responsible and Payroll Managers."
    )

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            if company.country_id:
                structures = self.env['hr.payroll.structure'].search([
                    ('company_id', '=', company.id),
                    ('country_id', '=', False)
                ])
                if structures:
                    structures.write({'country_id': company.country_id.id})
        return companies

    def write(self, vals):
        res = super().write(vals)
        if 'country_id' in vals and vals['country_id']:
            for company in self:
                structures = self.env['hr.payroll.structure'].search([
                    ('company_id', '=', company.id)
                ])
                if structures:
                    structures.write({'country_id': vals['country_id']})
        return res


class ResConfigSettings(models.TransientModel):
    """Payroll Configuration Settings."""
    _inherit = 'res.config.settings'

    # Notice period fields are inherited from res.company via base hr module:
    # contract_expiration_notice_period
    # work_permit_expiration_notice_period

    enable_contract_expiry_notification = fields.Boolean(
        related='company_id.enable_contract_expiry_notification',
        readonly=False,
        string='Enable Contract Expiry Notification'
    )
    enable_work_permit_expiry_notification = fields.Boolean(
        related='company_id.enable_work_permit_expiry_notification',
        readonly=False,
        string='Enable Work Permit Expiry Notification'
    )
    expiry_notification_user_ids = fields.Many2many(
        related='company_id.expiry_notification_user_ids',
        readonly=False,
        string='HR Notification Recipients'
    )

    ytd_reset_date = fields.Selection(
        related='company_id.ytd_reset_date',
        readonly=False,
        string='YTD Reset Date'
    )
    send_payslips = fields.Selection(
        related='company_id.send_payslips',
        readonly=False,
        string='Send Payslips to Employees'
    )
    deferred_time_off = fields.Boolean(
        related='company_id.deferred_time_off',
        readonly=False,
        string='Deferred Time Off'
    )
    deferred_time_off_responsible_id = fields.Many2one(
        'res.users',
        related='company_id.deferred_time_off_responsible_id',
        readonly=False,
        string='Responsible'
    )
    payrun_accounting = fields.Boolean(
        related='company_id.payrun_accounting',
        readonly=False,
        string='Batch Journal Entries'
    )
    module_account = fields.Boolean(
        string='Payroll Accounting',
        help='Post payroll slips and salary journal entries in accounting.'
    )
    module_hr_attendance = fields.Boolean(
        string='Biometric / Attendance Integration',
        help='Integrate attendance records and worked days with payslip computation.'
    )

    def action_check_and_notify_expirations(self):
        """Action button to trigger expiry check on demand from Settings UI."""
        counts = self.env['hr.employee'].notify_expiring_contract_work_permit()
        c_count = counts.get('contract_notified_count', 0)
        p_count = counts.get('permit_notified_count', 0)
        total = c_count + p_count
        msg = _(
            "Expiry Check Completed: %s contract notification(s) and %s work permit notification(s) processed.",
            c_count, p_count
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Automated Expiry Notifications"),
                'message': msg,
                'type': 'success' if total > 0 else 'info',
                'sticky': False,
            }
        }

