import subprocess
import sys
import time
import threading
import os

def run_bot(script_name):
    while True:
        print(f"[{script_name}] Запуск...")
        try:
            # Запуск скрипта
            process = subprocess.Popen([sys.executable, script_name])
            process.wait()
            
            print(f"[{script_name}] Бот остановился с кодом {process.returncode}. Перезапуск через 5 секунд...")
        except Exception as e:
            print(f"[{script_name}] Критическая ошибка запуска: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_tg = os.getenv("RUN_TELEGRAM_BOT", "1") != "0"
    run_wa = os.getenv("RUN_WHATSAPP_BOT", "1") != "0"

    print("=== ЗАПУСК МЕНЕДЖЕРА БОТОВ ===")
    print("TG:", "ON" if run_tg else "OFF", "| WA:", "ON" if run_wa else "OFF")
    if not run_tg and not run_wa:
        print("Оба бота отключены (RUN_TELEGRAM_BOT=0 и RUN_WHATSAPP_BOT=0).")
        sys.exit(1)

    threads = []
    if run_tg:
        t_tg = threading.Thread(target=run_bot, args=("main.py",), daemon=True)
        threads.append(t_tg)
    if run_wa:
        t_wa = threading.Thread(target=run_bot, args=("whatsapp_bot.py",), daemon=True)
        threads.append(t_wa)

    for t in threads:
        t.start()
    
    # Вечный цикл, чтобы главный скрипт app.py не завершился
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n=== ОСТАНОВКА БОТОВ ===")
