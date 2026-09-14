import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%printer%'")
print("Printer tables:", cur.fetchall())

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%pos_config%'")
print("Pos config tables:", cur.fetchall())

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'pos_printer'")
print("pos_printer columns:", [r[0] for r in cur.fetchall()])
