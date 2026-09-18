# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo import fields, models


class HdsPaymentMode(models.Model):
    """
    Configurable Payment Mode master for Indian Payroll.
    HR Admins can create, edit, or deactivate payment modes from
    Payroll Settings → Configure Payment Modes.
    The selected mode is stored on the Employee and auto-populated on Payslips.
    """
    _name = 'hds.payment.mode'
    _description = 'Payroll Payment Mode'
    _order = 'sequence, name'

    name = fields.Char(
        string="Payment Mode",
        required=True,
        translate=False,
        help="Display label for this payment mode (e.g. 'NEFT / RTGS', 'Cash')."
    )
    code = fields.Char(
        string="Code",
        required=True,
        help="Short internal code (e.g. 'neft_rtgs', 'cash'). Used for logic branching."
    )
    is_cash = fields.Boolean(
        string="Is Cash Mode",
        default=False,
        help="If checked, bank account / account number fields will be hidden on the payslip "
             "since cash payment does not involve bank details."
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Display ordering in dropdown lists."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this payment mode without deleting it."
    )
    notes = fields.Text(
        string="Notes",
        help="Optional internal notes about this payment mode."
    )
