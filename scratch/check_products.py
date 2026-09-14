import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("SELECT id, default_code FROM product_product LIMIT 5")
print("Product products:", cur.fetchall())
cur.execute("SELECT id, name FROM pos_config LIMIT 5")
for r in cur.fetchall():
    print("POS:", r)
cur.execute("SELECT id, name FROM pos_prep_display")
for r in cur.fetchall():
    print("Display:", r)
cur.execute("SELECT id, name, sequence, color FROM pos_prep_display_stage WHERE display_id = 1 ORDER BY sequence")
for r in cur.fetchall():
    print("Stages:", r)
