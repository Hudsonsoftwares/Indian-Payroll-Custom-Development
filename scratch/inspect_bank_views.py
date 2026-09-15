import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

cur.execute("SELECT * FROM employee_bank_account_rel")
print("employee_bank_account_rel:", cur.fetchall())
