import sqlite3
import glob
import os
import datetime

conv_dir = r"C:\Users\DELL\.gemini\antigravity-ide\conversations"
for db_path in glob.glob(os.path.join(conv_dir, "*.db")):
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(db_path)).strftime('%Y-%m-%d %H:%M:%S')
    base = os.path.basename(db_path)
    try:
        con = sqlite3.connect(db_path)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        print(f"File: {base} (Modified: {mtime}) -> Tables: {tables}")
        for t in tables:
            cnt = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            print(f"   {t}: {cnt} rows")
        con.close()
    except Exception as e:
        print(f"File: {base} error: {e}")
