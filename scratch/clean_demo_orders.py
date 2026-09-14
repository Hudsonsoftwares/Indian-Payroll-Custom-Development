import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

# Find the demo pos_orders we created
cur.execute("SELECT id FROM pos_order WHERE pos_reference LIKE 'Order 0000%'")
demo_pos_ids = [r[0] for r in cur.fetchall()]
print("Found demo pos_order IDs:", demo_pos_ids)

if demo_pos_ids:
    cur.execute("DELETE FROM pos_prep_order_line WHERE prep_order_id IN (SELECT id FROM pos_prep_order WHERE pos_order_id = ANY(%s))", (demo_pos_ids,))
    cur.execute("DELETE FROM pos_prep_order WHERE pos_order_id = ANY(%s)", (demo_pos_ids,))
    cur.execute("DELETE FROM pos_order WHERE id = ANY(%s)", (demo_pos_ids,))
    print("Deleted demo pos orders and prep orders!")

cur.execute("SELECT count(*) FROM pos_prep_order")
print("Remaining pos_prep_order count:", cur.fetchone()[0])

conn.commit()
conn.close()
