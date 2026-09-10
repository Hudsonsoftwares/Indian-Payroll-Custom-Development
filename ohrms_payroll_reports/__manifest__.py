# -*- coding: utf-8 -*-
{
    'name': 'Odoo 19 Payroll Reporting',
    'version': '19.0.1.0.1',
    'category': 'Human Resources',
    'summary': 'Pivot, Graph, and List views for Payroll Analysis',
    'description': """
This module adds pivot, graph, list, and search views for:
- Payslip Lines (hr.payslip.line)
- Payslip Worked Days (hr.payslip.worked.days)
- Payslip Inputs (hr.payslip.input)
Under a new Reporting menu in the Payroll application.
""",
    'author': 'OpenHRMS / Antigravity',
    'depends': ['hr_payroll_community'],
    'data': [
        'views/hr_payslip_line_views.xml',
        'views/hr_payslip_worked_days_views.xml',
        'views/hr_payslip_input_views.xml',
        'views/payroll_reporting_menu.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
