import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("SELECT id, name, key, type FROM ir_ui_view WHERE key LIKE '%order_status%' OR name LIKE '%order_status%' OR key LIKE '%kitchen%' OR name LIKE '%kitchen%';")
for r in cur.fetchall():
    print(r)

conn.close()
