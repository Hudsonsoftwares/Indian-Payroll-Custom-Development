import psycopg2
import re

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

cur.execute("SELECT name, path, bundle FROM ir_asset WHERE path LIKE '%payroll_dashboard_navigation%'")
print("Asset in ir_asset:", cur.fetchall())

cur.execute("SELECT id, dashboard_html FROM hds_payroll_dashboard LIMIT 1")
row = cur.fetchone()
if row:
    html = row[1] or ""
    print("Dashboard ID:", row[0])
    print("Has target=_blank:", "target=" in html)
    print("Sample tags:")
    for tag in re.findall(r'<a[^>]*>', html)[:10]:
        print("  ", tag)
else:
    print("No dashboard row found")
