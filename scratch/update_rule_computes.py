import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
reg = odoo.modules.registry.Registry('RevisedPayroll')
with reg.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("UPDATE ir_model_data SET noupdate = False WHERE module = 'hudson_attendance_payroll_link'")
    short_code = """result = -contract.get_period_shortage_rate(payslip.date_from, payslip.date_to)
shortage_hours = worked_days.SHORTAGE.number_of_hours if (worked_days.SHORTAGE and contract.pay_by_attendance) else 0.0
raw_ded = shortage_hours * abs(result)
total_earnings = categories.BASIC + categories.ALW
result = -min(raw_ded, total_earnings) if total_earnings > 0.0 else 0.0
result_qty = 1.0"""

    unpaid_code = """if worked_days.UNPAID and worked_days.UNPAID.number_of_hours > 0.0:
    raw_ded = worked_days.UNPAID.number_of_hours * contract.get_period_shortage_rate(payslip.date_from, payslip.date_to)
elif worked_days.UNPAID and worked_days.UNPAID.number_of_days > 0.0:
    raw_ded = worked_days.UNPAID.number_of_days * contract.get_period_day_rate(payslip.date_from, payslip.date_to)
else:
    raw_ded = 0.0
total_earnings = categories.BASIC + categories.ALW
short_ded = abs(rules.SHORT.total if 'SHORT' in rules else 0.0)
rem_earnings = max(0.0, total_earnings - short_ded)
result = -min(raw_ded, rem_earnings) if rem_earnings > 0.0 else 0.0
result_qty = 1.0"""

    rule_short = env['hr.salary.rule'].search([('code', '=', 'SHORT')], limit=1)
    if rule_short:
        rule_short.write({'amount_python_compute': short_code})
    rule_unpaid = env['hr.salary.rule'].search([('code', '=', 'UNPAID')], limit=1)
    if rule_unpaid:
        rule_unpaid.write({'amount_python_compute': unpaid_code})
    rule_net = env['hr.salary.rule'].search([('code', '=', 'NET')], limit=1)
    if rule_net:
        rule_net.write({'amount_python_compute': 'result = max(0.0, categories.BASIC + categories.ALW + categories.DED)'})
    cr.commit()
    print("Successfully updated SHORT, UNPAID, and NET salary rule definitions!")
