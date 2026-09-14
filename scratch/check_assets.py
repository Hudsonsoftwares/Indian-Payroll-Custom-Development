import psycopg2
conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("SELECT name, path, bundle FROM ir_asset WHERE path LIKE '%pos_prep_display%'")
rows = cur.fetchall()
print("ir_asset rows:", rows)
