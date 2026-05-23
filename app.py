"""
🚀 СУПЕРВАЙЗЕР-ЗАПУСКАТЕЛЬ: Автоматически поднимает API-сервер, Telegram-бота и WhatsApp-бота.

Данный файл разработан с двойной совместимостью:
1. Запуск через python: `python app.py` запускает все три компонента параллельно с авто-рестартом.
2. Запуск через ASGI/IDX: Экспортирует объект `app` из api.py для бесшовной интеграции с сервером предпросмотра Google IDX.
"""

import config
import logging
import os
import subprocess
import sys
import threading
import time

# Настройка логирования для супервайзера
logging.basicConfig(
    level=logging.INFO,
    format="⚙️ %(asctime)s [%(levelname)s] supervisor: %(message)s",
)
logger = logging.getLogger("supervisor")

RESTART_DELAY_SEC = 5

def run_script(script_name: str) -> None:
    """Запускает скрипт и автоматически перезапускает его после непредвиденной остановки."""
    while True:
        logger.info(f"▶️ Запуск компонента: {script_name}...")
        try:
            # Запуск скрипта как отдельного подпроцесса
            process = subprocess.Popen([sys.executable, script_name])
            process.wait()
            logger.warning(
                f"⚠️ Компонент [{script_name}] завершил работу с кодом {process.returncode}. "
                f"Перезапуск через {RESTART_DELAY_SEC} секунд..."
            )
        except Exception as e:
            logger.exception(f"❌ Критическая ошибка запуска [{script_name}]: {e}")
        time.sleep(RESTART_DELAY_SEC)


def main() -> None:
    # Загружаем настройки запуска из переменных окружения (по умолчанию всё включено)
    run_api = os.getenv("RUN_API", "1") != "0"
    run_tg = os.getenv("RUN_TELEGRAM_BOT", "1") != "0"
    run_wa = os.getenv("RUN_WHATSAPP_BOT", "1") != "0"

    logger.info("=========================================")
    logger.info("🚀 ЗАПУСК ЕДИНОГО СУПЕРВАЙЗЕРА SCHOOL BOT")
    logger.info(
        f"API Server: {'✅ ON' if run_api else '❌ OFF'} | "
        f"Telegram Bot: {'✅ ON' if run_tg else '❌ OFF'} | "
        f"WhatsApp Bot: {'✅ ON' if run_wa else '❌ OFF'}"
    )
    logger.info("=========================================")

    if not run_api and not run_tg and not run_wa:
        logger.error("❌ Все компоненты отключены в .env (RUN_API, RUN_TELEGRAM_BOT, RUN_WHATSAPP_BOT).")
        sys.exit(1)

    threads: list[threading.Thread] = []

    # 1. Запуск FastAPI REST API
    if run_api:
        threads.append(threading.Thread(target=run_script, args=("api.py",), daemon=True))

    # 2. Запуск Telegram бота
    if run_tg:
        threads.append(threading.Thread(target=run_script, args=("main.py",), daemon=True))

    # 3. Запуск WhatsApp бота
    if run_wa:
        threads.append(threading.Thread(target=run_script, args=("whatsapp_bot.py",), daemon=True))

    # Стартуем все потоки
    for t in threads:
        t.start()

    # Удерживаем главный поток активным
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("=========================================")
        logger.info("🛑 ОСТАНОВКА ВСЕХ СЛУЖБ СУПЕРВАЙЗЕРОМ...")
        logger.info("=========================================")


# ── СОВМЕСТИМОСТЬ С ASGI / GOOGLE IDX ──
# Экспортируем 'app' напрямую из api.py. Если хостинг (или IDX) импортирует app.py 
# для запуска веб-сервера, он получит инстанс FastAPI и запустит его.
try:
    from api import app
except ImportError as e:
    logger.error("❌ Не удалось импортировать 'app' из api.py для ASGI-режима: %s", e)


if __name__ == "__main__":
    main()
