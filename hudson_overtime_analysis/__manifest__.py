# -*- coding: utf-8 -*-
{
    'name': 'Hudson Overtime Analysis',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Analyze employee overtime and undertime with attendance and leaves integration',
    'description': """
        This module provides overtime and undertime analysis by integrating:
        - hr_attendance (check-in/check-out)
        - hr_holidays (approved time off)
    """,
    'author': 'Hudson Softwares',
    'depends': [
        'hr_attendance',
        'hr_holidays',
        'hr_payroll_community',
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
