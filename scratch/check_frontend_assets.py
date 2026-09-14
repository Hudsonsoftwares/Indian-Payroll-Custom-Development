import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("SELECT id, name, bundle, path FROM ir_asset WHERE bundle = 'web.assets_frontend'")
rows = cur.fetchall()
print(f"Total rows in web.assets_frontend: {len(rows)}")
for r in rows:
    if 'hudson' in r[3] or 'kitchen' in r[3]:
        print("Found:", r)
