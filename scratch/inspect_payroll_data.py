import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

print("=== PAYSLIP BATCHES (hr_payslip_run) ===")
cur.execute("SELECT id, name, date_start, date_end, state FROM hr_payslip_run")
for r in cur.fetchall():
    print(r)

print("\n=== PAYSLIPS WITH BATCH ID ===")
cur.execute("SELECT id, number, name, employee_id, payslip_run_id, state FROM hr_payslip")
for r in cur.fetchall():
    print(r)
