import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("""
    SELECT column_name FROM information_schema.columns WHERE table_name = 'tds_house_property_loss_carryforward'
""")
cols = [r[0] for r in cur.fetchall()]
print("EXISTING COLS:", cols)
