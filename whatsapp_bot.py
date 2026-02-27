import os
import re
import requests
from dotenv import load_dotenv
from whatsapp_api_client_python import API

# Подключаем общие модуцы
import db
from schedule_config import get_shifts, get_now_almaty, get_weekday_almaty
from translations import TEXTS, LESSON_TRANSLATIONS

load_dotenv()

ID_INSTANCE = os.getenv("ID_INSTANCE", "7103531121")
API_TOKEN_INSTANCE = os.getenv("API_TOKEN_INSTANCE", "5261f6ef2e8b4dd98d010a3f039ff95f0b2a08a7cadb46b2a7")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8794322225:AAHPZXDTCUWXueY77Dq0wTEdvyGRROb7Uqw")
import db
from schedule_config import get_shifts, get_now_almaty, get_weekday_almaty
from translations import TEXTS, LESSON_TRANSLATIONS

load_dotenv()

ID_INSTANCE = os.getenv("ID_INSTANCE", "7103531121")
API_TOKEN_INSTANCE = os.getenv("API_TOKEN_INSTANCE", "5261f6ef2e8b4dd98d010a3f039ff95f0b2a08a7cadb46b2a7")

greenAPI = API.GreenApi(ID_INSTANCE, API_TOKEN_INSTANCE)

def html_to_wa(text: str) -> str:
    """Конвертируем базовые HTML-теги из Telegram в markdown WhatsApp"""
    text = re.sub(r'<b>(.*?)</b>', r'*\1*', text)
    text = re.sub(r'<i>(.*?)</i>', r'_\1_', text)
    text = re.sub(r'<code>(.*?)</code>', r'\1', text)
    text = re.sub(r'<tg-spoiler>(.*?)</tg-spoiler>', r'\1', text)
    return text

def t(key: str, lang: str = "ru") -> str:
    lang = lang if lang in ("ru", "kk") else "ru"
    return html_to_wa(TEXTS.get(key, {}).get(lang, key))

def send_msg(wa_id: int, text: str):
    try:
        greenAPI.sending.sendMessage(f"{wa_id}@c.us", text)
    except Exception as e:
        print(f"Failed to send msg to {wa_id}: {e}")

def get_main_menu_text(lang: str, role: str) -> str:
    menu = []
    menu.append("1️⃣ " + t("menu_schedule", lang))
    menu.append("2️⃣ " + t("menu_profile", lang))
    if lang == "ru":
        menu.append("3️⃣ 🇰🇿 Сменить язык на Казахский")
    else:
        menu.append("3️⃣ 🇷🇺 Орыс тіліне ауысу")
    menu.append("4️⃣ " + t("menu_help", lang))
    menu.append("5️⃣ 🗓️ Расписание на неделю" if lang == "ru" else "5️⃣ 🗓️ Апталық кесте")
    if role in ("teacher", "zavuch"):
        menu.append("6️⃣ " + t("menu_gen_student_code", lang))
        menu.append("7️⃣ " + t("menu_my_codes", lang))
        if role == "zavuch":
            menu.append("8️⃣ " + t("menu_send_all", lang))
            menu.append("9️⃣ " + t("menu_edit_schedule", lang))
        else:
            menu.append("8️⃣ " + t("menu_send_class", lang))
    
    header = "🌟 *ГЛАВНОЕ МЕНЮ* 🌟\n" if lang == "ru" else "🌟 *БАСТЫ МӘЗІР* 🌟\n"
    footer = "\n👇 _Отправьте нужную цифру:_" if lang == "ru" else "\n👇 _Қажетті цифрды жіберіңіз:_"
    return header + "\n" + "\n".join(menu) + "\n" + footer

def handle_schedule(wa_id: int, user: dict):
    lang = user["lang"]
    bell_mode = db.get_setting("bell_mode", "standard")
    weekday = get_weekday_almaty()
    now_time = get_now_almaty()
    show_day = weekday
    is_tomorrow = False

    if weekday >= 6:
        show_day = 0
        is_tomorrow = True
    else:
        today_shifts = get_shifts(bell_mode, weekday)
        today_shift_data = today_shifts.get(user["shift"], {})
        
        last_end = "00:00"
        for times in today_shift_data.values():
            if times["end"] > last_end:
                last_end = times["end"]
                
        if now_time > last_end:
            if weekday == 4: show_day = 0
            elif weekday == 5: show_day = 0
            else: show_day = weekday + 1
            is_tomorrow = True

    day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"] if lang == "ru" else ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]
    day_name = day_names[show_day]
    lessons = db.get_lessons(user.get("class_code", ""), show_day)
    
    shifts = get_shifts(bell_mode, show_day)
    shift_data = shifts.get(user["shift"], {})
    if not lessons:
        send_msg(wa_id, t("no_lessons", lang))
        return
        
    lines = [f"📆 *{day_name}*\n"]
    for ls in lessons:
        num = ls["lesson_num"]
        time_info = shift_data.get(num, {})
        start = time_info.get("start", "—")
        end = time_info.get("end", "—")
        connector = "└" if ls == lessons[-1] else "├"
        
        lesson_name = ls["lesson_name"]
        if lang == "ru":
            lesson_name = LESSON_TRANSLATIONS.get(lesson_name, lesson_name)

        is_finished = (not is_tomorrow) and (end != "—") and (now_time > end)
        if is_finished:
            lines.append(f"{connector} {num}. ~*{lesson_name}*  ({start}–{end})~")
        else:
            lines.append(f"{connector} {num}. *{lesson_name}*  ({start}–{end})")
        
    mode_label = t(f"bell_{bell_mode}", lang)
    lines.append(f"\n_{mode_label}_")
    
    header_key = "schedule_tomorrow" if is_tomorrow else "schedule_today"
    text = t(header_key, lang).format(lessons="\n".join(lines))
    send_msg(wa_id, text)

def handle_weekly_schedule(wa_id: int, user: dict):
    lang = user["lang"]
    bell_mode = db.get_setting("bell_mode", "standard")
    
    day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"] if lang == "ru" else ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі"]
    all_lines = ["📅 *Расписание на неделю* / *Апталық кесте*\n"]
    has_any_lessons = False
    now_time = get_now_almaty()
    weekday = get_weekday_almaty()
    
    for day_idx in range(6):
        lessons = db.get_lessons(user.get("class_code", ""), day_idx)
        if not lessons: continue
            
        has_any_lessons = True
        shifts = get_shifts(bell_mode, day_idx)
        shift_data = shifts.get(user["shift"], {})
        
        all_lines.append(f"\n🔹 *{day_names[day_idx]}*")
        for ls in lessons:
            num = ls["lesson_num"]
            time_info = shift_data.get(num, {})
            start = time_info.get("start", "—")
            end = time_info.get("end", "—")
            
            lesson_name = ls["lesson_name"]
            if lang == "ru":
                lesson_name = LESSON_TRANSLATIONS.get(lesson_name, lesson_name)
                
            is_finished = (day_idx < weekday) or ((day_idx == weekday) and (end != "—") and (now_time > end))
            if is_finished:
                all_lines.append(f"~{num}. {lesson_name} ({start}–{end})~")
            else:
                all_lines.append(f"{num}. {lesson_name} ({start}–{end})")
            
    if not has_any_lessons:
        send_msg(wa_id, t("no_lessons", lang))
        return
        
    mode_label = t(f"bell_{bell_mode}", lang)
    all_lines.append(f"\n_{mode_label}_")
    send_msg(wa_id, "\n".join(all_lines))

# ---- STATES STORAGE (Very simple in-memory for WhatsApp) ----
FSM_DATA = {} # wa_id: {"state": str, "data": dict}

def process_message(wa_id: int, text: str):
    db.init_db()
    user = db.get_user(wa_id)
    text_ci = text.strip().lower()

    if text_ci in ("/logout", "выйти", "шығу"):
        db.delete_user(wa_id)
        if wa_id in FSM_DATA:
            del FSM_DATA[wa_id]
        msg_ru = "🚪 Вы вышли из аккаунта.\n\nНапишите любое сообщение, чтобы зарегистрироваться заново."
        msg_kk = "🚪 Сіз аккаунттан шықтыңыз.\n\nҚайта тіркелу үшін кез келген хабарлама жазыңыз."
        lang = user["lang"] if user else "ru"
        send_msg(wa_id, msg_ru if lang == "ru" else msg_kk)
        return

    if not user:
        # Not registered
        fsm = FSM_DATA.get(wa_id)
        if fsm and fsm.get("state") == "wait_lang":
            if text_ci in ("1", "ru", "русский"):
                lang = "ru"
            elif text_ci in ("2", "kk", "қазақша"):
                lang = "kk"
            else:
                send_msg(wa_id, "Пожалуйста, отправьте 1 или 2.\n1 (Русский)\n2 (Қазақша)")
                return
            
            FSM_DATA[wa_id]["state"] = "wait_name"
            FSM_DATA[wa_id]["data"]["lang"] = lang
            
            role = FSM_DATA[wa_id]["data"]["role"]
            class_code = db.format_class(FSM_DATA[wa_id]["data"].get("class_code", ""))
            send_msg(wa_id, t(f"code_accepted_{role}", lang).format(class_code=class_code))
            return
            
        elif fsm and fsm.get("state") == "wait_name":
            # Set name
            role = fsm["data"]["role"]
            class_code = fsm["data"]["class_code"]
            shift = fsm["data"]["shift"]
            lang = fsm["data"]["lang"]
            name = text.strip()
            
            # Very basic validation
            if len(name) < 2:
                send_msg(wa_id, "❌ " + t("registration_done", lang).replace("Ура!", "Ошибка:")) # Fallback error
                return
                
            db.add_user(wa_id, name, role, lang, class_code, shift, "whatsapp")
            user = db.get_user(wa_id)
            send_msg(wa_id, "🎉 " + t("registration_done", lang))
            send_msg(wa_id, get_main_menu_text(user["lang"], user["role"]))
            del FSM_DATA[wa_id]
            return
        # Maybe invite code?
        code_data = db.use_invite_code(text.upper(), wa_id)
        if code_data:
            FSM_DATA[wa_id] = {
                "state": "wait_lang",
                "data": {"role": code_data["role"], "class_code": code_data["class_code"], "shift": code_data["shift"]}
            }
            send_msg(wa_id, "Выберите язык / Тілді таңдаңыз:\n1. 🇷🇺 Русский\n2. 🇰🇿 Қазақша\n\n(Отправьте цифру / Цифрды жіберіңіз)")
            return

        send_msg(wa_id, t("welcome", "ru"))
        send_msg(wa_id, t("ask_invite_code", "ru"))
        return

    lang = user["lang"]
    
    fsm = FSM_DATA.get(wa_id)
    if fsm and fsm.get("state") == "wait_broadcast_text":
        if text_ci in ("отмена", "cancel", "болдырмау"):
            send_msg(wa_id, "🚫 " + ("Рассылка отменена." if lang == "ru" else "Рассылка тоқтатылды."))
            del FSM_DATA[wa_id]
            send_msg(wa_id, get_main_menu_text(lang, user["role"]))
            return
        
        text_to_send = text.strip()
        if user["role"] == "teacher" and user.get("class_code"):
            recipients = db.get_users_by_class(user["class_code"])
            template = TEXTS["broadcast_teacher"][lang]
            msg_text = template.format(name=user["full_name"], text=text_to_send)
        else:
            recipients = db.get_all_users()
            template = TEXTS["broadcast_admin"][lang]
            msg_text = template.format(text=text_to_send)
            
        count = 0
        errors = 0
        
        for u in recipients:
            platform = u.get("platform", "telegram")
            if platform == "whatsapp":
                try:
                    send_msg(u["tg_id"], html_to_wa(msg_text))
                    count += 1
                except Exception:
                    errors += 1
            else:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": u["tg_id"], "text": msg_text, "parse_mode": "HTML"},
                        timeout=5
                    )
                    count += 1
                except Exception:
                    errors += 1
        
        res_msg = t("broadcast_done", lang).format(count=count)
        if errors:
            res_msg += f"\n⚠️ Ошибок / Қате: {errors}"
        send_msg(wa_id, "✅ " + res_msg)
        del FSM_DATA[wa_id]
        send_msg(wa_id, get_main_menu_text(lang, user["role"]))
        return

    if fsm and fsm.get("state") == "edit_schedule_class":
        if text_ci in ("отмена", "cancel", "болдырмау"):
            send_msg(wa_id, "🚫 " + ("Отменено." if lang == "ru" else "Тоқтатылды."))
            del FSM_DATA[wa_id]
            send_msg(wa_id, get_main_menu_text(lang, user["role"]))
            return
            
        class_code = text.strip().upper()
        FSM_DATA[wa_id] = {
            "state": "edit_schedule_day",
            "class_code": class_code
        }
        
        roles_days_ru = "1. Понедельник\n2. Вторник\n3. Среда\n4. Четверг\n5. Пятница\n6. Суббота"
        roles_days_kk = "1. Дүйсенбі\n2. Сейсенбі\n3. Сәрсенбі\n4. Бейсенбі\n5. Жұма\n6. Сенбі"
        send_msg(wa_id, t("edit_schedule_ask_day", lang).format(class_code=class_code) + "\n\n" + (roles_days_ru if lang == "ru" else roles_days_kk) + "\n\n(отправьте цифру или слово)")
        return
        
    if fsm and fsm.get("state") == "edit_schedule_day":
        if text_ci in ("отмена", "cancel", "болдырмау"):
            send_msg(wa_id, "🚫 " + ("Отменено." if lang == "ru" else "Тоқтатылды."))
            del FSM_DATA[wa_id]
            send_msg(wa_id, get_main_menu_text(lang, user["role"]))
            return
            
        day_map = {
            "1": 0, "понедельник": 0, "дүйсенбі": 0,
            "2": 1, "вторник": 1, "сейсенбі": 1,
            "3": 2, "среда": 2, "сәрсенбі": 2,
            "4": 3, "четверг": 3, "бейсенбі": 3,
            "5": 4, "пятница": 4, "жұма": 4,
            "6": 5, "суббота": 5, "сенбі": 5,
        }
        
        day_idx = day_map.get(text_ci)
        if day_idx is None:
            send_msg(wa_id, "❌ Пожалуйста, отправьте цифру от 1 до 6.")
            return

        day_name = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"][day_idx]
        if lang == "kk":
            day_name = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі"][day_idx]
            
        FSM_DATA[wa_id] = {
            "state": "edit_schedule_text",
            "class_code": fsm["class_code"],
            "day_idx": day_idx,
            "day_name": day_name
        }
        
        send_msg(wa_id, t("edit_schedule_ask_text", lang).format(day_name=day_name, class_code=fsm["class_code"]))
        return
        
    if fsm and fsm.get("state") == "edit_schedule_text":
        if text_ci in ("отмена", "cancel", "болдырмау"):
            send_msg(wa_id, "🚫 " + ("Отменено." if lang == "ru" else "Тоқтатылды."))
            del FSM_DATA[wa_id]
            send_msg(wa_id, get_main_menu_text(lang, user["role"]))
            return
            
        class_code = fsm["class_code"]
        day_idx = fsm["day_idx"]
        day_name = fsm["day_name"]
        
        lessons_text = text.strip().split("\n")
        lessons = [l.strip() for l in lessons_text if l.strip()]
        
        db.delete_lessons(class_code, day_idx)
        formatted_schedule = ""
        for i, lesson in enumerate(lessons, 1):
            db.add_lesson(class_code, day_idx, i, lesson)
            formatted_schedule += f"{i}. {lesson}\n"
            
        send_msg(wa_id, t("edit_schedule_done", lang))
        del FSM_DATA[wa_id]
        send_msg(wa_id, get_main_menu_text(lang, user["role"]))
        
        recipients = db.get_users_by_class(class_code)
        for u in recipients:
            u_lang = u.get("lang", "ru")
            txt = t("edit_schedule_notify", u_lang).format(day_name=day_name, schedule=formatted_schedule)
            platform = u.get("platform", "telegram")
            if platform == "whatsapp":
                try:
                    send_msg(u["tg_id"], html_to_wa(txt))
                except Exception:
                    pass
            else:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": u["tg_id"], "text": txt, "parse_mode": "HTML"},
                        timeout=5
                    )
                except Exception:
                    pass
        return

    if text_ci in ("1", "расписание", "1. расписание", "кесте"):
        handle_schedule(wa_id, user)
        send_msg(wa_id, get_main_menu_text(user["lang"], user["role"]))
    elif text_ci in ("2", "профиль", "2. профиль"):
        role_key = f"role_{user['role']}"
        role_label = t(role_key, lang)
        msg_text = t("profile_card", lang).format(
            name=user["full_name"],
            role=role_label,
            class_code=db.format_class(user.get("class_code")),
            shift=user["shift"],
            lang="Русский" if lang == "ru" else "Қазақша"
        )
        send_msg(wa_id, msg_text)
    elif text_ci in ("3", "настройки", "параметрлер"):
        # Simple toggle language for now
        new_lang = "kk" if lang == "ru" else "ru"
        db.update_user_lang(wa_id, new_lang)
        send_msg(wa_id, t("lang_changed", new_lang))
        send_msg(wa_id, get_main_menu_text(new_lang, user["role"]))
    elif text_ci in ("4", "помощь", "анықтама"):
        send_msg(wa_id, t("help_text", lang))
    elif text_ci in ("5", "расписание на неделю", "апталық кесте"):
        handle_weekly_schedule(wa_id, user)
        send_msg(wa_id, get_main_menu_text(user["lang"], user["role"]))
    elif text_ci.startswith("6") and user["role"] in ("teacher", "zavuch"):
        new_code = db.create_invite_code("student", user.get("class_code"), user.get("shift", 1), wa_id)
        msg_ru = f"✅ Код для ученика создан:\n\n`{new_code}`\n\n_Передайте этот код ученику._"
        msg_kk = f"✅ Оқушы коды жасалды:\n\n`{new_code}`\n\n_Бұл кодты оқушыға беріңіз._"
        send_msg(wa_id, msg_ru if lang == "ru" else msg_kk)
        send_msg(wa_id, get_main_menu_text(lang, user["role"]))
    elif text_ci.startswith("7") and user["role"] in ("teacher", "zavuch"):
        codes = db.get_active_codes_by_creator(wa_id)
        if not codes:
            msg_ru = "У вас нет активных пригласительных кодов."
            msg_kk = "Сізде белсенді шақыру кодтары жоқ."
            send_msg(wa_id, msg_ru if lang == "ru" else msg_kk)
        else:
            lines = ["📋 " + ("Ваши активные коды:" if lang == "ru" else "Сіздің белсенді кодтарыңыз:")]
            for c in codes:
                lines.append(f"• `{c['code']}` ({c['role']})")
            send_msg(wa_id, "\n".join(lines))
        send_msg(wa_id, get_main_menu_text(lang, user["role"]))
    elif text_ci.startswith("8") and user["role"] in ("teacher", "zavuch"):
        FSM_DATA[wa_id] = {"state": "wait_broadcast_text"}
        msg_ru = "📝 Введите текст для рассылки\n(отправьте 'отмена' для выхода):"
        msg_kk = "📝 Рассылкаға арналған мәтінді енгізіңіз\n(шығу үшін 'отмена' жіберіңіз):"
        send_msg(wa_id, msg_ru if lang == "ru" else msg_kk)
    elif text_ci.startswith("9") and user["role"] == "zavuch":
        FSM_DATA[wa_id] = {"state": "edit_schedule_class"}
        send_msg(wa_id, t("edit_schedule_ask_class", lang))
    else:
        # Default menu: send schedule then menu
        handle_schedule(wa_id, user)
        send_msg(wa_id, get_main_menu_text(user["lang"], user["role"]))

def webhook_handler(typeWebhook, body):
    print(f"WEBHOOK: {typeWebhook}")
    if typeWebhook == 'incomingMessageReceived':
        try:
            messageData = body['messageData']
            senderData = body['senderData']
            chatId = senderData['chatId']
            
            # Skip group chats
            if not chatId.endswith('@c.us'):
                return
                
            wa_id_str = chatId.split('@')[0]
            wa_id = int(wa_id_str)
            
            text = ""
            if messageData['typeMessage'] == 'textMessage':
                text = messageData['textMessageData']['textMessage']
            elif messageData['typeMessage'] == 'extendedTextMessage':
                text = messageData['extendedTextMessageData']['text']
                
            if text:
                print(f"Received WA msg from {wa_id}: {text}")
                process_message(wa_id, text)
        except Exception as e:
            print("Error processing webhook:", e)

if __name__ == '__main__':
    if not ID_INSTANCE or not API_TOKEN_INSTANCE:
        print("ОШИБКА: Заполните ID_INSTANCE и API_TOKEN_INSTANCE в .env")
    else:
        print("🟢 WhatsApp бот запущен (Long Polling) ...")
        # clear backlog
        greenAPI.webhooks.startReceivingNotifications(webhook_handler)
