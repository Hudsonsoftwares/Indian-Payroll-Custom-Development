import sqlite3
import base64
import re

db_path = r'C:\Users\DELL\AppData\Roaming\Antigravity IDE\User\globalStorage\state.vscdb'
con = sqlite3.connect(db_path)
val = con.execute("SELECT value FROM ItemTable WHERE key='antigravityUnifiedStateSync.trajectorySummaries'").fetchone()[0]
raw = base64.b64decode(val)
uuids = [u.decode('ascii') for u in re.findall(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', raw)]
print("Found UUIDs count:", len(uuids))
for u in set(uuids):
    print(u)
con.close()
