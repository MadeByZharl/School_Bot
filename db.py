import sqlite3
import string
import random
from datetime import datetime, timedelta

DB_PATH = "school_bot.db"

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()


def init_db():
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'zavuch')),
            lang TEXT NOT NULL DEFAULT 'ru' CHECK(lang IN ('ru', 'kk')),
            class_code TEXT,
            shift INTEGER DEFAULT 1 CHECK(shift IN (1, 2)),
            sub_end_date TEXT
        );

        CREATE TABLE IF NOT EXISTS classes (
            class_code TEXT PRIMARY KEY,
            class_name TEXT NOT NULL,
            shift INTEGER NOT NULL CHECK(shift IN (1, 2))
        );

        CREATE TABLE IF NOT EXISTS lessons (
            class_code TEXT NOT NULL,
            day_idx INTEGER NOT NULL CHECK(day_idx BETWEEN 0 AND 6),
            lesson_num INTEGER NOT NULL,
            lesson_name TEXT NOT NULL,
            FOREIGN KEY (class_code) REFERENCES classes(class_code),
            UNIQUE(class_code, day_idx, lesson_num)
        );

        CREATE TABLE IF NOT EXISTS invite_codes (
            code TEXT PRIMARY KEY,
            role TEXT NOT NULL CHECK(role IN ('student', 'teacher')),
            class_code TEXT,
            shift INTEGER DEFAULT 1 CHECK(shift IN (1, 2)),
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            reusable INTEGER DEFAULT 0,
            use_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    cursor.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('bell_mode', 'standard')"
    )
    conn.commit()
    seed_demo_data()


def seed_demo_data():
    cursor.execute(
        "INSERT OR IGNORE INTO classes (class_code, class_name, shift) VALUES (?, ?, ?)",
        ("8Ә", "8 Ә", 1),
    )
    schedule = {
        0: [  # Понедельник
            "Сынып сағаты",
            "Алгебра",
            "Қазақ тілі",
            "Химия",
            "Орыс тілі мен әдебиеті",
            "Шетіл тілі",
            "Қазақстан тарихы",
            "Жаһандық құзыреттілік",
        ],
        1: [  # Вторник
            "Химия",
            "Орыс тілі мен әдебиеті",
            "Информатика",
            "Қазақ әдебиеті",
            "Алгебра",
            "Дүние жүзі тарихы",
            "География",
        ],
        2: [  # Среда
            "Алгебра",
            "Қазақстан тарихы",
            "Қазақ әдебиеті",
            "Физика",
            "Шетіл тілі",
            "Орыс тілі мен әдебиеті",
            "Дене шынықтыру",
        ],
        3: [  # Четверг
            "Дене шынықтыру",
            "Қазақ тілі",
            "Шетіл тілі",
            "Биология",
            "Алгебра",
            "Көркем еңбек",
        ],
        4: [  # Пятница
            "Биология",
            "География",
            "Қазақ әдебиеті",
            "Геометрия",
            "Физика",
            "Дене шынықтыру",
        ],
    }
    for day_idx, lessons in schedule.items():
        for num, name in enumerate(lessons, 1):
            cursor.execute(
                "INSERT OR IGNORE INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (?, ?, ?, ?)",
                ("8Ә", day_idx, num, name),
            )
    conn.commit()


def get_setting(key: str, default: str = "") -> str:
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def generate_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=length))
        cursor.execute("SELECT code FROM invite_codes WHERE code = ?", (code,))
        if not cursor.fetchone():
            return code


def create_invite_code(role: str, class_code: str, shift: int,
                       created_by: int, reusable: bool = False) -> str:
    code = generate_code()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """INSERT INTO invite_codes
           (code, role, class_code, shift, created_by, created_at, is_active, reusable, use_count)
           VALUES (?, ?, ?, ?, ?, ?, 1, ?, 0)""",
        (code, role, class_code, shift, created_by, now, int(reusable)),
    )
    conn.commit()
    return code


def use_invite_code(code: str, tg_id: int) -> dict | None:
    cursor.execute(
        "SELECT * FROM invite_codes WHERE code = ? AND is_active = 1",
        (code,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    data = dict(row)
    if data["reusable"]:
        cursor.execute(
            "UPDATE invite_codes SET use_count = use_count + 1 WHERE code = ?",
            (code,),
        )
    else:
        cursor.execute(
            "UPDATE invite_codes SET use_count = 1, is_active = 0 WHERE code = ?",
            (code,),
        )
    conn.commit()
    return data


def get_codes_by_creator(created_by: int):
    cursor.execute(
        "SELECT * FROM invite_codes WHERE created_by = ? ORDER BY created_at DESC",
        (created_by,),
    )
    return [dict(r) for r in cursor.fetchall()]


def get_active_codes_by_creator(created_by: int):
    cursor.execute(
        "SELECT * FROM invite_codes WHERE created_by = ? AND is_active = 1 ORDER BY created_at DESC",
        (created_by,),
    )
    return [dict(r) for r in cursor.fetchall()]


def add_user(tg_id: int, full_name: str, role: str, lang: str,
             class_code: str = None, shift: int = 1, platform: str = "telegram") -> dict:
    trial_end = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    cursor.execute(
        """INSERT OR REPLACE INTO users
           (tg_id, full_name, role, lang, class_code, shift, sub_end_date, platform)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (tg_id, full_name, role, lang, class_code, shift, trial_end, platform),
    )
    conn.commit()
    return get_user(tg_id)


def delete_user(tg_id: int):
    cursor.execute("DELETE FROM users WHERE tg_id = ?", (tg_id,))
    conn.commit()

def get_user(tg_id: int):
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def is_subscription_active(tg_id: int) -> bool:
    user = get_user(tg_id)
    if not user or not user["sub_end_date"]:
        return False
    end = datetime.strptime(user["sub_end_date"], "%Y-%m-%d").date()
    return end >= datetime.now().date()


def extend_subscription(tg_id: int, days: int = 30):
    user = get_user(tg_id)
    if not user:
        return
    current_end = datetime.strptime(user["sub_end_date"], "%Y-%m-%d")
    if current_end.date() < datetime.now().date():
        current_end = datetime.now()
    new_end = (current_end + timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute(
        "UPDATE users SET sub_end_date = ? WHERE tg_id = ?",
        (new_end, tg_id),
    )
    conn.commit()


def get_active_users(shift: int = None):
    today = datetime.now().strftime("%Y-%m-%d")
    if shift:
        cursor.execute(
            "SELECT * FROM users WHERE sub_end_date >= ? AND shift = ?",
            (today, shift),
        )
    else:
        cursor.execute(
            "SELECT * FROM users WHERE sub_end_date >= ?",
            (today,),
        )
    return [dict(r) for r in cursor.fetchall()]


def get_all_users():
    cursor.execute("SELECT * FROM users")
    return [dict(r) for r in cursor.fetchall()]


def get_users_by_class(class_code: str):
    cursor.execute(
        "SELECT * FROM users WHERE class_code = ?",
        (class_code,),
    )
    return [dict(r) for r in cursor.fetchall()]


def add_class(class_code: str, class_name: str, shift: int):
    cursor.execute(
        "INSERT OR REPLACE INTO classes (class_code, class_name, shift) VALUES (?, ?, ?)",
        (class_code, class_name, shift),
    )
    conn.commit()


def get_class(class_code: str):
    cursor.execute("SELECT * FROM classes WHERE class_code = ?", (class_code,))
    row = cursor.fetchone()
    return dict(row) if row else None


def add_lesson(class_code: str, day_idx: int, lesson_num: int, lesson_name: str):
    cursor.execute(
        "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (?, ?, ?, ?)",
        (class_code, day_idx, lesson_num, lesson_name),
    )
    conn.commit()


def get_lessons(class_code: str, day_idx: int):
    cursor.execute(
        "SELECT * FROM lessons WHERE class_code = ? AND day_idx = ? ORDER BY lesson_num",
        (class_code, day_idx),
    )
    return [dict(r) for r in cursor.fetchall()]


def delete_lessons(class_code: str, day_idx: int):
    cursor.execute(
        "DELETE FROM lessons WHERE class_code = ? AND day_idx = ?",
        (class_code, day_idx),
    )
    conn.commit()


def add_lesson(class_code: str, day_idx: int, lesson_num: int, lesson_name: str):
    cursor.execute(
        "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (?, ?, ?, ?)",
        (class_code, day_idx, lesson_num, lesson_name),
    )
    conn.commit()

def update_user_lang(tg_id: int, lang: str):
    cursor.execute("UPDATE users SET lang = ? WHERE tg_id = ?", (lang, tg_id))
    conn.commit()

import re
def format_class(class_code: str) -> str:
    if not class_code:
        return "—"
    match = re.match(r"^(\d+)\s*([A-Za-zА-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөНн]+)$", str(class_code).strip())
    if match:
        return f'{match.group(1)} "{match.group(2).upper()}"'
    return str(class_code)
