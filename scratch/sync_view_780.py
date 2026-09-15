import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

new_arch = """<data><xpath expr="//field[@name='employee_type']" position="replace">
    <field name="employee_type" invisible="1"/>
    <field name="employee_type_id" string="Employee Type" placeholder="Employee Type" options="{'no_create': True, 'no_create_edit': True}"/>
</xpath>
<xpath expr="//field[@name='contract_type_id']" position="attributes">
    <attribute name="invisible">1</attribute>
</xpath></data>"""

cur.execute("""
    UPDATE ir_ui_view 
    SET arch_db = jsonb_set(arch_db, '{en_US}', to_jsonb(%s::text))
    WHERE id = 780
""", (new_arch,))
conn.commit()
print("View 780 updated in DB successfully!")
