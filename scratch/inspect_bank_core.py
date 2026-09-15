file_path = r"C:\Program Files\Odoo 19.0.20260717\server\odoo\addons\hr\models\hr_employee.py"
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

import re
match = re.search(r'def _compute_primary_bank_account_id.*', text)
if match:
    start = match.start()
    print(text[start:start+1000])
