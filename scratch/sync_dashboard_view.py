import psycopg2
import xml.etree.ElementTree as ET

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

# Find view
cur.execute("SELECT id, name, model FROM ir_ui_view WHERE name = 'hds.payroll.dashboard.form' OR model = 'hds.payroll.dashboard'")
rows = cur.fetchall()
print("Found views:", rows)

tree = ET.parse(r'hudson_in_payroll\views\payroll_dashboard_views.xml')
root = tree.getroot()

form_record = None
for rec in root.findall('.//record'):
    if rec.get('id') == 'hds_payroll_dashboard_view_form':
        form_record = rec
        break

if form_record is not None:
    arch_elem = form_record.find("field[@name='arch']")
    form_elem = arch_elem.find('form')
    arch_str = ET.tostring(form_elem, encoding='unicode')
    
    # Check if arch_db is jsonb in Odoo 19
    cur.execute("SELECT pg_typeof(arch_db) FROM ir_ui_view WHERE name = 'hds.payroll.dashboard.form' LIMIT 1")
    col_type = cur.fetchone()[0]
    print("arch_db type:", col_type)
    
    if col_type == 'jsonb':
        cur.execute("UPDATE ir_ui_view SET arch_db = jsonb_set(arch_db, '{en_US}', to_jsonb(%s::text)) WHERE name = 'hds.payroll.dashboard.form'", (arch_str,))
    else:
        cur.execute("UPDATE ir_ui_view SET arch_db = %s WHERE name = 'hds.payroll.dashboard.form'", (arch_str,))
    conn.commit()
    print("Updated form view rows:", cur.rowcount)
