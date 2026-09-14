with open(r'C:\Program Files\Odoo 19.0.20260717\server\odoo\addons\point_of_sale\models\pos_order.py', 'r', encoding='utf-8') as f:
    c = f.read()
    import re
    match = re.search(r'def sync_from_ui.*?\n\s+return', c, re.DOTALL)
    if match:
        print(match.group(0)[:1500])
