import psycopg2
import xml.etree.ElementTree as ET

tree = ET.parse(r'hudson_kitchen_display\views\pos_prep_display_views.xml')
root = tree.getroot()

kanban_record = None
for rec in root.findall('.//record'):
    if rec.get('id') == 'view_pos_prep_display_kanban':
        kanban_record = rec
        break

arch_elem = kanban_record.find("field[@name='arch']")
kanban_elem = arch_elem.find('kanban')
arch_str = ET.tostring(kanban_elem, encoding='unicode')

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("UPDATE ir_ui_view SET arch_db = jsonb_set(arch_db, '{en_US}', to_jsonb(%s::text)) WHERE name = %s", (arch_str, 'pos.prep.display.kanban'))
conn.commit()
print("UPDATED ROWS:", cur.rowcount)
