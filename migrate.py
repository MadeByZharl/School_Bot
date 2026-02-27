import sqlite3

conn = sqlite3.connect("school_bot.db")
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE users ADD COLUMN platform TEXT DEFAULT 'telegram'")
    conn.commit()
    print("Column 'platform' added.")
except sqlite3.OperationalError:
    print("Column 'platform' already exists.")

cursor.execute("UPDATE users SET platform = 'whatsapp' WHERE tg_id > 10000000000")
conn.commit()

cursor.execute("SELECT code, role FROM invite_codes WHERE role IN ('teacher', 'zavuch') AND is_active = 1")
for c in cursor.fetchall():
    print(f"ACTIVE_CODE|{c[1]}|{c[0]}")
