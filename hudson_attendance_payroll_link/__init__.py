from . import models


def post_init_hook(env):
    # Colorize public/bank holiday leave types for visual clarity
    leave_types = env['hr.leave.type'].sudo().search([])
    for lt in leave_types:
        name = lt.name or ''
        if any(keyword in name.lower() for keyword in ['public', 'holiday', 'bank', 'global']):
            lt.color = 2

    # Retroactively fix any existing contracts with 0.0 shortage deduction rate.
    # Overtime rates are now managed by Standard Odoo 19 Overtime Rulesets —
    # no retroactive fix needed for OT rates.
    contracts = env['hr.version'].sudo().search([])
    for contract in contracts:
        if contract.shortage_deduction_rate_per_hour == 0.0:
            days = contract.standard_working_days_per_month or 26.0
            hours = contract.standard_hours_per_day or 8.0
            divisor = days * hours
            computed_hourly = contract.wage / divisor if divisor else 0.0
            if computed_hourly > 0.0:
                contract.write({
                    'shortage_deduction_rate_per_hour': computed_hourly,
                    'shortage_rate_manually_set': False,
                })
