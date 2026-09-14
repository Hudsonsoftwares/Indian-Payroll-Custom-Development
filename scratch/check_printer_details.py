import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

cur.execute("SELECT id, name, module_pos_restaurant FROM pos_config")
for r in cur.fetchall():
    print("POS Config:", r)

cur.execute("SELECT * FROM pos_printer")
print("Existing printers:", cur.fetchall())

cur.execute("SELECT * FROM pos_config_printer_rel")
print("POS config printer relations:", cur.fetchall())

cur.execute("SELECT id, name FROM pos_category")
print("POS categories:", cur.fetchall())
