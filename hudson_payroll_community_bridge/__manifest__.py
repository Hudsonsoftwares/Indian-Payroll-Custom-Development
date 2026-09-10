# -*- coding: utf-8 -*-
{
    'name': 'Hudson Payroll - Community Compatibility Bridge',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Aliases hr_payroll_community.* external IDs onto hudson_payroll_base records',
    'description': """
Hudson Payroll - Community Compatibility Bridge
==================================================
hudson_in_payroll (as currently shipped) references records by their
Cybrosys hr_payroll_community external IDs, e.g.:
    ref('hr_payroll_community.DED')
    ref('hr_payroll_community.structure_base')
    ref('hr_payroll_community.group_hr_payroll_community_manager')

This module does NOT install Cybrosys. Instead, on install, it creates
ir.model.data rows under the module name 'hr_payroll_community' that
point at hudson_payroll_base's OWN equivalent records. Any ref() call
using the old Cybrosys external ID then resolves correctly, without
editing hudson_in_payroll's ~50 reference sites one by one.

*** WHAT THIS BRIDGE COVERS (safe, plain data references) ***
    - Salary rule categories: DED, COMP, ALW, GROSS, NET
    - Base salary rules that hudson_payroll_base already ships:
      hr_rule_basic, hr_rule_taxable, hr_rule_net
    - Default structure: structure_base
    - Security groups: group_hr_payroll_community_user/manager
    - Menus: menu_hr_payroll_community_root/configuration
    - model_hr_payslip (for report action bindings)
    - res_config_settings_view_form / view_employee_form (aliased
      directly to Odoo core's own base.* views, since Cybrosys itself
      ultimately inherits from those)

NOTE ON HRA/DA: hudson_payroll_base does not ship HRA/DA rules (they
are India-specific components, not universal ones like BASIC/GROSS/
NET). They are intentionally NOT created here - they belong in
hudson_in_payroll's own India-specific data, referenced by their own
local xml_id, not routed through this country-agnostic bridge.

*** WHAT THIS BRIDGE DELIBERATELY DOES NOT COVER ***
    - hr_payslip_view_form / hr_payslip_view_tree
    - hr_salary_rule_view_form / hr_salary_rule_view_tree
    - hr_payroll_structure_view_tree / hr_payslip_run_view_tree
    - report_payslip / report_payslipdetails (report templates)

These are view/report XML INHERITS with xpath expressions written
against Cybrosys's exact view layout. Aliasing their ID would make
the reference resolve, but the xpath inside could still fail (or
silently attach in the wrong place) because hudson_payroll_base's own
views have a different structure. These still need a real, reviewed
edit per file - deliberately left unaliased so install fails loudly
and specifically on those files rather than rendering something wrong.
""",
    'author': 'Hudson Software Solutions',
    'license': 'LGPL-3',
    'depends': ['hudson_payroll_base'],
    'data': [],
    'post_init_hook': 'post_init_create_bridge_aliases',
    'installable': True,
    'application': False,
}
