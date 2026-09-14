import psycopg2
from datetime import datetime, timedelta

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

# Query active and recent done orders for display 1
cur.execute("""
    SELECT id, stage_id, active, done_date, write_date, table_name 
    FROM pos_prep_order 
    WHERE display_id = 1 
      AND (active = TRUE OR done_date >= NOW() - INTERVAL '30 minutes' OR write_date >= NOW() - INTERVAL '30 minutes')
    ORDER BY id DESC;
""")
rows = cur.fetchall()
print("Matching orders for Order Status Screen:")
for r in rows:
    print(r)

conn.close()
