# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# Each entry: (alias_xml_id, target_module, target_xml_id, target_model)
# alias_xml_id is what hudson_in_payroll's XML files already reference as
# 'hr_payroll_community.<alias_xml_id>'.
ALIASES = [
    # --- Salary rule categories ---
    ('DED',   'hudson_payroll_base', 'rule_category_ded',   'hr.salary.rule.category'),
    ('COMP',  'hudson_payroll_base', 'rule_category_comp',  'hr.salary.rule.category'),
    ('ALW',   'hudson_payroll_base', 'rule_category_alw',   'hr.salary.rule.category'),
    ('GROSS', 'hudson_payroll_base', 'rule_category_gross', 'hr.salary.rule.category'),
    ('NET',   'hudson_payroll_base', 'rule_category_net',   'hr.salary.rule.category'),

    # --- Base salary rules that already exist in hudson_payroll_base ---
    ('hr_rule_basic',   'hudson_payroll_base', 'hr_rule_basic',   'hr.salary.rule'),
    ('hr_rule_taxable', 'hudson_payroll_base', 'hr_rule_taxable', 'hr.salary.rule'),
    ('hr_rule_net',     'hudson_payroll_base', 'hr_rule_net',     'hr.salary.rule'),

    # NOTE: hr_rule_hra / hr_rule_da are NOT aliased here - HRA/DA are
    # India-specific salary components, not universal ones. They belong
    # in hudson_in_payroll's own data (see its
    # data/hr_salary_rule_hra_da_india.xml), referenced there directly
    # by their own local xml_id - not routed through this bridge.

    # --- Default structure ---
    ('structure_base', 'hudson_payroll_base', 'structure_base', 'hr.payroll.structure'),

    # --- Security groups ---
    ('group_hr_payroll_community_user',    'hudson_payroll_base', 'group_payroll_user',    'res.groups'),
    ('group_hr_payroll_community_manager', 'hudson_payroll_base', 'group_payroll_manager', 'res.groups'),

    # --- Menus ---
    ('menu_hr_payroll_community_root',          'hudson_payroll_base', 'menu_hr_payroll_root',          'ir.ui.menu'),
    ('menu_hr_payroll_community_configuration', 'hudson_payroll_base', 'menu_hr_payroll_configuration', 'ir.ui.menu'),

    # --- Core Odoo views Cybrosys itself ultimately inherits from ---
    ('res_config_settings_view_form', 'hudson_payroll_base', 'res_config_settings_view_form', 'ir.ui.view'),
    ('view_employee_form',            'hr',   'view_employee_form',            'ir.ui.view'),
]

# model_hr_payslip is handled separately since its target is an ir.model
# record (not found via a normal xml_id ref - looked up by model name).
MODEL_ALIASES = [
    ('model_hr_payslip', 'hr.payslip'),
]


def post_init_create_bridge_aliases(env):
    """Create ir.model.data rows under module='hr_payroll_community' so
    every ref('hr_payroll_community.<id>') used by hudson_in_payroll
    resolves to the equivalent record in hudson_payroll_base (or this
    bridge module), without editing hudson_in_payroll's own XML files."""
    IMD = env['ir.model.data']
    created, skipped, missing = 0, 0, []

    for alias_name, target_module, target_xmlid, target_model in ALIASES:
        full_target_id = "%s.%s" % (target_module, target_xmlid)
        target_record = env.ref(full_target_id, raise_if_not_found=False)
        if not target_record:
            missing.append(full_target_id)
            continue

        existing = IMD.search([
            ('module', '=', 'hr_payroll_community'),
            ('name', '=', alias_name),
        ], limit=1)
        if existing:
            if existing.res_id != target_record.id or existing.model != target_model:
                existing.write({'res_id': target_record.id, 'model': target_model})
            skipped += 1
            continue

        IMD.create({
            'module': 'hr_payroll_community',
            'name': alias_name,
            'model': target_model,
            'res_id': target_record.id,
            'noupdate': True,
        })
        created += 1

    for alias_name, model_name in MODEL_ALIASES:
        ir_model = env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        if not ir_model:
            missing.append("ir.model for %s" % model_name)
            continue
        existing = IMD.search([
            ('module', '=', 'hr_payroll_community'),
            ('name', '=', alias_name),
        ], limit=1)
        if existing:
            skipped += 1
            continue
        IMD.create({
            'module': 'hr_payroll_community',
            'name': alias_name,
            'model': 'ir.model',
            'res_id': ir_model.id,
            'noupdate': True,
        })
        created += 1

    _logger.info(
        "hudson_payroll_community_bridge: created %s aliases, skipped %s existing.",
        created, skipped
    )
    if missing:
        _logger.warning(
            "hudson_payroll_community_bridge: could NOT create aliases for "
            "missing targets: %s. Check these exist in hudson_payroll_base "
            "before installing hudson_in_payroll.", missing
        )
