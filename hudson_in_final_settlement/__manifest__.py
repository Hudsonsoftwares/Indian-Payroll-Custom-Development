# -*- coding: utf-8 -*-
{
    'name': 'Hudson Indian Final Settlement',
    'version': '19.0.1.0.2',
    'category': 'Human Resources/Payroll',
    'summary': 'India Statutory Final Settlement (Gratuity Act 1972, Leave Encashment, Notice Pay) for Hudson HRMS',
    'author': 'Hudson Software Solutions',
    'depends': [
        'hr',
        'hudson_exit_management',
        'hudson_payroll_base',
        'hudson_in_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/final_settlement_sequence.xml',
        'views/final_settlement_views.xml',
        'views/hr_resignation_views.xml',
        'views/payroll_dashboard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
