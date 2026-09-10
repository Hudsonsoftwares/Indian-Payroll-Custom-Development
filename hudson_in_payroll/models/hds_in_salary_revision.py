# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HdsInSalaryRevision(models.Model):
    """
    Immutable Salary Revision History Model.
    Maintains complete historical audit records of employee salary revisions,
    statutory recalculations, and contract adjustments.
    """
    _name = 'hds.in.salary.revision'
    _description = 'Hudson Indian Payroll Salary Revision'
    _order = 'effective_date desc, id desc'

    name = fields.Char(
        string="Revision Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        readonly=True,
        ondelete='restrict'
    )
    contract_id = fields.Many2one(
        'hr.version',
        string="Active Contract",
        required=True,
        readonly=True,
        ondelete='restrict'
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        related='employee_id.company_id',
        store=True,
        readonly=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='company_id.currency_id',
        readonly=True
    )
    effective_date = fields.Date(
        string="Effective Date",
        required=True,
        readonly=True
    )
    revision_type = fields.Selection([
        ('annual_increment', 'Annual Increment'),
        ('promotion', 'Promotion'),
        ('correction', 'Salary Correction'),
        ('manual', 'Manual Salary Revision'),
    ], string="Revision Type", required=True, readonly=True)

    revision_basis = fields.Selection([
        ('full_wage', 'Full Wage'),
        ('capped_wage', 'Capped Wage'),
    ], string="Applies On", required=True, readonly=True)

    capped_wage_amount = fields.Monetary(
        string="Capped Wage Amount",
        currency_field='currency_id',
        readonly=True
    )
    computation_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
    ], string="Increase Type", required=True, readonly=True)

    increase_percentage = fields.Float(
        string="Increase Percentage (%)",
        readonly=True
    )
    increase_amount = fields.Float(
        string="Increase Amount (₹)",
        readonly=True
    )

    # Salary Comparison
    old_wage = fields.Monetary(
        string="Old Gross Salary",
        currency_field='currency_id',
        readonly=True
    )
    new_wage = fields.Monetary(
        string="Revised Gross Salary",
        currency_field='currency_id',
        readonly=True
    )
    wage_difference = fields.Monetary(
        string="Gross Salary Difference",
        currency_field='currency_id',
        readonly=True
    )

    # Employer Cost (CTC)
    old_employer_cost_monthly = fields.Monetary(
        string="Old Employer Cost (Monthly)",
        currency_field='currency_id',
        readonly=True
    )
    new_employer_cost_monthly = fields.Monetary(
        string="Revised Employer Cost (Monthly)",
        currency_field='currency_id',
        readonly=True
    )

    # Statutory EPF Breakdown
    old_epf_wage = fields.Monetary(string="Old EPF Wage", currency_field='currency_id', readonly=True)
    new_epf_wage = fields.Monetary(string="Revised EPF Wage", currency_field='currency_id', readonly=True)
    old_employee_epf = fields.Monetary(string="Old Employee EPF", currency_field='currency_id', readonly=True)
    new_employee_epf = fields.Monetary(string="Revised Employee EPF", currency_field='currency_id', readonly=True)
    old_employer_pf = fields.Monetary(string="Old Employer PF", currency_field='currency_id', readonly=True)
    new_employer_pf = fields.Monetary(string="Revised Employer PF", currency_field='currency_id', readonly=True)

    # Statutory ESIC Breakdown
    old_esic_applicable = fields.Boolean(string="Old ESIC Applicable", readonly=True)
    new_esic_applicable = fields.Boolean(string="Revised ESIC Applicable", readonly=True)
    old_employee_esic = fields.Monetary(string="Old Employee ESIC", currency_field='currency_id', readonly=True)
    new_employee_esic = fields.Monetary(string="Revised Employee ESIC", currency_field='currency_id', readonly=True)
    old_employer_esic = fields.Monetary(string="Old Employer ESIC", currency_field='currency_id', readonly=True)
    new_employer_esic = fields.Monetary(string="Revised Employer ESIC", currency_field='currency_id', readonly=True)

    # Professional Tax & LWF
    old_pt_amount = fields.Monetary(string="Old PT Amount", currency_field='currency_id', readonly=True)
    new_pt_amount = fields.Monetary(string="Revised PT Amount", currency_field='currency_id', readonly=True)
    old_lwf_amount = fields.Monetary(string="Old LWF Amount", currency_field='currency_id', readonly=True)
    new_lwf_amount = fields.Monetary(string="Revised LWF Amount", currency_field='currency_id', readonly=True)

    # ESIC Contribution Period Status (Computed for History View)
    esic_cur_period_label = fields.Char(string="Current ESIC Period Label", compute='_compute_esic_period_status')
    esic_cur_period_status = fields.Boolean(string="Current ESIC Period Status", compute='_compute_esic_period_status')
    esic_next_period_label = fields.Char(string="Next ESIC Period Label", compute='_compute_esic_period_status')
    esic_next_period_status = fields.Boolean(string="Next ESIC Period Status", compute='_compute_esic_period_status')
    esic_next_period_reason = fields.Text(string="Next ESIC Period Reason", compute='_compute_esic_period_status')

    @api.depends('employee_id', 'effective_date', 'new_wage', 'company_id', 'old_esic_applicable', 'new_esic_applicable')
    def _compute_esic_period_status(self):
        import datetime
        from ..services.esic.contribution_period_service import ESICContributionPeriodService
        period_service = ESICContributionPeriodService(self.env)
        for rec in self:
            if not rec.employee_id or not rec.effective_date:
                rec.esic_cur_period_label = False
                rec.esic_cur_period_status = False
                rec.esic_next_period_label = False
                rec.esic_next_period_status = False
                rec.esic_next_period_reason = False
                continue

            company = rec.company_id or self.env.company
            employee = rec.employee_id
            is_covered = period_service.is_covered_for_contribution_period(employee, eval_date=rec.effective_date)
            cur_app = bool(company.hds_in_esic_applicable and employee.hds_in_esic_applicable and is_covered)

            cur_start, cur_end = period_service.get_contribution_period_bounds(rec.effective_date)
            rec.esic_cur_period_label = f"({cur_start.strftime('%b %Y')} – {cur_end.strftime('%b %Y')})"
            rec.esic_cur_period_status = cur_app

            next_ref = cur_end + datetime.timedelta(days=1)
            next_start, next_end = period_service.get_contribution_period_bounds(next_ref)
            rec.esic_next_period_label = f"({next_start.strftime('%b %Y')} – {next_end.strftime('%b %Y')})"

            esic_ceiling = period_service.get_parameter('hds_in_esic_pwd_wage_ceiling', date=next_start) if getattr(employee, 'hds_in_is_pwd', False) else period_service.get_parameter('hds_in_esic_wage_ceiling', date=next_start)
            next_app = bool(company.hds_in_esic_applicable and employee.hds_in_esic_applicable and (rec.new_wage <= esic_ceiling if esic_ceiling else True))
            rec.esic_next_period_status = next_app

            if not next_app and company.hds_in_esic_applicable and employee.hds_in_esic_applicable:
                rec.esic_next_period_reason = f"Employee's wage at the start of the next contribution period ({next_start.strftime('%d-%b-%Y')}) exceeds the ESIC wage ceiling (₹{esic_ceiling:,.0f})."
            else:
                rec.esic_next_period_reason = ""

    reason = fields.Text(string="Reason for Revision", readonly=True)
    notes = fields.Text(string="Notes", readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='approved', readonly=True)

    created_by_id = fields.Many2one('res.users', string="Created By", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hds.in.salary.revision') or _('New')
        return super().create(vals_list)
