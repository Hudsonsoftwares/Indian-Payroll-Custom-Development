from . import models

def post_init_hook(env):
    leave_types = env['hr.leave.type'].sudo().search([])
    for lt in leave_types:
        name = lt.name or ''
        if any(keyword in name.lower() for keyword in ['public', 'holiday', 'bank', 'global']):
            lt.color = 2

    # Retroactively fix any existing contracts saved with 0.0 rates
    contracts = env['hr.version'].sudo().search([])
    for contract in contracts:
        if contract.overtime_rate_per_hour == 0.0 or contract.shortage_deduction_rate_per_hour == 0.0:
            days = contract.standard_working_days_per_month or 26.0
            hours = contract.standard_hours_per_day or 8.0
            mult = contract.overtime_multiplier or 1.0
            divisor = days * hours
            computed_hourly = contract.wage / divisor if divisor else 0.0
            
            vals = {}
            if contract.overtime_rate_per_hour == 0.0:
                vals['overtime_rate_per_hour'] = computed_hourly * mult
                vals['overtime_rate_manually_set'] = False
            if contract.shortage_deduction_rate_per_hour == 0.0:
                vals['shortage_deduction_rate_per_hour'] = computed_hourly
                vals['shortage_rate_manually_set'] = False
                
            if vals:
                contract.write(vals)
