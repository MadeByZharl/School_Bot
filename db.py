import pymysql
import pymysql.cursors
import string
import random
from datetime import datetime, timedelta
import os
import re
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "db.msk.minerent.net")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "u21319_qwgUvpiitb")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "s21319_TgBot")

def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def init_db():
    queries = [
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INT PRIMARY KEY AUTO_INCREMENT,
            tg_id BIGINT UNIQUE NOT NULL,
            full_name VARCHAR(255) NOT NULL,
            role ENUM('student', 'teacher', 'zavuch') NOT NULL,
            lang ENUM('ru', 'kk') NOT NULL DEFAULT 'ru',
            class_code VARCHAR(50),
            shift INT DEFAULT 1,
            sub_end_date VARCHAR(20),
            platform VARCHAR(50) DEFAULT 'telegram'
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS classes (
            class_code VARCHAR(50) PRIMARY KEY,
            class_name VARCHAR(255) NOT NULL,
            shift INT NOT NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS lessons (
            class_code VARCHAR(50) NOT NULL,
            day_idx INT NOT NULL,
            lesson_num INT NOT NULL,
            lesson_name VARCHAR(255) NOT NULL,
            FOREIGN KEY (class_code) REFERENCES classes(class_code),
            UNIQUE KEY unique_lesson (class_code, day_idx, lesson_num)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS invite_codes (
            code VARCHAR(50) PRIMARY KEY,
            role ENUM('student', 'teacher', 'zavuch') NOT NULL,
            class_code VARCHAR(50),
            shift INT DEFAULT 1,
            created_by BIGINT NOT NULL,
            created_at VARCHAR(50) NOT NULL,
            is_active TINYINT(1) DEFAULT 1,
            reusable TINYINT(1) DEFAULT 0,
            use_count INT DEFAULT 0
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS settings (
            `key` VARCHAR(50) PRIMARY KEY,
            `value` VARCHAR(255) NOT NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            tg_id BIGINT NOT NULL,
            setting_key VARCHAR(50) NOT NULL,
            setting_value VARCHAR(50) NOT NULL DEFAULT 'on',
            PRIMARY KEY (tg_id, setting_key)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """,
    ]
    with get_connection() as conn:
        with conn.cursor() as cursor:
            for q in queries:
                cursor.execute(q)
            cursor.execute(
                "INSERT IGNORE INTO settings (`key`, `value`) VALUES ('bell_mode', 'standard')"
            )
    seed_demo_data()


def seed_demo_data():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT IGNORE INTO classes (class_code, class_name, shift) VALUES (%s, %s, %s)",
                ("8Ә", "8 Ә", 1),
            )
            schedule = {
                0: [  # Понедельник
                    "Сынып сағаты", "Алгебра", "Қазақ тілі", "Химия",
                    "Орыс тілі мен әдебиеті", "Шетіл тілі", "Қазақстан тарихы", "Жаһандық құзыреттілік",
                ],
                1: [  # Вторник
                    "Химия", "Орыс тілі мен әдебиеті", "Информатика", "Қазақ әдебиеті",
                    "Алгебра", "Дүние жүзі тарихы", "География",
                ],
                2: [  # Среда
                    "Алгебра", "Қазақстан тарихы", "Қазақ әдебиеті", "Физика",
                    "Шетіл тілі", "Орыс тілі мен әдебиеті", "Дене шынықтыру",
                ],
                3: [  # Четверг
                    "Дене шынықтыру", "Қазақ тілі", "Шетіл тілі", "Биология",
                    "Геометрия", "Көркем еңбек",
                ],
                4: [  # Пятница
                    "Биология", "География", "Қазақ әдебиеті", "Геометрия",
                    "Физика", "Дене шынықтыру",
                ],
            }
            for day_idx, lessons in schedule.items():
                for num, name in enumerate(lessons, 1):
                    cursor.execute(
                        "INSERT IGNORE INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                        ("8Ә", day_idx, num, name),
                    )


def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT `value` FROM settings WHERE `key` = %s", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "REPLACE INTO settings (`key`, `value`) VALUES (%s, %s)",
                (key, value),
            )


def get_user_setting(tg_id: int, key: str, default: str = "on") -> str:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT setting_value FROM user_settings WHERE tg_id = %s AND setting_key = %s",
                (tg_id, key),
            )
            row = cursor.fetchone()
            return row["setting_value"] if row else default


def get_user_settings_bulk(tg_ids: list[int], keys: list[str]) -> dict[int, dict[str, str]]:
    if not tg_ids or not keys:
        return {}

    # Remove duplicates while preserving order to keep query size compact.
    uniq_ids = list(dict.fromkeys(tg_ids))
    uniq_keys = list(dict.fromkeys(keys))

    id_placeholders = ", ".join(["%s"] * len(uniq_ids))
    key_placeholders = ", ".join(["%s"] * len(uniq_keys))
    query = (
        f"SELECT tg_id, setting_key, setting_value FROM user_settings "
        f"WHERE tg_id IN ({id_placeholders}) AND setting_key IN ({key_placeholders})"
    )

    result: dict[int, dict[str, str]] = {}
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, tuple(uniq_ids + uniq_keys))
            for row in cursor.fetchall():
                uid = row["tg_id"]
                if uid not in result:
                    result[uid] = {}
                result[uid][row["setting_key"]] = row["setting_value"]
    return result


def set_user_setting(tg_id: int, key: str, value: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "REPLACE INTO user_settings (tg_id, setting_key, setting_value) VALUES (%s, %s, %s)",
                (tg_id, key, value),
            )


def generate_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=length))
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT code FROM invite_codes WHERE code = %s", (code,))
                if not cursor.fetchone():
                    return code


def create_invite_code(role: str, class_code: str, shift: int,
                       created_by: int, reusable: bool = False) -> str:
    code = generate_code()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO invite_codes
                   (code, role, class_code, shift, created_by, created_at, is_active, reusable, use_count)
                   VALUES (%s, %s, %s, %s, %s, %s, 1, %s, 0)""",
                (code, role, class_code, shift, created_by, now, int(reusable)),
            )
    return code


def use_invite_code(code: str, tg_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM invite_codes WHERE code = %s AND is_active = 1",
                (code,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            if not row["reusable"]:
                cursor.execute(
                    "UPDATE invite_codes SET use_count = use_count + 1, is_active = 0 WHERE code = %s AND is_active = 1",
                    (code,),
                )
                if cursor.rowcount == 0:
                    return None
            else:
                cursor.execute(
                    "UPDATE invite_codes SET use_count = use_count + 1 WHERE code = %s AND is_active = 1",
                    (code,),
                )
                if cursor.rowcount == 0:
                    return None
            return row


def get_codes_by_creator(created_by: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM invite_codes WHERE created_by = %s ORDER BY created_at DESC",
                (created_by,),
            )
            return cursor.fetchall()


def get_active_codes_by_creator(created_by: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM invite_codes WHERE created_by = %s AND is_active = 1 ORDER BY created_at DESC",
                (created_by,),
            )
            return cursor.fetchall()


def add_user(tg_id: int, full_name: str, role: str, lang: str,
             class_code: str = None, shift: int = 1, platform: str = "telegram") -> dict:
    trial_end = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """REPLACE INTO users
                   (tg_id, full_name, role, lang, class_code, shift, sub_end_date, platform)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (tg_id, full_name, role, lang, class_code, shift, trial_end, platform),
            )
    return get_user(tg_id)


def delete_user(tg_id: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE tg_id = %s", (tg_id,))


def get_user(tg_id: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE tg_id = %s", (tg_id,))
            return cursor.fetchone()


def is_subscription_active(tg_id: int) -> bool:
    user = get_user(tg_id)
    if not user or not user.get("sub_end_date"):
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
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET sub_end_date = %s WHERE tg_id = %s",
                (new_end, tg_id),
            )


def get_active_users(shift: int = None):
    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        with conn.cursor() as cursor:
            if shift:
                cursor.execute(
                    "SELECT * FROM users WHERE sub_end_date >= %s AND shift = %s",
                    (today, shift),
                )
            else:
                cursor.execute(
                    "SELECT * FROM users WHERE sub_end_date >= %s",
                    (today,),
                )
            return cursor.fetchall()


def get_all_users():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            return cursor.fetchall()


def get_users_by_class(class_code: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE class_code = %s",
                (class_code,),
            )
            return cursor.fetchall()


def add_class(class_code: str, class_name: str, shift: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "REPLACE INTO classes (class_code, class_name, shift) VALUES (%s, %s, %s)",
                (class_code, class_name, shift),
            )


def get_class(class_code: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM classes WHERE class_code = %s", (class_code,))
            return cursor.fetchone()

def get_all_classes():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT class_code FROM classes ORDER BY class_code ASC")
            return [row["class_code"] for row in cursor.fetchall()]


def delete_lessons(class_code: str, day_idx: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM lessons WHERE class_code = %s AND day_idx = %s",
                (class_code, day_idx),
            )

def delete_single_lesson(class_code: str, day_idx: int, lesson_num: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM lessons WHERE class_code = %s AND day_idx = %s AND lesson_num = %s",
                (class_code, day_idx, lesson_num),
            )


def add_lesson(class_code: str, day_idx: int, lesson_num: int, lesson_name: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                (class_code, day_idx, lesson_num, lesson_name),
            )

def set_weekly_schedule(class_code: str, schedule: dict):
    # schedule format: {0: ["Math", "Physics"], 1: ["History", "PE", "Chemistry"]}
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM lessons WHERE class_code = %s", (class_code,))
            for day_idx, lessons in schedule.items():
                for num, name in enumerate(lessons, 1):
                    cursor.execute(
                        "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                        (class_code, day_idx, num, str(name).strip())
                    )

def update_single_lesson(class_code: str, day_idx: int, lesson_num: int, lesson_name: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "REPLACE INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                (class_code, day_idx, lesson_num, lesson_name),
            )


def get_lessons(class_code: str, day_idx: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM lessons WHERE class_code = %s AND day_idx = %s ORDER BY lesson_num",
                (class_code, day_idx),
            )
            return cursor.fetchall()

def get_all_subjects():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT lesson_name FROM lessons WHERE lesson_name != '' AND lesson_name IS NOT NULL ORDER BY lesson_name LIMIT 50"
            )
            return [row["lesson_name"] for row in cursor.fetchall()]


def get_class_subjects(class_code: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT lesson_name
                FROM lessons
                WHERE class_code = %s
                  AND lesson_name != ''
                  AND lesson_name IS NOT NULL
                ORDER BY lesson_name
                """,
                (class_code,),
            )
            return [row["lesson_name"] for row in cursor.fetchall()]


def update_user_lang(tg_id: int, lang: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET lang = %s WHERE tg_id = %s", (lang, tg_id))


def format_class(class_code: str) -> str:
    if not class_code:
        return "—"
    
    # Check if the class is already saved with a space (e.g. "8 А" instead of "8А")
    match = re.match(r"^(\d+)\s*([A-Za-zА-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөНн]+)$", str(class_code).strip())
    if match:
        return f'{match.group(1)} "{match.group(2).upper()}"'
    return str(class_code)


def get_bot_stats():
    """Returns a dictionary with total users, count by role, and count by class."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Total users
            cursor.execute("SELECT COUNT(*) as total FROM users")
            total = cursor.fetchone()["total"]

            # By role
            cursor.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
            roles_raw = cursor.fetchall()
            roles = {"student": 0, "teacher": 0, "zavuch": 0}
            for r in roles_raw:
                roles[r["role"]] = r["count"]

            # By class
            cursor.execute("SELECT class_code, COUNT(*) as count FROM users WHERE role = 'student' AND class_code IS NOT NULL GROUP BY class_code")
            classes = cursor.fetchall()

            return {
                "total": total,
                "roles": roles,
                "classes": classes
            }

def get_full_backup() -> dict:
    """Exports all major tables to a dictionary for backup purposes."""
    backup = {}
    with get_connection() as conn:
        with conn.cursor() as cursor:
            tables = ["users", "classes", "lessons", "invite_codes", "settings"]
            for table in tables:
                cursor.execute(f"SELECT * FROM {table}")
                backup[table] = cursor.fetchall()
    return backup
