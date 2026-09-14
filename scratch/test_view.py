import psycopg2
conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("SELECT * FROM ir_asset WHERE bundle = 'web.assets_backend'")
for row in cur.fetchall():
    print(row)
