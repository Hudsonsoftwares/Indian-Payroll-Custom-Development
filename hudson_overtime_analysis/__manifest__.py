# -*- coding: utf-8 -*-
{
    'name': 'Hudson Overtime Analysis',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Analyze employee overtime and undertime with attendance, leaves, and Hudson Payroll integration',
    'description': """
        This module provides overtime and undertime analysis by integrating:
        - hr_attendance (check-in/check-out)
        - hr_holidays (approved time off)
        - hudson_payroll_base (Hudson Payroll engine)
    """,
    'author': 'Hudson Softwares',
    'depends': [
        'hr_attendance',
        'hr_holidays',
        'hudson_payroll_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_overtime_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
