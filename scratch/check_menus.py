import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("""
    SELECT m.id, d.module, d.name, m.name->>'en_US' as menu_name, p.name->>'en_US' as parent_name, m.action 
    FROM ir_ui_menu m 
    JOIN ir_model_data d ON d.res_id = m.id AND d.model = 'ir.ui.menu'
    LEFT JOIN ir_ui_menu p ON m.parent_id = p.id 
    WHERE m.name::text ILIKE '%work entr%' OR m.name::text ILIKE '%time off%' OR (p.name IS NOT NULL AND p.name::text ILIKE '%work entr%')
""")
for r in cur.fetchall():
    print(r)
