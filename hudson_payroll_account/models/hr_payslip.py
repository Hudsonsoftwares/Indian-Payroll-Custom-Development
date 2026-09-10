# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    date = fields.Date(
        string='Date Account',
        help="Keep empty to use the payslip end date (date_to)."
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Salary Journal',
        required=True,
        default=lambda self: self.env['account.journal'].search(
            [('type', '=', 'general')], limit=1
        ),
        help="Select Salary Journal for accounting entries."
    )
    move_id = fields.Many2one(
        'account.move',
        string='Accounting Entry',
        readonly=True,
        copy=False,
        help="Accounting entry generated for this payslip."
    )

    @api.model_create_multi
    def create(self, vals_list):
        journal_id = self.env.context.get('journal_id')
        if journal_id:
            for vals in vals_list:
                if 'journal_id' not in vals:
                    vals['journal_id'] = journal_id
        return super().create(vals_list)

    def write(self, vals):
        res = super(HrPayslip, self).write(vals)
        # When moving to paid or done status, ensure entry is generated in draft status
        if vals.get('state') == 'paid' or vals.get('paid'):
            for slip in self:
                if not slip.move_id:
                    slip._create_account_move()
        elif vals.get('state') == 'done':
            for slip in self:
                if not slip.move_id:
                    slip._create_account_move()
        return res

    @api.onchange('contract_id')
    def onchange_contract_id(self):
        if hasattr(super(), 'onchange_contract_id'):
            super().onchange_contract_id()
        if self.contract_id and hasattr(self.contract_id, 'journal_id') and self.contract_id.journal_id:
            self.journal_id = self.contract_id.journal_id

    def action_payslip_cancel(self):
        """Cancel the payroll slip and remove or cancel associated accounting entries."""
        for slip in self:
            if slip.move_id:
                move = slip.move_id
                if move.state == 'posted':
                    move.button_draft()
                move.unlink()
        return super(HrPayslip, self).action_payslip_cancel()

    def action_payslip_done(self):
        """Finalize the payslip and create draft journal entry."""
        res = super(HrPayslip, self).action_payslip_done()
        for slip in self:
            slip._create_account_move()
        return res

    def action_payslip_paid(self):
        """Mark payslip as paid and generate draft journal entry."""
        res = super(HrPayslip, self).action_payslip_paid()
        for slip in self:
            if not slip.move_id:
                slip._create_account_move()
        return res

    def action_post_account_move(self):
        """Allows posting the draft accounting entry directly."""
        self.ensure_one()
        if not self.move_id and self.state in ('done', 'paid'):
            self._create_account_move()
        if self.move_id and self.move_id.state == 'draft':
            self.move_id.action_post()
        return True

    def _create_account_move(self):
        """Creates a balanced journal entry (account.move) for the payslip."""
        for slip in self:
            if slip.move_id:
                continue

            if not slip.journal_id:
                slip.journal_id = self.env['account.journal'].search([('type', '=', 'general')], limit=1)

            line_ids = []
            debit_sum = 0.0
            credit_sum = 0.0
            date_entry = slip.date or slip.date_to or fields.Date.today()
            currency = slip.company_id.currency_id or self.env.company.currency_id
            company_id = slip.company_id.id or self.env.company.id

            # Fallback default accounts if rule does not have explicit account configured
            def get_company_account(code=None, account_types=None, name_keyword=None):
                domain = [('company_ids', 'in', [company_id])]
                if code:
                    domain.append(('code', '=', code))
                if account_types:
                    domain.append(('account_type', 'in', account_types))
                if name_keyword:
                    domain.append(('name', 'ilike', name_keyword))
                return self.env['account.account'].search(domain, limit=1)

            def_expense_acc = (
                get_company_account(code='210100')
                or get_company_account(account_types=['expense'], name_keyword='salary')
                or get_company_account(account_types=['expense'])
            )
            def_payable_acc = (
                get_company_account(code='112410')
                or get_company_account(code='300010')
                or get_company_account(account_types=['liability_payable', 'liability_current'], name_keyword='wage')
                or get_company_account(account_types=['liability_payable', 'liability_current'])
            )

            is_refund = bool(slip.credit_note)

            for line in slip.line_ids:
                if currency.is_zero(line.total):
                    continue

                rule = line.salary_rule_id
                cat_code = rule.category_id.code if rule.category_id else ''

                # Subtotals and intermediate calculations should not generate accounting lines
                if cat_code in ('GROSS', 'PF_CALC', 'ESIC_CALC') or rule.code in ('GROSS', 'PF_WAGE', 'ESIC_WAGE'):
                    continue

                abs_amt = currency.round(abs(line.total))
                if currency.is_zero(abs_amt):
                    continue

                debit_account_id = rule.account_debit_id.id
                credit_account_id = rule.account_credit_id.id

                # Intelligent fallback if not explicitly configured on rule
                if not debit_account_id and not credit_account_id:
                    if cat_code in ('BASIC', 'ALW') or (rule.code in ('BASIC', 'HRA', 'DA', 'FIXED', 'OT', 'BONUS')):
                        debit_account_id = def_expense_acc.id if def_expense_acc else False
                    elif cat_code == 'NET' or rule.code == 'NET':
                        credit_account_id = def_payable_acc.id if def_payable_acc else False
                    elif cat_code == 'DED':
                        ded_acc = (
                            get_company_account(name_keyword=rule.name)
                            or get_company_account(name_keyword=rule.code)
                            or def_payable_acc
                        )
                        credit_account_id = ded_acc.id if ded_acc else False

                analytic_acc = rule.analytic_account_id or slip.contract_id.analytic_account_id
                analytic_distribution = {str(analytic_acc.id): 100} if analytic_acc else False

                if debit_account_id:
                    debit_amt = 0.0 if is_refund else abs_amt
                    credit_amt = abs_amt if is_refund else 0.0
                    partner_id = line._get_partner_id(credit_account=False)
                    debit_vals = {
                        'name': f"{slip.employee_id.name} - {line.name}",
                        'partner_id': partner_id,
                        'account_id': debit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date_entry,
                        'debit': debit_amt,
                        'credit': credit_amt,
                    }
                    if analytic_distribution:
                        debit_vals['analytic_distribution'] = analytic_distribution
                    if rule.account_tax_id:
                        debit_vals['tax_ids'] = [(6, 0, [rule.account_tax_id.id])]
                    line_ids.append((0, 0, debit_vals))
                    debit_sum += debit_amt
                    credit_sum += credit_amt

                if credit_account_id:
                    debit_amt = abs_amt if is_refund else 0.0
                    credit_amt = 0.0 if is_refund else abs_amt
                    partner_id = line._get_partner_id(credit_account=True)
                    credit_vals = {
                        'name': f"{slip.employee_id.name} - {line.name}",
                        'partner_id': partner_id,
                        'account_id': credit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date_entry,
                        'debit': debit_amt,
                        'credit': credit_amt,
                    }
                    if analytic_distribution:
                        credit_vals['analytic_distribution'] = analytic_distribution
                    if rule.account_tax_id:
                        credit_vals['tax_ids'] = [(6, 0, [rule.account_tax_id.id])]
                    line_ids.append((0, 0, credit_vals))
                    debit_sum += debit_amt
                    credit_sum += credit_amt

            if not line_ids:
                continue

            # Auto-balance rounding adjustments if debit and credit sum differ
            if currency.compare_amounts(credit_sum, debit_sum) == -1:
                acc_id = slip.journal_id.default_account_id.id
                if not acc_id:
                    fallback_acc = self.env['account.account'].search([
                        ('company_ids', 'in', [company_id]),
                        ('account_type', 'in', ('expense', 'liability_current', 'equity_unaffected'))
                    ], limit=1)
                    acc_id = fallback_acc.id if fallback_acc else False
                if acc_id:
                    adjust_credit = (0, 0, {
                        'name': _('Adjustment Entry'),
                        'partner_id': False,
                        'account_id': acc_id,
                        'journal_id': slip.journal_id.id,
                        'date': date_entry,
                        'debit': 0.0,
                        'credit': currency.round(debit_sum - credit_sum),
                    })
                    line_ids.append(adjust_credit)
            elif currency.compare_amounts(debit_sum, credit_sum) == -1:
                acc_id = slip.journal_id.default_account_id.id
                if not acc_id:
                    fallback_acc = self.env['account.account'].search([
                        ('company_ids', 'in', [company_id]),
                        ('account_type', 'in', ('expense', 'liability_current', 'equity_unaffected'))
                    ], limit=1)
                    acc_id = fallback_acc.id if fallback_acc else False
                if acc_id:
                    adjust_debit = (0, 0, {
                        'name': _('Adjustment Entry'),
                        'partner_id': False,
                        'account_id': acc_id,
                        'journal_id': slip.journal_id.id,
                        'date': date_entry,
                        'debit': currency.round(credit_sum - debit_sum),
                        'credit': 0.0,
                    })
                    line_ids.append(adjust_debit)

            move_dict = {
                'narration': _('Payslip of %s (%s - %s)') % (slip.employee_id.name, slip.date_from, slip.date_to),
                'ref': slip.number or slip.name,
                'journal_id': slip.journal_id.id,
                'date': date_entry,
                'line_ids': line_ids,
            }
            move = self.env['account.move'].create(move_dict)
            slip.write({'move_id': move.id, 'date': date_entry})
        return True

    def action_open_account_move(self):
        """Opens the related Accounting Entry for this payslip."""
        self.ensure_one()
        if not self.move_id:
            if self.state in ('done', 'paid'):
                self._create_account_move()
        if not self.move_id:
            return False
        return {
            'name': _('Accounting Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
            'target': 'current',
        }
