import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("SELECT id, pos_order_id, display_id, stage_id, fulfillment_type FROM pos_prep_order")
orders = cur.fetchall()
print("pos_prep_order rows:", len(orders), orders)
cur.execute("SELECT id, name, pos_reference FROM pos_order")
pos_orders = cur.fetchall()
print("pos_order rows:", len(pos_orders), pos_orders)
