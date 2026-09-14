import psycopg2
from datetime import datetime, timedelta

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

# Add table_name and customer_count columns if not present
cur.execute("""
    ALTER TABLE pos_prep_order 
    ADD COLUMN IF NOT EXISTS table_name VARCHAR,
    ADD COLUMN IF NOT EXISTS customer_count INTEGER DEFAULT 2;
""")

# Get pos_config
cur.execute("SELECT id, company_id FROM pos_config LIMIT 1")
cfg_row = cur.fetchone()
pos_config_id = cfg_row[0]
company_id = cfg_row[1] or 1

# Get session
cur.execute("SELECT id FROM pos_session WHERE config_id = %s ORDER BY id DESC LIMIT 1", (pos_config_id,))
sess = cur.fetchone()
if sess:
    session_id = sess[0]
else:
    cur.execute("""
        INSERT INTO pos_session (config_id, user_id, company_id, name, state, start_at, create_uid, write_uid, create_date, write_date)
        VALUES (%s, 1, %s, 'POS/Session/Demo', 'opened', NOW(), 1, 1, NOW(), NOW())
        RETURNING id
    """, (pos_config_id, company_id))
    session_id = cur.fetchone()[0]

# Stages
cur.execute("SELECT id, name FROM pos_prep_display_stage WHERE display_id = 1 ORDER BY sequence")
stages = dict(cur.fetchall())
to_cook_id = None
ready_id = None
completed_id = None
for s_id, s_name in stages.items():
    if s_name == 'To cook': to_cook_id = s_id
    elif s_name == 'Ready': ready_id = s_id
    elif s_name == 'Completed': completed_id = s_id

# Clean existing orders
cur.execute("DELETE FROM pos_prep_order WHERE display_id = 1")

now = datetime.now()

sample_orders = [
    {
        'table': 'T1',
        'guests': 8,
        'stage_id': to_cook_id,
        'created': now - timedelta(minutes=88),
        'lines': [('Salmon and Avocado', 2)]
    },
    {
        'table': 'T4',
        'guests': 5,
        'stage_id': to_cook_id,
        'created': now - timedelta(minutes=88),
        'lines': [('Chicken Curry Sandwich', 1), ('Bacon Burger', 1)]
    },
    {
        'table': 'T6',
        'guests': 2,
        'stage_id': to_cook_id,
        'created': now - timedelta(minutes=80),
        'lines': [('Pasta 4 Formaggi', 1), ('Mozzarella Sandwich', 1), ('Lunch Salmon 20pc', 1)]
    },
    {
        'table': 'T2',
        'guests': 4,
        'stage_id': ready_id,
        'created': now - timedelta(minutes=45),
        'lines': [('Club Sandwich', 1), ('Fresh Orange Juice', 2)]
    },
]

cur.execute("SELECT id FROM product_product LIMIT 1")
prod_id = cur.fetchone()[0]

for idx, o in enumerate(sample_orders):
    ref = f"Order 0000{idx+1}-001-000{idx+1}"
    cur.execute("""
        INSERT INTO pos_order (name, session_id, company_id, pos_reference, customer_count, amount_total, amount_tax, amount_paid, amount_return, state, create_uid, write_uid, create_date, write_date)
        VALUES (%s, %s, %s, %s, %s, 50.0, 5.0, 50.0, 0.0, 'paid', 1, 1, %s, %s)
        RETURNING id
    """, (ref, session_id, company_id, ref, o['guests'], o['created'], o['created']))
    pos_order_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO pos_prep_order (pos_order_id, display_id, stage_id, fulfillment_type, table_name, customer_count, create_uid, write_uid, create_date, write_date)
        VALUES (%s, 1, %s, 'dine_in', %s, %s, 1, 1, %s, %s)
        RETURNING id
    """, (pos_order_id, o['stage_id'], o['table'], o['guests'], o['created'], o['created']))
    prep_order_id = cur.fetchone()[0]

    for line_name, qty in o['lines']:
        cur.execute("""
            INSERT INTO pos_prep_order_line (prep_order_id, product_id, name, qty, create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, %s, %s, 1, 1, NOW(), NOW())
        """, (prep_order_id, prod_id, line_name, qty))

conn.commit()
print("Sample orders created successfully!")
conn.close()
