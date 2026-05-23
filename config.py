"""
🎒 CONFIGURATION FILE FOR SCHOOL BOT SYSTEM (config.py)
Вы можете редактировать все настройки здесь напрямую в Python-формате вместо файла .env.
"""

import os

# ── 1. Запуск компонентов супервайзером (app.py) ──
RUN_API = True               # Запускать REST API веб-сервер (True / False)
RUN_TELEGRAM_BOT = True      # Запускать Telegram-бота (True / False)
RUN_WHATSAPP_BOT = False     # Запускать WhatsApp-бота (True / False) -> ВЫКЛЮЧЕН ПО ЗАПРОСУ

# ── 2. Настройки REST API сервера (FastAPI) ──
# Здесь вы можете прописать IP-адрес и порт вашего хостинга (например, 65.108.73.224:48095)
API_HOST = "65.108.73.224"   # IP-адрес для запуска API (0.0.0.0 для локального прослушивания)
API_PORT = 48095             # Порт для запуска API

# ── 3. Настройки Telegram-бота ──
BOT_TOKEN = "8794322225:AAHTKOzspazl1zMdu32RGxLkvXMF2RkSOak"
BOT_USERNAME = "SchoolUshtobeBot"
ADMIN_ID = 7903470823

# ── 4. Настройки WhatsApp Green API (если потребуется) ──
ID_INSTANCE = "7103531121"
API_TOKEN_INSTANCE = "5261f6ef2e8b4dd98d010a3f039ff95f0b2a08a7cadb46b2a7"

# ── 5. База данных (MySQL / SQLite Fallback) ──
USE_SQLITE = True             # True - использовать локальную БД SQLite (school.db) для надежной работы!

DB_HOST = "d1.qwertyx.host"
DB_PORT = 3306
DB_USER = "u21556_wFWgwZ6dwb"
DB_PASSWORD = "kpbWPrSqj.Ac1X^C98L4@LB!"
DB_NAME = "s21556_School"

# ── 6. Git автоматизация ──
GIT_BRANCH = "main"


# ==============================================================================
# 🚨 СИСТЕМНЫЙ ЭКСПОРТ (Не редактировать)
# Автоматически переносим настройки в os.environ для 100% совместимости с кодом проекта
# ==============================================================================
for key, value in list(globals().items()):
    if not key.startswith("__") and key not in ["os", "list", "globals"]:
        if isinstance(value, bool):
            os.environ[key] = "1" if value else "0"
        else:
            os.environ[key] = str(value)
