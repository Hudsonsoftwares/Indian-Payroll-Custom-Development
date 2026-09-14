import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("SELECT id, pos_order_id, table_name, customer_count, stage_id FROM pos_prep_order WHERE display_id = 1")
print("Orders:", cur.fetchall())
cur.execute("SELECT id, name FROM pos_prep_display_stage WHERE display_id = 1 ORDER BY sequence")
print("Stages:", cur.fetchall())
