# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

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
