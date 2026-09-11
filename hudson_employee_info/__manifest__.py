# -*- coding: utf-8 -*-
{
    'name': 'Hudson Employee Information',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Generic Employee Information Extensions, Preferences, Work Permit & Document Management',
    'description': """
Hudson Employee Information Extension
======================================
Generic employee profile enhancements reusable across all companies and localizations:
- Personal Information: Birthday visibility preference, demographic disability indicator, preferred payslip language.
- Visa & Work Permit: Work permit expiry date.
- Citizenship: Non-resident statutory classification.
- Family Information: Spouse legal name and birthdate validation.
- Employee Documents: Secure attachment storage for SIM Card Copy and Internet Subscription Invoice.
    """,
    'author': 'Hudson Software Solutions',
    'depends': [
        'hr',
        'hudson_payroll_base',
        'account',
    ],
    'data': [
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
