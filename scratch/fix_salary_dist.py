import psycopg2, json

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

# Get all employees and their bank accounts from employee_bank_account_rel
cur.execute("""
    SELECT e.id, ARRAY_AGG(r.bank_account_id)
    FROM hr_employee e
    LEFT JOIN employee_bank_account_rel r ON r.employee_id = e.id
    GROUP BY e.id
""")
rows = cur.fetchall()

for emp_id, bank_ids in rows:
    valid_banks = [b for b in bank_ids if b is not None]
    dist = {}
    for idx, b_id in enumerate(valid_banks):
        dist[str(b_id)] = {
            'sequence': idx,
            'amount': 100.0 if idx == 0 else 0.0,
            'amount_is_percentage': True
        }
    dist_json = json.dumps(dist)
    print(f"Updating emp {emp_id} with salary_distribution = {dist_json}")
    cur.execute("UPDATE hr_employee SET salary_distribution = %s::jsonb WHERE id = %s", (dist_json, emp_id))

conn.commit()
print("Salary distribution populated successfully for all employees!")
