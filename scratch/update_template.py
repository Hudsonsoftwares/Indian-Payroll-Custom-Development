import psycopg2
import xml.etree.ElementTree as ET

tree = ET.parse(r'e:\New Payroll\hudson_kitchen_display\views\templates.xml')
root = tree.getroot()

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

for t in root.findall('.//template'):
    tmpl_id = t.get('id')
    if not tmpl_id:
        continue
    arch_str = ET.tostring(t, encoding='unicode')
    full_key = f'hudson_kitchen_display.{tmpl_id}'
    
    cur.execute("""
        UPDATE ir_ui_view 
        SET arch_db = jsonb_set(arch_db, '{en_US}', to_jsonb(%s::text)) 
        WHERE key = %s
    """, (arch_str, full_key))
    updated = cur.rowcount
    if updated == 0:
        cur.execute("""
            UPDATE ir_ui_view 
            SET arch_db = jsonb_set(arch_db, '{en_US}', to_jsonb(%s::text)) 
            WHERE name = %s
        """, (arch_str, tmpl_id))
        updated = cur.rowcount
    print(f"Template {tmpl_id} ({full_key}) updated rows: {updated}")

conn.commit()
conn.close()
print("All templates updated in database successfully!")
