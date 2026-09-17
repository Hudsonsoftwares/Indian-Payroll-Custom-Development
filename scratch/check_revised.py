import sys
sys.path.append(r'C:\Program Files\Odoo 19.0.20260717\server')
import odoo
from odoo import tools, sql_db
tools.config.parse_config(['-c', r'C:\Program Files\Odoo 19.0.20260717\server\odoo.conf'])

conn = sql_db.db_connect('RevisedPayroll')
with conn.cursor() as cr:
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'hr_employee' 
          AND (column_name LIKE '%emergency%' OR column_name LIKE '%aadhaar%' OR column_name LIKE '%identif%' OR column_name LIKE '%contact%')
    """)
    cols = [r[0] for r in cr.fetchall()]
    print("MATCHING COLUMNS:", cols)

    query = f"SELECT id, name, {', '.join(cols)} FROM hr_employee WHERE active = true"
    cr.execute(query)
    for row in cr.fetchall():
        print(row)
