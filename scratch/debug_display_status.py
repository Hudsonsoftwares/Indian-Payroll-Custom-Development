from datetime import datetime, timezone, timedelta
import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

# Check display 1 stages
cur.execute("SELECT id, name, sequence FROM pos_prep_display_stage WHERE display_id = 1;")
print("Stages:", cur.fetchall())

# Check all orders for display 1
cur.execute("SELECT id, display_id, stage_id, active, done_date, write_date, create_date, table_name FROM pos_prep_order WHERE display_id = 1 ORDER BY id DESC LIMIT 5;")
print("Recent orders:", cur.fetchall())

conn.close()
