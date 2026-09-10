# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrPayrollStructureType(models.Model):
    _name = 'hr.payroll.structure.type'
    _description = 'Salary Structure Type'
    _order = 'sequence, name'

    name = fields.Char(string='Structure Type', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.company.country_id,
        help="Country for which this structure type is applicable."
    )
    wage_type = fields.Selection([
        ('monthly', 'Fixed Wage'),
        ('hourly', 'Hourly Wage'),
    ], string='Wage Type', default='monthly', required=True)

    schedule_pay = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi-annually', 'Semi-annually'),
        ('annually', 'Annually'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-weekly'),
        ('bi-monthly', 'Bi-monthly'),
    ], string='Scheduled Pay', default='monthly', required=True,
        help="Defines the frequency of wage payment.")

    default_resource_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Working Hours',
        default=lambda self: self.env.company.resource_calendar_id,
        help="Default working hours schedule for contracts using this structure type."
    )

    default_struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Pay Structure',
        help="Default regular pay structure applied to contracts of this structure type."
    )

    time_type = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
    ], string='Time Type', default='full_time',
        help="Employment engagement time type.")

    struct_ids = fields.One2many(
        'hr.payroll.structure',
        'type_id',
        string='Related Structures',
        help="All salary structures belonging to this structure type."
    )
    struct_count = fields.Integer(
        string='Structures Count',
        compute='_compute_struct_count'
    )

    @api.depends('struct_ids')
    def _compute_struct_count(self):
        for rec in self:
            rec.struct_count = len(rec.struct_ids)

    def action_view_structures(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('hr_payroll_community.hr_payroll_structure_action')
        action['domain'] = [('id', 'in', self.struct_ids.ids)]
        action['context'] = {'default_type_id': self.id}
        return action
