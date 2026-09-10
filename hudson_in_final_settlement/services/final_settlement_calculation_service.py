# -*- coding: utf-8 -*-
from odoo import fields, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class FinalSettlementCalculationService:
    """
    Enterprise Settlement Orchestration Service for Hudson Indian Final Settlement Module.
    Single Responsibility: Orchestrate computation across pluggable statutory component services
    (Leave Encashment, Gratuity, PF, Notice Pay) and maintain idempotent breakdown lines on final.settlement.
    Does NOT contain statutory calculation formulas or validation rules.
    """

    def __init__(self, env):
        self.env = env

    def compute_settlement(self, settlement):
        """
        Orchestrates full settlement calculation for a given final.settlement record.

        :param settlement: final.settlement recordset (required)
        :return: dict summary of created/updated lines
        """
        if not settlement:
            raise ValueError(_("Final settlement record is required for calculation."))

        settlement.ensure_one()

        employee = settlement.employee_id
        if not employee:
            raise UserError(_("Please select an employee on the settlement record before calculating."))

        lwd = settlement.last_working_day or fields.Date.today()
        calc_results = []

        # 1. Compute Leave Encashment Component
        le_res = self._compute_leave_encashment_component(settlement, employee, lwd)
        if le_res:
            calc_results.append(le_res)

        # 2. Pluggable Extension Point for Gratuity Component
        gratuity_res = self._compute_gratuity_component(settlement, employee, lwd)
        if gratuity_res:
            calc_results.append(gratuity_res)

        # 3. Synchronize lines idempotently
        updated_lines = self._sync_settlement_lines(settlement, calc_results)

        _logger.info("Successfully computed final settlement %s for employee %s: %s lines processed.",
                     settlement.name, employee.name, len(updated_lines))

        return {
            'settlement_id': settlement.id,
            'processed_lines': len(updated_lines),
            'total_earnings': settlement.total_earnings,
            'total_deductions': settlement.total_deductions,
            'net_amount': settlement.net_settlement_amount,
        }

    def _compute_leave_encashment_component(self, settlement, employee, lwd):
        """
        Calls LeaveEncashmentService statutory SOA component.
        """
        try:
            from odoo.addons.hudson_in_payroll.services.leave_encashment import LeaveEncashmentService
            le_service = LeaveEncashmentService(self.env)
            amount = le_service.compute_leave_encashment(
                employee=employee,
                last_working_day=lwd,
                calc_date=settlement.settlement_date
            )
            return {
                'component_code': 'LEAVE_ENCASH',
                'component_name': _('Leave Encashment'),
                'line_type': 'earning',
                'amount': float(amount or 0.0),
                'description': _('Statutory leave encashment calculated as of last working day %s.') % lwd,
            }
        except Exception as e:
            _logger.warning("Leave Encashment computation skipped/failed for settlement %s: %s", settlement.name, str(e))
            return {
                'component_code': 'LEAVE_ENCASH',
                'component_name': _('Leave Encashment'),
                'line_type': 'earning',
                'amount': 0.0,
                'description': _('Leave Encashment not applicable or disabled (%s).') % str(e),
            }

    def _compute_gratuity_component(self, settlement, employee, lwd):
        """
        Calls GratuityService statutory SOA component using existing API.
        """
        try:
            try:
                from odoo.addons.hudson_in_payroll.services.gratuity.gratuity_service import GratuityService
            except (ImportError, ValueError):
                from odoo.addons.hudson_in_payroll.services.gratuity import GratuityService

            contract = self.env['hr.version'].search([
                ('employee_id', '=', employee.id)
            ], order='id desc', limit=1)

            gratuity_service = GratuityService(self.env, localdict={'employee': employee, 'contract': contract})
            amount = gratuity_service.compute_gratuity(separation_date=lwd)
            return {
                'component_code': 'GRATUITY',
                'component_name': _('Gratuity'),
                'line_type': 'earning',
                'amount': float(amount or 0.0),
                'description': _('Statutory gratuity calculated under Payment of Gratuity Act 1972 as of last working day %s.') % lwd,
            }
        except Exception as e:
            _logger.warning("Gratuity computation skipped/failed for settlement %s: %s", settlement.name, str(e))
            return {
                'component_code': 'GRATUITY',
                'component_name': _('Gratuity'),
                'line_type': 'earning',
                'amount': 0.0,
                'description': _('Gratuity not applicable or ineligible (%s).') % str(e),
            }

    def _sync_settlement_lines(self, settlement, component_results):
        """
        Idempotently creates or updates final.settlement.line records for settlement.
        Matches by component_code. If amount is >= 0, updates existing line or creates new line.
        """
        line_model = self.env['final.settlement.line']
        existing_lines = {l.component_code: l for l in settlement.line_ids}
        synced_line_ids = []

        for comp in component_results:
            code = comp['component_code']
            amount = float(comp.get('amount', 0.0))

            if code in existing_lines:
                line = existing_lines[code]
                line.write({
                    'component_name': comp['component_name'],
                    'line_type': comp['line_type'],
                    'amount': amount,
                    'description': comp.get('description', ''),
                })
                synced_line_ids.append(line.id)
            else:
                new_line = line_model.create({
                    'settlement_id': settlement.id,
                    'component_code': code,
                    'component_name': comp['component_name'],
                    'line_type': comp['line_type'],
                    'amount': amount,
                    'description': comp.get('description', ''),
                })
                synced_line_ids.append(new_line.id)

        # Trigger recomputation of totals on settlement
        settlement._compute_settlement_totals()
        return synced_line_ids
