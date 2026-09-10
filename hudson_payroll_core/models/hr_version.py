# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    structure_type_id = fields.Many2one(
        'hr.payroll.structure.type',
        string='Salary Structure Type',
        help="Salary Structure Type defining default pay frequency, structure, and working hours."
    )

    company_country_code = fields.Char(
        string="Company Country Code",
        related='company_id.country_id.code',
        readonly=True,
        store=True,
    )
    country_code = fields.Char(
        string="Country Code",
        compute='_compute_country_code',
        store=True,
        readonly=True,
        help="Applicable country code for payroll localization, derived from structure type or company."
    )
    is_india_localization = fields.Boolean(
        string="Is India Localization",
        compute='_compute_country_code',
        store=True,
        help="Flag indicating whether Indian payroll localization is applicable."
    )
    is_uae_localization = fields.Boolean(
        string="Is UAE Localization",
        compute='_compute_country_code',
        store=True,
        help="Flag indicating whether UAE payroll localization is applicable."
    )

    @api.depends('company_id', 'company_id.country_id', 'company_id.country_id.code',
                 'structure_type_id', 'structure_type_id.country_id', 'structure_type_id.country_id.code')
    def _compute_country_code(self):
        for rec in self:
            company = rec.company_id or self.env.company
            code = (
                rec.structure_type_id.country_id.code
                if rec.structure_type_id and rec.structure_type_id.country_id
                else (company.country_id.code if company and company.country_id else '')
            )
            code = (code or '').upper()
            rec.country_code = code
            rec.is_india_localization = (code == 'IN')
            rec.is_uae_localization = (code in ('AE', 'ARE'))

    def _is_india_localization(self):
        self.ensure_one()
        return bool(self.is_india_localization)

    def _is_uae_localization(self):
        self.ensure_one()
        return bool(self.is_uae_localization)

    @api.onchange('structure_type_id')
    def _onchange_structure_type_id(self):
        """Default struct_id and scheduled pay when structure_type_id is selected."""
        if self.structure_type_id:
            if self.structure_type_id.default_struct_id:
                self.struct_id = self.structure_type_id.default_struct_id
            if self.structure_type_id.schedule_pay:
                self.schedule_pay = self.structure_type_id.schedule_pay
            if self.structure_type_id.default_resource_calendar_id:
                self.resource_calendar_id = self.structure_type_id.default_resource_calendar_id
