import subprocess
import sys
import time
import threading

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
    print("=== ЗАПУСК МЕНЕДЖЕРА БОТОВ ===")
    print("Этот скрипт запускает сразу и Telegram-бота (main.py) и WhatsApp-бота (whatsapp_bot.py)")
    
    # Создаем потоки для одновременного запуска
    t_tg = threading.Thread(target=run_bot, args=("main.py",))
    t_wa = threading.Thread(target=run_bot, args=("whatsapp_bot.py",))
    
    # Помечаем как daemon, чтобы они завершились при выключении контейнера
    t_tg.daemon = True
    t_wa.daemon = True
    
    t_tg.start()
    t_wa.start()
    
    # Вечный цикл, чтобы главный скрипт app.py не завершился
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n=== ОСТАНОВКА БОТОВ ===")
