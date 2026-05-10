"""Супервайзер: запускает main.py (Telegram) и whatsapp_bot.py с авто-рестартом."""
import logging
import os
import subprocess
import sys
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("supervisor")

RESTART_DELAY_SEC = 5


def run_bot(script_name: str) -> None:
    """Запускает скрипт и автоматически перезапускает его после остановки."""
    while True:
        logger.info("[%s] Запуск...", script_name)
        try:
            process = subprocess.Popen([sys.executable, script_name])
            process.wait()
            logger.warning(
                "[%s] Бот остановился с кодом %s. Перезапуск через %s сек...",
                script_name, process.returncode, RESTART_DELAY_SEC,
            )
        except Exception as e:
            logger.exception("[%s] Критическая ошибка запуска: %s", script_name, e)
        time.sleep(RESTART_DELAY_SEC)


def main() -> None:
    run_tg = os.getenv("RUN_TELEGRAM_BOT", "1") != "0"
    run_wa = os.getenv("RUN_WHATSAPP_BOT", "1") != "0"

    logger.info("=== ЗАПУСК МЕНЕДЖЕРА БОТОВ ===")
    logger.info("TG: %s | WA: %s", "ON" if run_tg else "OFF", "ON" if run_wa else "OFF")

    if not run_tg and not run_wa:
        logger.error("Оба бота отключены (RUN_TELEGRAM_BOT=0 и RUN_WHATSAPP_BOT=0).")
        sys.exit(1)

    threads: list[threading.Thread] = []
    if run_tg:
        threads.append(threading.Thread(target=run_bot, args=("main.py",), daemon=True))
    if run_wa:
        threads.append(threading.Thread(target=run_bot, args=("whatsapp_bot.py",), daemon=True))

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("=== ОСТАНОВКА БОТОВ ===")


if __name__ == "__main__":
    main()
