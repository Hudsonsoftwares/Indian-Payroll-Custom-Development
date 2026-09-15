import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

cur.execute("SELECT id, name, salary_distribution FROM hr_employee")
for r in cur.fetchall():
    print(r)
