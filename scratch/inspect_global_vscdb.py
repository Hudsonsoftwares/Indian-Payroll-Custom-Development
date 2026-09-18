import sqlite3
import json

db_path = r'C:\Users\DELL\AppData\Roaming\Antigravity IDE\User\globalStorage\state.vscdb'
con = sqlite3.connect(db_path)
cur = con.cursor()
for k, v in cur.execute("SELECT key, value FROM ItemTable WHERE key LIKE '%chat%' OR key LIKE '%antigravity%' OR key LIKE '%conv%' OR key LIKE '%session%'"):
    print("KEY:", k)
    try:
        data = json.loads(v)
        print("VALUE (json):", json.dumps(data, indent=2)[:1000])
    except Exception:
        print("VALUE (raw):", str(v)[:500])
    print("-" * 50)
con.close()
