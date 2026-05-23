import config
import pymysql
import pymysql.cursors
import sqlite3
import string
import random
from contextlib import contextmanager
from datetime import datetime, timedelta
import os
import re
from queue import Queue, Empty
from cachetools import TTLCache

# Автоматически используем SQLite, если включен USE_SQLITE или не заданы MySQL учетные данные.
USE_SQLITE = os.getenv("USE_SQLITE", "1").lower() in ["1", "true"]

def _require_env(name: str) -> str:
    """Fail-fast: если обязательной переменной окружения нет — сразу падаем."""
    value = os.getenv(name)
    if not value:
        if USE_SQLITE and name in ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]:
            return ""
        raise RuntimeError(
            f"Environment variable {name!r} is required. "
            f"Добавь её в .env (см. .env.example)."
        )
    return value


DB_HOST = _require_env("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306")) if os.getenv("DB_PORT") else 3306
DB_USER = _require_env("DB_USER")
DB_PASSWORD = _require_env("DB_PASSWORD")
DB_NAME = _require_env("DB_NAME")


# ── SQLite Adapter for drop-in replacement ──

def mysql_to_sqlite(sql: str) -> str:
    # 1. Заменяем плейсхолдер %s на ?
    sql = sql.replace("%s", "?")
    
    # 2. Заменяем INSERT IGNORE на INSERT OR IGNORE
    sql = re.sub(r"INSERT\s+IGNORE", "INSERT OR IGNORE", sql, flags=re.IGNORECASE)
    
    # 3. Удаляем конструкции CHARACTER SET и COLLATE
    sql = re.sub(r"CHARACTER\s+SET\s+\w+", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"COLLATE\s+[\w_]+", "", sql, flags=re.IGNORECASE)
    
    # 4. Заменяем AUTO_INCREMENT на AUTOINCREMENT
    sql = re.sub(r"user_id\s+INT\s+PRIMARY\s+KEY\s+AUTO_INCREMENT", 
                 "user_id INTEGER PRIMARY KEY AUTOINCREMENT", sql, flags=re.IGNORECASE)
    
    # 5. Заменяем UNIQUE KEY ... на UNIQUE (...)
    sql = re.sub(r"UNIQUE\s+KEY\s+\w+\s*\(([^)]+)\)", r"UNIQUE (\1)", sql, flags=re.IGNORECASE)
    
    # 6. Заменяем ENUM(...) на TEXT (так как SQLite не поддерживает ENUM)
    sql = re.sub(r"ENUM\s*\([^)]+\)", "TEXT", sql, flags=re.IGNORECASE)
    
    return sql


class SQLiteCursor:
    def __init__(self, sqlite_cursor):
        self.cursor = sqlite_cursor

    def execute(self, query, params=None):
        translated_query = mysql_to_sqlite(query)
        if params is None:
            self.cursor.execute(translated_query)
        else:
            if not isinstance(params, (tuple, list)):
                params = (params,)
            self.cursor.execute(translated_query, params)
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def close(self):
        self.cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class SQLiteConnection:
    def __init__(self, db_path="school.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.isolation_level = None  # Режим autocommit
        self.open = True

    def cursor(self):
        return SQLiteCursor(self.conn.cursor())

    def ping(self, reconnect=True):
        pass

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()
        self.open = False


# ── Connection pool ──
_pool = Queue(maxsize=10)

def _create_conn():
    if USE_SQLITE:
        return SQLiteConnection("school.db")
    try:
        return pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True, connect_timeout=5,
            read_timeout=10, write_timeout=10,
        )
    except Exception as e:
        print(f"⚠️ Не удалось подключиться к удаленному MySQL ({e}). Автоматически откатываемся на локальную SQLite!")
        return SQLiteConnection("school.db")

def get_connection():
    """Get a connection from pool or create new."""
    try:
        conn = _pool.get_nowait()
        try:
            conn.ping(reconnect=True)
            return conn
        except Exception:
            try: conn.close()
            except: pass
    except Empty:
        pass
    return _create_conn()

def release_connection(conn):
    """Return connection to pool for reuse."""
    if conn is None:
        return
    try:
        if conn.open:
            _pool.put_nowait(conn)
        else:
            conn.close()
    except Exception:
        try: conn.close()
        except: pass


@contextmanager
def pooled_connection():
    """Context manager that properly returns connection to pool."""
    conn = get_connection()
    try:
        yield conn
    finally:
        release_connection(conn)



# ── In-process caches ──
_user_cache = TTLCache(maxsize=5000, ttl=60)
_settings_cache = TTLCache(maxsize=100, ttl=120)
_lessons_cache = TTLCache(maxsize=2000, ttl=300)
_all_users_cache = TTLCache(maxsize=1, ttl=30)  # scheduler calls every minute, cache 30s


def invalidate_user_cache(tg_id: int):
    _user_cache.pop(tg_id, None)


def invalidate_lessons_cache(class_code: str | None = None):
    if class_code is None:
        _lessons_cache.clear()
    else:
        norm = normalize_class_code(class_code)
        to_remove = [k for k in _lessons_cache if k[0] == norm]
        for k in to_remove:
            _lessons_cache.pop(k, None)


def invalidate_settings_cache():
    _settings_cache.clear()


def normalize_class_code(class_code: str | None) -> str | None:
    if class_code is None:
        return None
    cleaned = re.sub(r'[\s"\']+', "", str(class_code)).upper()
    return cleaned or None


def _normalized_class_sql(column_name: str = "class_code") -> str:
    return f"REPLACE(REPLACE(REPLACE(UPPER({column_name}), ' ', ''), '\"', ''), \"'\", '')"

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
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            for q in queries:
                cursor.execute(q)
            cursor.execute(
                "INSERT IGNORE INTO settings (`key`, `value`) VALUES ('bell_mode', 'standard')"
            )
    seed_demo_data()


def seed_demo_data():
    with pooled_connection() as conn:
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
    if key in _settings_cache:
        return _settings_cache[key]
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT `value` FROM settings WHERE `key` = %s", (key,))
            row = cursor.fetchone()
            val = row["value"] if row else default
            _settings_cache[key] = val
            return val


def set_setting(key: str, value: str):
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "REPLACE INTO settings (`key`, `value`) VALUES (%s, %s)",
                (key, value),
            )
    _settings_cache[key] = value


def get_user_setting(tg_id: int, key: str, default: str = "on") -> str:
    with pooled_connection() as conn:
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
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, tuple(uniq_ids + uniq_keys))
            for row in cursor.fetchall():
                uid = row["tg_id"]
                if uid not in result:
                    result[uid] = {}
                result[uid][row["setting_key"]] = row["setting_value"]
    return result


def set_user_setting(tg_id: int, key: str, value: str):
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "REPLACE INTO user_settings (tg_id, setting_key, setting_value) VALUES (%s, %s, %s)",
                (tg_id, key, value),
            )


def generate_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    for _ in range(100):
        code = "".join(random.choices(chars, k=length))
        with pooled_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT code FROM invite_codes WHERE code = %s", (code,))
                if not cursor.fetchone():
                    return code
    raise RuntimeError("Failed to generate unique invite code after 100 attempts")


def create_invite_code(role: str, class_code: str, shift: int,
                       created_by: int, reusable: bool = False) -> str:
    code = generate_code()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO invite_codes
                   (code, role, class_code, shift, created_by, created_at, is_active, reusable, use_count)
                   VALUES (%s, %s, %s, %s, %s, %s, 1, %s, 0)""",
                (code, role, normalized_class_code, shift, created_by, now, int(reusable)),
            )
    return code


def validate_invite_code(code: str) -> dict | None:
    """Check if invite code is valid without consuming it."""
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM invite_codes WHERE code = %s AND is_active = 1",
                (code,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            row["class_code"] = normalize_class_code(row.get("class_code"))
            return row


def use_invite_code(code: str, tg_id: int) -> dict | None:
    with pooled_connection() as conn:
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
            row["class_code"] = normalize_class_code(row.get("class_code"))
            return row


def get_codes_by_creator(created_by: int):
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM invite_codes WHERE created_by = %s ORDER BY created_at DESC",
                (created_by,),
            )
            return cursor.fetchall()


def get_active_codes_by_creator(created_by: int):
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM invite_codes WHERE created_by = %s AND is_active = 1 ORDER BY created_at DESC",
                (created_by,),
            )
            return cursor.fetchall()


def add_user(tg_id: int, full_name: str, role: str, lang: str,
             class_code: str = None, shift: int = 1, platform: str = "telegram") -> dict:
    trial_end = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """REPLACE INTO users
                   (tg_id, full_name, role, lang, class_code, shift, sub_end_date, platform)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (tg_id, full_name, role, lang, normalized_class_code, shift, trial_end, platform),
            )
    invalidate_user_cache(tg_id)
    _all_users_cache.pop("all", None)
    return get_user(tg_id)


def delete_user(tg_id: int):
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE tg_id = %s", (tg_id,))
    invalidate_user_cache(tg_id)
    _all_users_cache.pop("all", None)


def get_user(tg_id: int):
    if tg_id in _user_cache:
        return _user_cache[tg_id]
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE tg_id = %s", (tg_id,))
            user = cursor.fetchone()
            if user:
                _user_cache[tg_id] = user
            return user


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
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET sub_end_date = %s WHERE tg_id = %s",
                (new_end, tg_id),
            )
    invalidate_user_cache(tg_id)


def get_active_users(shift: int = None):
    today = datetime.now().strftime("%Y-%m-%d")
    with pooled_connection() as conn:
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
    cached = _all_users_cache.get("all")
    if cached is not None:
        return cached
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            result = cursor.fetchall()
    _all_users_cache["all"] = result
    return result


def get_users_by_class(class_code: str):
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM users WHERE {_normalized_class_sql('class_code')} = %s",
                (normalized_class_code,),
            )
            return cursor.fetchall()


def add_class(class_code: str, class_name: str, shift: int):
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "REPLACE INTO classes (class_code, class_name, shift) VALUES (%s, %s, %s)",
                (normalized_class_code, class_name, shift),
            )


def get_class(class_code: str):
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM classes WHERE class_code = %s", (normalized_class_code,))
            row = cursor.fetchone()
            if row:
                return row
            cursor.execute(
                f"SELECT * FROM classes WHERE {_normalized_class_sql('class_code')} = %s LIMIT 1",
                (normalized_class_code,),
            )
            return cursor.fetchone()

def get_all_classes():
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT class_code FROM classes ORDER BY class_code ASC")
            classes = []
            seen = set()
            for row in cursor.fetchall():
                normalized = normalize_class_code(row["class_code"])
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    classes.append(normalized)
            return classes


def delete_lessons(class_code: str, day_idx: int):
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM lessons WHERE {_normalized_class_sql('class_code')} = %s AND day_idx = %s",
                (normalized_class_code, day_idx),
            )
    invalidate_lessons_cache(class_code)

def delete_single_lesson(class_code: str, day_idx: int, lesson_num: int):
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM lessons WHERE {_normalized_class_sql('class_code')} = %s AND day_idx = %s AND lesson_num = %s",
                (normalized_class_code, day_idx, lesson_num),
            )
    invalidate_lessons_cache(class_code)


def add_lesson(class_code: str, day_idx: int, lesson_num: int, lesson_name: str):
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                (normalized_class_code, day_idx, lesson_num, lesson_name),
            )
    invalidate_lessons_cache(class_code)

def set_weekly_schedule(class_code: str, schedule: dict):
    # schedule format: {0: ["Math", "Physics"], 1: ["History", "PE", "Chemistry"]}
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM lessons WHERE {_normalized_class_sql('class_code')} = %s",
                (normalized_class_code,),
            )
            for day_idx, lessons in schedule.items():
                for num, name in enumerate(lessons, 1):
                    cursor.execute(
                        "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                        (normalized_class_code, day_idx, num, str(name).strip())
                    )
    invalidate_lessons_cache(class_code)

def update_single_lesson(class_code: str, day_idx: int, lesson_num: int, lesson_name: str):
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM lessons WHERE {_normalized_class_sql('class_code')} = %s AND day_idx = %s AND lesson_num = %s",
                (normalized_class_code, day_idx, lesson_num),
            )
            cursor.execute(
                "INSERT INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
                (normalized_class_code, day_idx, lesson_num, lesson_name),
            )
    invalidate_lessons_cache(class_code)


def get_lessons(class_code: str, day_idx: int):
    normalized_class_code = normalize_class_code(class_code)
    cache_key = (normalized_class_code, day_idx)
    if cache_key in _lessons_cache:
        return _lessons_cache[cache_key]
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM lessons WHERE class_code = %s AND day_idx = %s ORDER BY lesson_num",
                (normalized_class_code, day_idx),
            )
            rows = cursor.fetchall()
            if rows:
                _lessons_cache[cache_key] = rows
                return rows
            cursor.execute(
                f"""
                SELECT lesson_num, MAX(lesson_name) AS lesson_name
                FROM lessons
                WHERE {_normalized_class_sql('class_code')} = %s AND day_idx = %s
                GROUP BY lesson_num
                ORDER BY lesson_num
                """,
                (normalized_class_code, day_idx),
            )
            result = cursor.fetchall()
            _lessons_cache[cache_key] = result
            return result


def get_weekly_lessons(class_code: str):
    """Выгружает расписание на всю неделю за ОДИН запрос к БД (высокая оптимизация)."""
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT day_idx, lesson_num, lesson_name FROM lessons WHERE class_code = %s ORDER BY day_idx, lesson_num",
                (normalized_class_code,)
            )
            rows = cursor.fetchall()
            if rows:
                return rows
            
            cursor.execute(
                f"""
                SELECT day_idx, lesson_num, MAX(lesson_name) AS lesson_name
                FROM lessons
                WHERE {_normalized_class_sql('class_code')} = %s
                GROUP BY day_idx, lesson_num
                ORDER BY day_idx, lesson_num
                """,
                (normalized_class_code,)
            )
            return cursor.fetchall()

def get_all_subjects():
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT lesson_name FROM lessons WHERE lesson_name != '' AND lesson_name IS NOT NULL ORDER BY lesson_name LIMIT 50"
            )
            return [row["lesson_name"] for row in cursor.fetchall()]


def get_class_subjects(class_code: str):
    normalized_class_code = normalize_class_code(class_code)
    with pooled_connection() as conn:
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
                (normalized_class_code,),
            )
            subjects = [row["lesson_name"] for row in cursor.fetchall()]
            if subjects:
                return subjects
            cursor.execute(
                f"""
                SELECT DISTINCT lesson_name
                FROM lessons
                WHERE {_normalized_class_sql('class_code')} = %s
                  AND lesson_name != ''
                  AND lesson_name IS NOT NULL
                ORDER BY lesson_name
                """,
                (normalized_class_code,),
            )
            return [row["lesson_name"] for row in cursor.fetchall()]


def update_user_lang(tg_id: int, lang: str):
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET lang = %s WHERE tg_id = %s", (lang, tg_id))
    invalidate_user_cache(tg_id)


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
    with pooled_connection() as conn:
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
    ALLOWED_TABLES = {"users", "classes", "lessons", "invite_codes", "settings"}
    backup = {}
    with pooled_connection() as conn:
        with conn.cursor() as cursor:
            for table in ALLOWED_TABLES:
                cursor.execute(f"SELECT * FROM `{table}`")
                backup[table] = cursor.fetchall()
    return backup
