"""
Restore database from JSON backup file.
Usage: python restore_backup.py /path/to/auto_backup_20260318_2200.json
"""
import json
import sys
import os
from dotenv import load_dotenv

load_dotenv()

import pymysql
import pymysql.cursors

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME")


def get_connection():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASSWORD, database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor, autocommit=False
    )


def restore(backup_path: str):
    with open(backup_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = get_connection()
    cur = conn.cursor()

    try:
        # --- init tables (same as db.init_db) ---
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INT PRIMARY KEY AUTO_INCREMENT,
            tg_id BIGINT UNIQUE NOT NULL,
            full_name VARCHAR(255) NOT NULL,
            role ENUM('student','teacher','zavuch') NOT NULL,
            lang ENUM('ru','kk') NOT NULL DEFAULT 'ru',
            class_code VARCHAR(50),
            shift INT DEFAULT 1,
            sub_end_date VARCHAR(20),
            platform VARCHAR(50) DEFAULT 'telegram'
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            class_code VARCHAR(50) PRIMARY KEY,
            class_name VARCHAR(255) NOT NULL,
            shift INT NOT NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            class_code VARCHAR(50) NOT NULL,
            day_idx INT NOT NULL,
            lesson_num INT NOT NULL,
            lesson_name VARCHAR(255) NOT NULL,
            FOREIGN KEY (class_code) REFERENCES classes(class_code),
            UNIQUE KEY unique_lesson (class_code, day_idx, lesson_num)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS invite_codes (
            code VARCHAR(50) PRIMARY KEY,
            role ENUM('student','teacher','zavuch') NOT NULL,
            class_code VARCHAR(50),
            shift INT DEFAULT 1,
            created_by BIGINT NOT NULL,
            created_at VARCHAR(50) NOT NULL,
            is_active TINYINT(1) DEFAULT 1,
            reusable TINYINT(1) DEFAULT 0,
            use_count INT DEFAULT 0
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            `key` VARCHAR(50) PRIMARY KEY,
            `value` VARCHAR(255) NOT NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            tg_id BIGINT NOT NULL,
            setting_key VARCHAR(50) NOT NULL,
            setting_value VARCHAR(50) NOT NULL DEFAULT 'on',
            PRIMARY KEY (tg_id, setting_key)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)
        conn.commit()

        # --- clear existing data (order matters for FK) ---
        cur.execute("DELETE FROM lessons")
        cur.execute("DELETE FROM users")
        cur.execute("DELETE FROM invite_codes")
        cur.execute("DELETE FROM settings")
        cur.execute("DELETE FROM classes")
        conn.commit()

        # 1. Classes
        for c in data.get("classes", []):
            cur.execute(
                "INSERT INTO classes (class_code, class_name, shift) VALUES (%s, %s, %s)",
                (c["class_code"], c["class_name"], c["shift"])
            )
        print(f"✅ Классы: {len(data.get('classes', []))}")

        # 2. Users
        for u in data.get("users", []):
            cur.execute(
                """INSERT INTO users (tg_id, full_name, role, lang, class_code, shift, sub_end_date, platform)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (u["tg_id"], u["full_name"], u["role"], u["lang"],
                 u.get("class_code"), u.get("shift", 1),
                 u.get("sub_end_date"), u.get("platform", "telegram"))
            )
        print(f"✅ Пользователи: {len(data.get('users', []))}")

        # 3. Lessons
        for ls in data.get("lessons", []):
            cur.execute(
                "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                (ls["class_code"], ls["day_idx"], ls["lesson_num"], ls["lesson_name"])
            )
        print(f"✅ Уроки: {len(data.get('lessons', []))}")

        # 4. Invite codes
        for ic in data.get("invite_codes", []):
            cur.execute(
                """INSERT INTO invite_codes (code, role, class_code, shift, created_by, created_at, is_active, reusable, use_count)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (ic["code"], ic["role"], ic.get("class_code"), ic.get("shift", 1),
                 ic["created_by"], ic["created_at"], ic.get("is_active", 1),
                 ic.get("reusable", 0), ic.get("use_count", 0))
            )
        print(f"✅ Инвайт-коды: {len(data.get('invite_codes', []))}")

        # 5. Settings
        for s in data.get("settings", []):
            cur.execute(
                "REPLACE INTO settings (`key`, `value`) VALUES (%s, %s)",
                (s["key"], s["value"])
            )
        print(f"✅ Настройки: {len(data.get('settings', []))}")

        conn.commit()
        print("\n🎉 Бэкап успешно восстановлен!")

    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python restore_backup.py <backup.json>")
        sys.exit(1)
    restore(sys.argv[1])
