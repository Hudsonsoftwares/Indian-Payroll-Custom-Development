import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'pos_order' AND column_name IN ('tracking_number', 'sequence_number', 'pos_reference', 'table_id', 'ticket_code');
""")
print('pos_order columns:', cur.fetchall())

cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'pos_prep_order';
""")
print('pos_prep_order columns:', cur.fetchall())

cur.execute("""
    SELECT id, access_token, name FROM pos_prep_display LIMIT 5;
""")
print('displays:', cur.fetchall())

cur.execute("""
    SELECT id, pos_reference, tracking_number FROM pos_order ORDER BY id DESC LIMIT 5;
""" if 'tracking_number' else "SELECT id, pos_reference FROM pos_order ORDER BY id DESC LIMIT 5;")
try:
    print('recent pos orders:', cur.fetchall())
except:
    pass

conn.close()
