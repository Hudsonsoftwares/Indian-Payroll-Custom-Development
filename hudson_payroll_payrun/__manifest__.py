# -*- coding: utf-8 -*-
{
    'name': 'Hudson Payroll - Department-Aware Pay Run & Payment Advice',
    'version': '19.0.1.0.2',
    'category': 'Human Resources/Payroll',
    'summary': 'Kanban board, guided Pay Run wizard, department & employee-type scoping, and bank Payment Advice with CSV/PDF export',
    'author': 'Hudson Softwares',
    'website': 'https://www.hudsonsoftwares.com',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_payroll_community',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_employee_type_data.xml',
        'reports/payment_advice_report.xml',
        'data/mail_template_data.xml',
        'views/payroll_operations_menu.xml',
        'views/hr_employee_type_views.xml',
        'views/payrun_wizard_views.xml',
        'views/payment_advice_views.xml',
        'views/hr_payslip_run_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
