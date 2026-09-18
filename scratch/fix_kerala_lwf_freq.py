import sys
sys.path.insert(0, r"C:\Program Files\Odoo 19.0.20260717\server")
import odoo
from odoo.tools import config
from odoo.modules.registry import Registry
from odoo import api, SUPERUSER_ID

config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf', '-d', 'RevisedPayroll'])
registry = Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    r = env['lwf.state.rate'].browse(4)
    print("Before fix:", r.name, r.deduction_frequency, r.deduction_month_1, r.deduction_month_2)
    r.write({
        'deduction_frequency': 'half_yearly',
        'deduction_month_1': '6',
        'deduction_month_2': '12',
    })
    print("After fix:", r.name, r.deduction_frequency, r.deduction_month_1, r.deduction_month_2)
    
    # Check eval dates
    import datetime
    d_oct = datetime.date(2026, 10, 31)
    d_nov = datetime.date(2026, 11, 30)
    d_dec = datetime.date(2026, 12, 31)
    d_jun = datetime.date(2026, 6, 30)
    print("Is Oct deduction month?", r.is_deduction_month(d_oct))
    print("Is Nov deduction month?", r.is_deduction_month(d_nov))
    print("Is Dec deduction month?", r.is_deduction_month(d_dec))
    print("Is Jun deduction month?", r.is_deduction_month(d_jun))
    
    # Recompute Slip 388 (October) and check LWF
    slip_oct = env['hr.payslip'].browse(388)
    slip_oct.action_compute_sheet()
    lwf_ee = slip_oct.line_ids.filtered(lambda l: l.code == 'LWF_EE').total
    lwf_er = slip_oct.line_ids.filtered(lambda l: l.code == 'LWF_ER').total
    print(f"\nRecomputed Slip 388 (October): LWF_EE={lwf_ee}, LWF_ER={lwf_er}, Net={slip_oct.net_wage}")
    
    # Recompute Slip 389 (November) and check LWF
    slip_nov = env['hr.payslip'].browse(389)
    slip_nov.action_compute_sheet()
    lwf_ee_nov = slip_nov.line_ids.filtered(lambda l: l.code == 'LWF_EE').total
    lwf_er_nov = slip_nov.line_ids.filtered(lambda l: l.code == 'LWF_ER').total
    print(f"Recomputed Slip 389 (November): LWF_EE={lwf_ee_nov}, LWF_ER={lwf_er_nov}, Net={slip_nov.net_wage}")
    
    cr.commit()
    print("Committed successfully!")
