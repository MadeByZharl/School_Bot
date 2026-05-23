import json
import pymysql
import pymysql.cursors

# Подключение к новому MySQL серверу из скриншота
DB_HOST = "65.108.73.224"
DB_PORT = 3306
DB_USER = "u1796_MBWhHo8lSF"
DB_PASSWORD = "ITBJKIvgQ+37jfM!jpB+LP^x"
DB_NAME = "s1796_Schoolbot"

print(f"🔗 Подключение к базе данных {DB_NAME} на {DB_HOST}:{DB_PORT}...")

conn = pymysql.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True
)

cursor = conn.cursor()

# 1. Создание таблиц (схема MySQL)
print("🛠️ Создание таблиц в базе данных...")

queries = [
    """
    CREATE TABLE IF NOT EXISTS classes (
        class_code VARCHAR(50) PRIMARY KEY,
        class_name VARCHAR(255) NOT NULL,
        shift INT NOT NULL
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """,
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
        platform VARCHAR(50) DEFAULT 'telegram',
        FOREIGN KEY (class_code) REFERENCES classes(class_code) ON DELETE SET NULL
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS lessons (
        class_code VARCHAR(50) NOT NULL,
        day_idx INT NOT NULL,
        lesson_num INT NOT NULL,
        lesson_name VARCHAR(255) NOT NULL,
        FOREIGN KEY (class_code) REFERENCES classes(class_code) ON DELETE CASCADE,
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
        use_count INT DEFAULT 0,
        FOREIGN KEY (class_code) REFERENCES classes(class_code) ON DELETE SET NULL
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
    """
]

for q in queries:
    cursor.execute(q)

print("✅ Все таблицы успешно созданы/проверены!")

# 2. Загрузка бэкапа из backup.json
print("📖 Загрузка JSON-бэкапа из файла...")
with open("/Users/user/Documents/minecraft-plugins/school_bot/scratch/backup.json", "r", encoding="utf-8") as f:
    backup = json.load(f)

# 3. Восстановление данных
# Восстанавливаем classes
classes = backup.get("classes", [])
print(f"📦 Восстановление классов ({len(classes)})...")
for c in classes:
    cursor.execute(
        "REPLACE INTO classes (class_code, class_name, shift) VALUES (%s, %s, %s)",
        (c["class_code"], c["class_name"], c["shift"])
    )

# Восстанавливаем lessons
lessons = backup.get("lessons", [])
print(f"📦 Восстановление расписания уроков ({len(lessons)})...")
for l in lessons:
    cursor.execute(
        "REPLACE INTO lessons (class_code, day_idx, lesson_num, lesson_name) VALUES (%s, %s, %s, %s)",
        (l["class_code"], l["day_idx"], l["lesson_num"], l["lesson_name"])
    )

# Восстанавливаем settings
settings = backup.get("settings", [])
print(f"📦 Восстановление общих настроек ({len(settings)})...")
for s in settings:
    cursor.execute(
        "REPLACE INTO settings (`key`, `value`) VALUES (%s, %s)",
        (s["key"], s["value"])
    )

# Восстанавливаем invite_codes
invite_codes = backup.get("invite_codes", [])
print(f"📦 Восстановление кодов приглашений ({len(invite_codes)})...")
for code in invite_codes:
    cursor.execute(
        """REPLACE INTO invite_codes 
           (code, role, class_code, shift, created_by, created_at, is_active, reusable, use_count) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (code["code"], code["role"], code.get("class_code"), code.get("shift", 1), 
         code["created_by"], code["created_at"], code["is_active"], code["reusable"], code["use_count"])
    )

# Восстанавливаем users
users = backup.get("users", [])
print(f"📦 Восстановление пользователей ({len(users)})...")
for u in users:
    cursor.execute(
        """REPLACE INTO users 
           (user_id, tg_id, full_name, role, lang, class_code, shift, sub_end_date, platform) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (u["user_id"], u["tg_id"], u["full_name"], u["role"], u["lang"], 
         u.get("class_code"), u.get("shift", 1), u.get("sub_end_date"), u.get("platform", "telegram"))
    )

print("🎉 Восстановление данных успешно завершено!")
cursor.close()
conn.close()
