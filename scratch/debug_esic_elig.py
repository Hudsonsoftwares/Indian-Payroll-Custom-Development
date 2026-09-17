import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import api, fields, models, tools

tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])
registry = odoo.modules.registry.Registry('RevisedPayroll')
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    Employee = env['hr.employee']
    emp = Employee.search([('wage', '>', 0)], limit=1)

    from odoo.addons.hudson_in_payroll.services.epf.epf_service import ContractPayslipAdapter
    from odoo.addons.hudson_in_payroll.services.esic.esic_service import ESICService
    from odoo.addons.hudson_in_payroll.services.esic.validator import ESICValidator

    contracts = env['hr.version'].search([('employee_id', '=', emp.id)])
    contract = contracts[0]

    adapter = ContractPayslipAdapter(contract, employee=emp)
    val = ESICValidator(env)
    print("Company hds_in_esic_applicable:", adapter.company_id.hds_in_esic_applicable)
    print("Employee hds_in_esic_applicable:", adapter.employee_id.hds_in_esic_applicable)
    print("Employee ip_status:", adapter.employee_id.hds_in_esic_ip_status)
    print("Employee wage:", adapter.employee_id.wage)
    print("Contract wage:", adapter.contract.wage)

    is_elig = val.is_esic_eligible(adapter, gross_wage=20000.0)
    print("is_esic_eligible:", is_elig)

    svc = ESICService(env)
    er_amount = svc.compute_esic_employer(adapter)
    print("compute_esic_employer:", er_amount)
