import psycopg2

conn = psycopg2.connect(dbname='RevisedPayroll', user='odoo', password='odoopwd', host='localhost', port=5432)
cur = conn.cursor()

cur.execute("""
    SELECT r.code, r.name, c.code, c.name, r.hds_in_contributes_to_employer_cost
    FROM hr_salary_rule r
    LEFT JOIN hr_salary_rule_category c ON c.id = r.category_id
    WHERE r.code IN ('EMPLOYER_EPF', 'EPS', 'EPF_SHARE', 'EDLI', 'EPF_ADMIN', 'EDLI_ADMIN', 'ESIC_ER', 'LWF_ER', 'GROSS', 'NET')
""")
for row in cur.fetchall():
    print(row)
