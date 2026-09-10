# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayrollStructure(models.Model):
    """Salary Structure containing the set of rules applied during payslip computation."""
    _name = 'hr.payroll.structure'
    _description = 'Salary Structure'

    name = fields.Char(string='Structure Name', required=True, translate=True)
    code = fields.Char(string='Reference', required=True, index=True)
    type_id = fields.Many2one(
        'hr.payroll.structure.type',
        string='Type'
    )
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.company.country_id,
        compute='_compute_country_id',
        store=True,
        readonly=False,
        help="Country of applicability, defaults to the company's country."
    )
    use_worked_day_lines = fields.Boolean(
        string='Use Worked Day Lines',
        default=True,
        help="Work entries will be used to generate worked days."
    )
    ytd_computation = fields.Boolean(
        string='Year to Date Computation',
        default=False,
        help="Compute Year-to-Date totals on payslips."
    )
    report_id = fields.Many2one(
        'ir.actions.report',
        string='Template',
        domain="[('model', '=', 'hr.payslip')]",
        default=lambda self: self.env.ref('hudson_payroll_base.action_report_payslip', raise_if_not_found=False)
    )
    payslip_name = fields.Char(
        string='Payslip Name',
        help="Name given to payslips generated with this structure."
    )
    hide_basic_on_pdf = fields.Boolean(
        string='Hide Basic On Pdf',
        default=False,
        help="Hide basic salary component from the payslip PDF report."
    )
    schedule_pay = fields.Selection([
        ('monthly', 'month'),
        ('quarterly', 'quarter'),
        ('semi-annually', 'half-year'),
        ('annually', 'year'),
        ('weekly', 'week'),
        ('bi-weekly', 'bi-week'),
        ('bi-monthly', 'bi-month'),
    ], string='Scheduled Pay', default='monthly', compute='_compute_schedule_pay', store=True, readonly=False,
       help="Defines the frequency of the wage payment.")

    unpaid_work_entry_type_ids = fields.Many2many(
        'hr.work.entry.type',
        'hr_payroll_structure_unpaid_work_entry_type_rel',
        'struct_id',
        'work_entry_type_id',
        string='Unpaid Work Entry Types',
        help="Work entry types considered as unpaid time off."
    )
    input_line_type_ids = fields.Many2many(
        'hr.payslip.input.type',
        'hr_payslip_input_type_structure_rel',
        'struct_id',
        'input_type_id',
        string='Other Input',
        help="Input types available on payslips using this structure."
    )

    @api.depends('type_id.schedule_pay')
    def _compute_schedule_pay(self):
        for rec in self:
            if rec.type_id and rec.type_id.schedule_pay:
                rec.schedule_pay = rec.type_id.schedule_pay
            elif not rec.schedule_pay:
                rec.schedule_pay = 'monthly'

    @api.depends('company_id.country_id', 'type_id.country_id')
    def _compute_country_id(self):
        for rec in self:
            if rec.company_id and rec.company_id.country_id:
                rec.country_id = rec.company_id.country_id
            elif rec.type_id and rec.type_id.country_id:
                rec.country_id = rec.type_id.country_id
            elif not rec.country_id:
                rec.country_id = self.env.company.country_id

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id and self.company_id.country_id:
            self.country_id = self.company_id.country_id
    parent_id = fields.Many2one(
        'hr.payroll.structure',
        string='Parent Structure',
        index=True
    )
    children_ids = fields.One2many(
        'hr.payroll.structure',
        'parent_id',
        string='Sub Structures'
    )
    rule_ids = fields.One2many(
        'hr.salary.rule',
        'struct_id',
        string='Salary Rules'
    )
    note = fields.Text(string='Description')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('Error! You cannot create recursive salary structures.'))

    def get_all_rules(self):
        """Returns all rules of this structure including parent structure rules.
        If a child structure defines a rule with the same code as a parent structure,
        the child structure's rule overrides the parent's rule.
        Rules are sorted by (sequence, id).
        """
        self.ensure_one()
        rule_by_code = {}
        curr = self
        while curr:
            # Sort current structure rules by sequence
            for rule in curr.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
                # If rule code not yet registered, register it (child has priority)
                if rule.code not in rule_by_code:
                    rule_by_code[rule.code] = rule
            curr = curr.parent_id

        # Return as an hr.salary.rule recordset sorted by sequence
        all_rules = self.env['hr.salary.rule'].browse([r.id for r in rule_by_code.values()])
        return all_rules.sorted(key=lambda r: (r.sequence, r.id))
