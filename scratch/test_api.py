import urllib.request
import json

req = urllib.request.Request('http://localhost:8069/web/session/authenticate', 
    data=json.dumps({
        "jsonrpc": "2.0",
        "params": {
            "db": "RevisedPayroll",
            "login": "odoo",
            "password": "odoopwd"
        }
    }).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req) as resp:
        cookies = resp.headers.get('Set-Cookie')
        res = json.loads(resp.read().decode('utf-8'))
        print("Auth result user_id:", res.get('result', {}).get('uid'))
        
        # Test get_orders
        req2 = urllib.request.Request('http://localhost:8069/hudson_kitchen_display/get_orders',
            data=json.dumps({
                "jsonrpc": "2.0",
                "params": {"display_id": 1}
            }).encode('utf-8'),
            headers={"Content-Type": "application/json", "Cookie": cookies}
        )
        with urllib.request.urlopen(req2) as resp2:
            data = json.loads(resp2.read().decode('utf-8'))
            print("Get orders result stages:", len(data.get('result', {}).get('stages', [])))
            print("Get orders result orders count:", len(data.get('result', {}).get('orders', [])))
            for o in data.get('result', {}).get('orders', []):
                print("  Order:", o.get('table_number'), "Guests:", o.get('customer_count'), "Stage:", o.get('stage_id'), "Lines:", o.get('lines'))
except Exception as e:
    print("Error:", e)
