# -*- coding: utf-8 -*-
{
    'name': 'Hudson Accounting Bundle',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Master Accounting & Payroll Bridge Bundle for Hudson',
    'description': """
Hudson Accounting Bundle
========================
Complete Accounting and Payroll Integration Suite:
- Full Accounting Dashboard & Financial Reports
- Assets & Budget Management
- Recurring Payments & Follow-ups
- Seamless Integration with Hudson Payroll Base
    """,
    'author': 'Hudson Softwares',
    'website': 'https://www.hudsonsoftwares.com',
    'license': 'LGPL-3',
    'depends': [
        'om_account_accountant',
        'hudson_payroll_account',
    ],
    'data': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
