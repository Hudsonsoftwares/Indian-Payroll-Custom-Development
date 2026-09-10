# -*- coding: utf-8 -*-
#############################################################################
#    A part of OpenHRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

GENDER_SELECTION = [('male', 'Male'),
                    ('female', 'Female'),
                    ('other', 'Other')]


class HrEmployee(models.Model):
    """Extended model for HR employees with additional features."""
    _inherit = 'hr.employee'

    personal_mobile = fields.Char(string='Mobile', related='private_phone',
                                  help="Personal mobile number of the "
                                       "employee", store=True, )
    joining_date = fields.Date(compute='_compute_joining_date',
                               string='Joining Date', store=True,
                               help="Employee joining date computed from the"
                                    " contract start date")
    id_expiry_date = fields.Date(help='Expiry date of Identification document',
                                 string='Expiry Date',)
    passport_expiry_date = fields.Date(help='Expiry date of Passport ID',
                                       string='Expiry Date')
    identification_attachment_ids = fields.Many2many(
        'ir.attachment', 'id_attachment_rel',
        'id_ref', 'attach_ref', string="Attachment",
        help='Attach the copy of Identification document')
    passport_attachment_ids = fields.Many2many(
        'ir.attachment',
        'passport_attachment_rel',
        'passport_ref', 'attach_ref1', string="Attachment",
        help='Attach the copy of Passport')
    family_info_ids = fields.One2many('hr.employee.family', 'employee_id',
                                      string='Family',
                                      help='Family Information')

    # ---------------------------------------------------------
    # Personal Information & Preferences
    # ---------------------------------------------------------
    show_birthday_to_employees = fields.Boolean(
        string='Show Birthday To Employees',
        default=False,
        help="Controls whether the employee's birthday may be visible to other employees."
    )
    is_disabled = fields.Boolean(
        string='Disabled?',
        default=False,
        help="Generic demographic/administrative indicator if employee is a person with disabilities."
    )
    payslip_lang_id = fields.Many2one(
        'res.lang',
        string='Payslip Language',
        help="Preferred language for payslip display and generation."
    )

    # ---------------------------------------------------------
    # Citizenship
    # ---------------------------------------------------------
    is_non_resident = fields.Boolean(
        string='Non-resident?',
        default=False,
        help="Residency classification indicator for administrative and HR profile purposes."
    )

    # ---------------------------------------------------------
    # Visa & Work Permit
    # ---------------------------------------------------------
    work_permit_expiry_date = fields.Date(
        string='Expires On',
        help="Expiration date of the employee's work permit."
    )

    # ---------------------------------------------------------
    # Family Information
    # ---------------------------------------------------------
    spouse_legal_name = fields.Char(
        string='Spouse Legal Name',
        help="Legal full name of the employee's spouse."
    )
    spouse_birthdate = fields.Date(
        string='Spouse Birthdate',
        help="Date of birth of the employee's spouse."
    )

    # ---------------------------------------------------------
    # Employee Documents
    # ---------------------------------------------------------
    sim_card_copy = fields.Binary(
        string='SIM Card Copy',
        attachment=True,
        help="Attached digital copy of the employee's SIM Card."
    )
    sim_card_copy_filename = fields.Char(string='SIM Card Copy Filename')

    internet_subscription_invoice = fields.Binary(
        string='Internet Subscription Invoice',
        attachment=True,
        help="Attached digital copy of the employee's Internet Subscription Invoice."
    )
    internet_subscription_invoice_filename = fields.Char(string='Internet Subscription Invoice Filename')

    @api.constrains('spouse_birthdate')
    def _check_spouse_birthdate(self):
        today = fields.Date.today()
        for employee in self:
            if employee.spouse_birthdate and employee.spouse_birthdate > today:
                raise ValidationError(_("Spouse Birthdate cannot be in the future."))

    @api.depends('version_id')
    def _compute_joining_date(self):
        """Compute the joining date of the employee based on their contract
         information."""
        for employee in self:
            employee.joining_date = min(
                employee.version_id.mapped('date_start')) \
                if employee.version_id else False

    @api.onchange('spouse_complete_name', 'spouse_birthdate')
    def _onchange_spouse_complete_name(self):
        """Populates the family_info_ids field with the spouse's information,
         creating a family member record associated with the employee when
         spouse's complete name or birthdate changed."""
        relation = self.env.ref('hr_employee_updation.employee_relationship', raise_if_not_found=False)
        if relation and self.spouse_complete_name and self.spouse_birthdate:
            self.family_info_ids = [(0, 0, {
                'member_name': self.spouse_complete_name,
                'relation_id': relation.id,
                'birth_date': self.spouse_birthdate,
            })]

    def expiry_mail_reminder(self):
        """Sending ID and Passport expiry notification."""
        current_date = fields.Date.context_today(self) + timedelta(days=1)
        employee_ids = self.search(['|', ('id_expiry_date', '!=', False),
                                    ('passport_expiry_date', '!=', False)])
        for employee in employee_ids:
            if employee.id_expiry_date:
                exp_date = fields.Date.from_string(
                    employee.id_expiry_date) - timedelta(days=14)
                if current_date >= exp_date:
                    mail_content = ("Hello  " + employee.name + ",<br>Your ID "
                                    + (employee.identification_id or '') +
                                    " is going to expire on " +
                                    str(employee.id_expiry_date)
                                    + ". Please renew it before expiry date")
                    main_content = {
                        'subject': _('ID-%s Expired On %s') % (
                            employee.identification_id,
                            employee.id_expiry_date),
                        'author_id': self.env.user.partner_id.id,
                        'body_html': mail_content,
                        'email_to': employee.work_email,
                    }
                    self.env['mail.mail'].sudo().create(main_content).send()
            if employee.passport_expiry_date:
                exp_date = fields.Date.from_string(
                    employee.passport_expiry_date) - timedelta(days=180)
                if current_date >= exp_date:
                    mail_content = ("  Hello  " + employee.name +
                                    ",<br>Your Passport " + (employee.passport_id or '')
                                    + " is going to expire on " +
                                    str(employee.passport_expiry_date) +
                                    ". Please renew it before expire")
                    main_content = {
                        'subject': _('Passport-%s Expired On %s') % (
                            employee.passport_id,
                            employee.passport_expiry_date),
                        'author_id': self.env.user.partner_id.id,
                        'body_html': mail_content,
                        'email_to': employee.work_email,
                    }
                    self.env['mail.mail'].sudo().create(main_content).send()
