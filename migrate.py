"""Migration script: adds 'platform' column and marks WhatsApp users."""
from db import pooled_connection

with pooled_connection() as conn:
    with conn.cursor() as cursor:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN platform VARCHAR(50) DEFAULT 'telegram'")
            print("Column 'platform' added.")
        except Exception as e:
            if "Duplicate column" in str(e):
                print("Column 'platform' already exists.")
            else:
                raise

        cursor.execute("UPDATE users SET platform = 'whatsapp' WHERE tg_id > 10000000000")
        print("WhatsApp users marked.")

        cursor.execute("SELECT code, role FROM invite_codes WHERE role IN ('teacher', 'zavuch') AND is_active = 1")
        for c in cursor.fetchall():
            print(f"ACTIVE_CODE|{c['role']}|{c['code']}")
