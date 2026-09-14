import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("SELECT id, arch_db FROM ir_ui_view WHERE id = 2715;")
row = cur.fetchone()
print('ID:', row[0])
print('arch_db keys:', row[1].keys() if isinstance(row[1], dict) else type(row[1]))
val = row[1].get('en_US', '') if isinstance(row[1], dict) else str(row[1])
print('First 300 chars of arch_db:', val[:300])

conn.close()
