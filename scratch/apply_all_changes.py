import psycopg2
import xml.etree.ElementTree as ET

# 1. Read XML arch
tree = ET.parse(r'e:\New Payroll\hudson_kitchen_display\views\pos_prep_display_views.xml')
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

# 2. Update ir_ui_view arch_db
cur.execute("UPDATE ir_ui_view SET arch_db = jsonb_set(arch_db, '{en_US}', to_jsonb(%s::text)) WHERE name = %s", (arch_str, 'pos.prep.display.kanban'))
print("Updated ir_ui_view rows:", cur.rowcount)

# 3. Insert or update ir_asset
cur.execute("SELECT id FROM ir_asset WHERE path = '/hudson_kitchen_display/static/src/css/pos_prep_display_backend.css'")
row = cur.fetchone()
if not row:
    cur.execute("""
        INSERT INTO ir_asset (name, bundle, directive, path, target, active, sequence, create_uid, write_uid, create_date, write_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1, NOW(), NOW())
    """, (
        'hudson_kitchen_display_backend_css',
        'web.assets_backend',
        'append',
        '/hudson_kitchen_display/static/src/css/pos_prep_display_backend.css',
        None,
        True,
        100
    ))
    print("Inserted ir_asset row")
else:
    cur.execute("""
        UPDATE ir_asset SET active = true, write_date = NOW() WHERE id = %s
    """, (row[0],))
    print("Updated ir_asset row id:", row[0])

# 4. Clear asset bundle attachments to force regeneration
cur.execute("DELETE FROM ir_attachment WHERE url LIKE '%assets_backend%' OR name LIKE '%assets_backend%'")
print("Deleted cached asset bundles:", cur.rowcount)

# 5. Check pos.prep.display records
cur.execute("SELECT id, name FROM pos_prep_display")
displays = cur.fetchall()
print("Displays found:", displays)

for disp_id, disp_name in displays:
    cur.execute("SELECT id, name, sequence, color FROM pos_prep_display_stage WHERE display_id = %s ORDER BY sequence", (disp_id,))
    stages = cur.fetchall()
    print(f"Stages for display {disp_name} ({disp_id}):", stages)
    if not stages:
        print(f"Creating default stages for {disp_name}")
        cur.execute("""
            INSERT INTO pos_prep_display_stage (display_id, name, sequence, color, alert_timer, create_uid, write_uid, create_date, write_date)
            VALUES 
            (%s, 'To cook', 1, '#C8C9CB', 10, 1, 1, NOW(), NOW()),
            (%s, 'Ready', 2, '#4A90E2', 5, 1, 1, NOW(), NOW()),
            (%s, 'Completed', 3, '#55BA53', 0, 1, 1, NOW(), NOW())
        """, (disp_id, disp_id, disp_id))

conn.commit()
conn.close()
print("SUCCESS!")
