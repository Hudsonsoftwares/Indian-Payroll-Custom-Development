# -*- coding: utf-8 -*-
{
    'name': 'Hudson Payroll Core',
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Payroll',
    'summary': 'Core Payroll Models, Salary Input Types, and Rule Parameter Framework',
    'author': 'Hudson Software Solutions',
    'depends': [
        'hr',
        'hr_payroll_community',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_payslip_input_type_data.xml',
        'views/hr_payroll_structure_type_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/hr_version_views.xml',
        'views/hr_rule_parameter_views.xml',
        'views/hr_payslip_input_type_views.xml',
        'views/hr_payslip_input_section_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_salary_rule_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
