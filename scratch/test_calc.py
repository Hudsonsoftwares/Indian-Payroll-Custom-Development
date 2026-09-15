import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

cur.execute("""
    SELECT s.id, s.number, e.name, s.state, s.date_from, s.date_to
    FROM hr_payslip s
    JOIN hr_employee e ON e.id = s.employee_id
    WHERE s.date_from <= '2026-09-30' AND s.date_to >= '2026-09-01' AND s.state != 'cancel'
    ORDER BY s.id
""")
slips = cur.fetchall()

# Deduplicate by employee
latest_slips = {}
for s in sorted(slips, key=lambda x: (4 if x[3]=='paid' else (3 if x[3]=='done' else (2 if x[3]=='verify' else 1)), x[0]), reverse=True):
    emp_id = s[2]
    if emp_id not in latest_slips:
        latest_slips[emp_id] = s

tot_gross = 0.0
tot_employer = 0.0
tot_net_payable = 0.0
tot_net_paid = 0.0
tot_epf = 0.0
tot_esi = 0.0

print("=== SELECTED SLIPS ===")
for emp, s in latest_slips.items():
    slip_id = s[0]
    cur.execute("SELECT code, total FROM hr_payslip_line WHERE slip_id = %s", (slip_id,))
    lines = cur.fetchall()
    
    gross = 0.0
    net = 0.0
    employer_cost = 0.0
    epf = 0.0
    esi = 0.0
    
    codes = set(l[0] for l in lines)
    has_er_epf = 'EMPLOYER_EPF' in codes or 'ER_PF' in codes
    
    for l in lines:
        code = l[0]
        amt = float(l[1] or 0.0)
        
        if code == 'GROSS':
            gross = abs(amt)
        elif code == 'NET':
            net = abs(amt)
            
        # EPF
        if code in ('PF', 'EPF', 'EE_PF'):
            epf += abs(amt)
        elif code in ('EMPLOYER_EPF', 'ER_PF'):
            epf += abs(amt)
        elif not has_er_epf and code in ('EPS', 'EPF_SHARE'):
            epf += abs(amt)
        elif code in ('EDLI', 'EPF_ADMIN', 'EDLI_ADMIN'):
            epf += abs(amt)
            
        # ESIC
        if code in ('ESIC_EE', 'EE_ESI'):
            esi += abs(amt)
        elif code in ('ESIC_ER', 'ER_ESI'):
            esi += abs(amt)
            
        # Employer Cost
        if code in ('EMPLOYER_EPF', 'EDLI', 'EPF_ADMIN', 'EDLI_ADMIN', 'ESIC_ER', 'LWF_ER'):
            employer_cost += abs(amt)
        elif not has_er_epf and code in ('EPS', 'EPF_SHARE'):
            employer_cost += abs(amt)
            
    tot_gross += gross
    tot_employer += employer_cost
    tot_epf += epf
    tot_esi += esi
    
    if s[3] == 'paid':
        tot_net_paid += net
    else:
        tot_net_payable += net
        
    print(f"Slip {slip_id} ({emp}, state={s[3]}): Gross={gross}, EmployerCost={employer_cost}, TotalCost={gross+employer_cost}, Net={net}")

print("\n=== TOTALS ===")
print(f"Total Gross: {tot_gross:,.2f}")
print(f"Total Employer Contributions: {tot_employer:,.2f}")
print(f"Total Payroll Cost (Gross + Employer): {tot_gross + tot_employer:,.2f}")
print(f"Total Net Paid (Disbursed): {tot_net_paid:,.2f}")
print(f"Total Net Payable (Pending): {tot_net_payable:,.2f}")
print(f"Total EPF Liability: {tot_epf:,.2f}")
print(f"Total ESIC Liability: {tot_esi:,.2f}")
