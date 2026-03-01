import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    BotCommand, WebAppInfo,
)
from aiogram.filters import CommandStart, Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from cachetools import TTLCache

import uvicorn
from web_app import app as fastapi_app

from db import (
    init_db, seed_demo_data, add_user, get_user,
    get_all_users, get_users_by_class, get_lessons, get_all_classes,
    create_invite_code, use_invite_code, get_active_codes_by_creator,
    get_setting, set_setting, delete_user, set_weekly_schedule,
    format_class, update_user_lang, get_bot_stats, get_full_backup,
)
from schedule_config import get_shifts, get_now_almaty, get_weekday_almaty
from translations import TEXTS

from whatsapp_bot import send_msg as wa_send_msg, html_to_wa

async def send_to_user(bot_instance: Bot, user: dict, text: str, parse_mode=ParseMode.HTML):
    platform = user.get("platform", "telegram")
    if platform == "whatsapp":
        wa_text = html_to_wa(text) if parse_mode == ParseMode.HTML else text
        try:
            await asyncio.to_thread(wa_send_msg, user["tg_id"], wa_text)
        except Exception as e:
            logger.error(f"WA Broadcast Error {user['tg_id']}: {e}")
            raise e
    else:
        try:
            await bot_instance.send_message(user["tg_id"], text, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"TG Broadcast Error {user['tg_id']}: {e}")
            raise e

BOT_TOKEN = "8794322225:AAHPZXDTCUWXueY77Dq0wTEdvyGRROb7Uqw"
ADMIN_ID = 7903470823
WEBAPP_URL = "https://your-fastapi-site.com"
BOT_USERNAME = "SchoolUshtobeBot"

# Timezone definition
ALMATY_TZ = ZoneInfo("Asia/Almaty")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()


def ensure_git_init():
    """Checks if .git folder exists, if not - initializes it so /update can work."""
    import subprocess
    import os
    repo_path = os.path.dirname(os.path.abspath(__file__))
    git_path = os.path.join(repo_path, ".git")
    
    if not os.path.exists(git_path):
        print("🚀 [System] Git folder not found. Initializing repository for auto-updates...")
        try:
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(["git", "remote", "add", "origin", "https://github.com/MadeByZharl/School_Bot.git"], cwd=repo_path, check=True)
            subprocess.run(["git", "fetch", "origin"], cwd=repo_path, check=True)
            # We don't reset --hard here to avoid losing non-pushed local changes on first boot
            print("✅ [System] Git initialized successfully!")
        except Exception as e:
            print(f"❌ [System] Failed to initialize git: {e}")

# Run git check at boot
ensure_git_init()
dp = Dispatcher(storage=storage)

spam_cache = TTLCache(maxsize=10000, ttl=1.5)
warning_cache = TTLCache(maxsize=10000, ttl=5.0)

class AntiSpamMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        
        # If user is in spam cache, they clicked too fast
        if user_id in spam_cache:
            # If they haven't been warned recently, warn them
            if user_id not in warning_cache:
                warning_cache[user_id] = True
                user = get_user(user_id)
                lang = user["lang"] if user else "ru"
                
                if isinstance(event, Message):
                    await event.answer(t("spam_warning", lang), parse_mode=ParseMode.HTML)
                elif isinstance(event, CallbackQuery):
                    await event.answer(t("spam_warning", lang), show_alert=True)
            return
            
        # Register the action
        spam_cache[user_id] = True
        return await handler(event, data)

dp.message.middleware(AntiSpamMiddleware())
dp.callback_query.middleware(AntiSpamMiddleware())

router = Router()
dp.include_router(router)

BAD_WORDS = ["блять", "сука", "хуй", "пизд", "ебан", "нахуй", "залуп", "ёб", "дерьм"]

ROLE_MAP = {
    "student": "role_student",
    "teacher": "role_teacher",
    "zavuch": "role_zavuch",
}

# УПРАВЛЕНИЕ РЕЖИМОМ ЗВОНКОВ
BELL_MODE_LABEL = {
    "standard": "bell_standard",
    "short": "bell_short",
    "custom": "bell_custom"
}

LANG_LABEL = {"ru": "🇷🇺 Русский", "kk": "🇰🇿 Қазақша"}

DAY_NAMES_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
DAY_NAMES_KK = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]

BTN = lambda key: {TEXTS[key]["ru"], TEXTS[key]["kk"]}

ALL_MENU_BUTTONS = (
    BTN("menu_schedule") | BTN("menu_profile") |
    BTN("menu_settings") | BTN("menu_help") |
    BTN("menu_gen_student_code") | BTN("menu_gen_teacher_code") |
    BTN("menu_send_class") | BTN("menu_send_all") | BTN("menu_my_codes") |
    BTN("menu_bell_mode") | BTN("menu_send_class_zavuch") | BTN("menu_edit_schedule") |
    BTN("menu_stats")
)


class EditScheduleInline(StatesGroup):
    choosing_class = State()
    entering_custom_subject = State()


class Registration(StatesGroup):
    choosing_lang = State()
    entering_code = State()
    entering_name = State()


class Broadcast(StatesGroup):
    waiting_text_all = State()
    waiting_text_class = State()
    waiting_class_code_zavuch = State()
    waiting_text_class_zavuch = State()


class GenCode(StatesGroup):
    entering_class_code = State()
    choosing_shift = State()


def t(key: str, lang: str = "ru") -> str:
    return TEXTS.get(key, {}).get(lang, TEXTS.get(key, {}).get("ru", key))


def has_bad_words(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in BAD_WORDS)


def validate_fio(text: str) -> bool:
    parts = text.strip().split()
    if len(parts) < 2:
        return False
    for p in parts:
        if not p or not p[0].isupper():
            return False
        if not all(c.isalpha() for c in p):
            return False
    return True


def get_main_menu(lang: str = "ru", role: str = "student") -> ReplyKeyboardMarkup:
    rows = [
        [
            KeyboardButton(text=t("menu_schedule", lang)),
            KeyboardButton(text=t("menu_profile", lang)),
        ],
        [
            KeyboardButton(text=t("menu_settings", lang)),
            KeyboardButton(text=t("menu_help", lang)),
        ],
    ]
    if role == "teacher":
        rows.append([
            KeyboardButton(text=t("menu_gen_student_code", lang)),
            KeyboardButton(text=t("menu_send_class", lang)),
        ])
        rows.append([
            KeyboardButton(text=t("menu_my_codes", lang)),
        ])
    elif role == "zavuch":
        rows.append([
            KeyboardButton(text=t("menu_gen_student_code", lang)),
            KeyboardButton(text=t("menu_gen_teacher_code", lang)),
        ])
        rows.append([
            KeyboardButton(text=t("menu_send_all", lang)),
            KeyboardButton(text=t("menu_send_class_zavuch", lang)),
        ])
        rows.append([
            KeyboardButton(text=t("menu_my_codes", lang)),
            KeyboardButton(text=t("menu_bell_mode", lang)),
        ])
        rows.append([
            KeyboardButton(text=t("menu_edit_schedule", lang)),
            KeyboardButton(text=t("menu_stats", lang)),
        ])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
    )


def menu_for_user(user: dict) -> ReplyKeyboardMarkup:
    return get_main_menu(user.get("lang", "ru"), user.get("role", "student"))


def make_invite_link(code: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start={code}"


async def set_bot_commands(b: Bot):
    commands_ru = [BotCommand(command="start", description="🔄 Перезапуск")]
    commands_kk = [BotCommand(command="start", description="🔄 Қайта бастау")]
    await b.set_my_commands(commands_ru, language_code="ru")
    await b.set_my_commands(commands_kk, language_code="kk")
    await b.set_my_commands(commands_ru)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /start [CODE] → lang → name → done
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    existing = get_user(message.from_user.id)
    if existing:
        lang = existing["lang"]
        await message.answer(
            t("already_registered", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=menu_for_user(existing),
        )
        return

    deep_link_code = command.args
    if deep_link_code:
        await state.update_data(pending_code=deep_link_code.strip().upper())

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang_kk"),
        ]
    ])
    await message.answer(
        t("welcome", "ru"),
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(Registration.choosing_lang)

@router.message(Command("logout"))
async def cmd_logout(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if user:
        lang = user["lang"]
        delete_user(message.from_user.id)
        await state.clear()
        
        msg_ru = "🚪 Вы успешно вышли из аккаунта.\nВведите /start, чтобы зарегистрироваться заново."
        msg_kk = "🚪 Сіз аккаунттан сәтті шықтыңыз.\nҚайта тіркелу үшін /start пәрменін енгізіңіз."
        text = msg_ru if lang == "ru" else msg_kk
        
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("Вы не зарегистрированы.\nВведите /start", reply_markup=ReplyKeyboardRemove())


@router.message(Command("update"))
async def cmd_update(message: Message):
    user = get_user(message.from_user.id)
    if not user or (user["role"] != "zavuch" and message.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return
    
    lang = user["lang"]
    await message.answer(t("update_start", lang), parse_mode=ParseMode.HTML)
    
    import subprocess
    import sys
    import os
    
    try:
        # Detect repo path
        repo_path = os.path.dirname(os.path.abspath(__file__))
        branch = os.getenv("GIT_BRANCH", "main")
        
        # Check if it's a git repo
        if not os.path.exists(os.path.join(repo_path, ".git")):
            # Auto-initialize if possible
            cmds = [
                ["git", "init"],
                ["git", "remote", "add", "origin", "https://github.com/MadeByZharl/School_Bot.git"],
                ["git", "fetch", "origin"],
                ["git", "reset", "--hard", f"origin/{branch}"]
            ]
            for cmd in cmds:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=repo_path)
                out, err = p.communicate()
                if p.returncode != 0:
                    await message.answer(t("update_error", lang).format(error=f"Init fail: {err}"), parse_mode=ParseMode.HTML)
                    return
            stdout = "Git initialized and synchronized."
        else:
            # Regular pull
            process = subprocess.Popen(
                ["git", "pull", "origin", branch],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=repo_path
            )
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                # Force reset if pull fails due to conflicts
                process = subprocess.Popen(["git", "reset", "--hard", f"origin/{branch}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=repo_path)
                stdout_r, stderr_r = process.communicate()
                stdout = f"Pull failed (conflicts?), forced reset: {stdout_r}"

        await message.answer(t("update_success", lang) + f"\n\n<code>{stdout}</code>", parse_mode=ParseMode.HTML)
        
        # Restart process
        os._exit(0)
        
    except Exception as e:
        await message.answer(t("update_error", lang).format(error=str(e)), parse_mode=ParseMode.HTML)


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Exclusive command for the bot owner (SUPERUSER)."""
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        # Invisible to non-admins
        return

    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    
    stats = get_bot_stats()
    res = f"👑 <b>Панель Владельца</b> (SUPERUSER)\n\n"
    res += t("stats_users_total", lang).format(total=stats["total"])
    res += t("stats_roles", lang).format(
        students=stats["roles"].get("student", 0),
        teachers=stats["roles"].get("teacher", 0),
        zavuchs=stats["roles"].get("zavuch", 0)
    )
    
    if stats["classes"]:
        res += t("stats_classes_title", lang)
        for c in stats["classes"]:
            res += t("stats_class_item", lang).format(
                class_name=format_class(c["class_code"]),
                count=c["count"]
            )
    
    res += f"\n🌐 Web Management: <code>{WEBAPP_URL}</code>"
    res += f"\n⚙️ System: Online\n\n💡 <i>Скрытые команды:</i>\n/update — Обновить код\n/backup — Скачать базу данных"
    
    await message.answer(res, parse_mode=ParseMode.HTML)


@router.message(Command("backup"))
async def cmd_backup(message: Message, state: FSMContext):
    """Secret command to export DB."""
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    
    import json
    import tempfile
    from aiogram.types import FSInputFile
    
    await message.answer("🔄 Подготовка резервной копии...")
    try:
        data = get_full_backup()
        # Convert datetime objects to string for JSON serialization
        def default_serializer(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return str(obj)
            
        json_str = json.dumps(data, default=default_serializer, ensure_ascii=False, indent=2)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write(json_str)
            temp_path = f.name
            
        name = f"schoolbot_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        db_file = FSInputFile(temp_path, filename=name)
        await message.answer_document(db_file, caption=f"📦 Резервная копия базы данных ({datetime.now().strftime('%d.%m.%Y %H:%M')})")
        
        # Cleanup
        os.remove(temp_path)
    except Exception as e:
        await message.answer(f"❌ Ошибка бэкапа: {e}")


@router.callback_query(Registration.choosing_lang, F.data.in_({"lang_ru", "lang_kk"}))
async def process_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(lang=lang)

    data = await state.get_data()
    pending_code = data.get("pending_code")

    if pending_code:
        code_data = use_invite_code(pending_code, callback.from_user.id)
        if code_data:
            role = code_data["role"]
            role_label = t(ROLE_MAP.get(role, "role_student"), lang)
            await state.update_data(
                role=role,
                class_code=code_data["class_code"],
                shift=code_data["shift"],
            )
            await callback.message.edit_text(
                t(f"code_accepted_{role}", lang).format(class_code=format_class(code_data.get("class_code", ""))),
                parse_mode=ParseMode.HTML,
            )
            if role == "student":
                await callback.message.answer(t("ask_name_student", lang), parse_mode=ParseMode.HTML)
            else:
                await callback.message.answer(t("ask_name_teacher", lang), parse_mode=ParseMode.HTML)
            await state.set_state(Registration.entering_name)
            await callback.answer()
            return
        else:
            await callback.message.edit_text(
                t("invalid_code", lang),
                parse_mode=ParseMode.HTML,
            )
            await callback.answer()
            await state.clear()
            return

    await callback.message.edit_text(
        t("ask_invite_code", lang),
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(Registration.entering_code)
    await callback.answer()


@router.message(Registration.entering_code)
async def process_invite_code(message: Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    lang = data["lang"]
    code_text = message.text.strip().upper()

    code_data = use_invite_code(code_text, message.from_user.id)
    if not code_data:
        await message.answer(t("invalid_code", lang), parse_mode=ParseMode.HTML)
        return

    role = code_data["role"]
    role_label = t(ROLE_MAP.get(role, "role_student"), lang)
    await state.update_data(
        role=role,
        class_code=code_data["class_code"],
        shift=code_data["shift"],
    )
    await message.answer(
        t(f"code_accepted_{role}", lang).format(class_code=format_class(code_data.get("class_code", ""))),
        parse_mode=ParseMode.HTML,
    )
    if role == "student":
        await message.answer(t("ask_name_student", lang), parse_mode=ParseMode.HTML)
    else:
        await message.answer(t("ask_name_teacher", lang), parse_mode=ParseMode.HTML)
    await state.set_state(Registration.entering_name)


@router.message(Registration.entering_name)
async def process_name(message: Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    lang = data["lang"]
    role = data["role"]
    name = message.text.strip()

    if role == "student":
        if len(name) < 2 or len(name) > 20 or has_bad_words(name):
            await message.answer(t("invalid_nickname", lang), parse_mode=ParseMode.HTML)
            return
    else:
        if not validate_fio(name):
            await message.answer(t("invalid_fio", lang), parse_mode=ParseMode.HTML)
            return

    user = add_user(
        tg_id=message.from_user.id,
        full_name=name,
        role=role,
        lang=lang,
        class_code=data.get("class_code"),
        shift=data.get("shift", 1),
    )
    await message.answer(
        t("registration_done", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=menu_for_user(user),
    )
    await state.clear()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📅 РАСПИСАНИЕ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.in_(BTN("menu_schedule")))
async def cmd_schedule(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user:
        await message.answer(t("not_registered", "ru"), parse_mode=ParseMode.HTML)
        return
    lang = user["lang"]
    bell_mode = get_setting("bell_mode", "standard")
    weekday = get_weekday_almaty()
    now_time = get_now_almaty()
    show_day = weekday
    is_tomorrow = False

    # Если сейчас воскресенье → показать понедельник
    if weekday >= 6:
        show_day = 0
        is_tomorrow = True
    else:
        # Проверим закончились ли уроки сегодня
        # Для этого берем правильные шифты для сегодняшнего дня
        today_shifts = get_shifts(bell_mode, weekday)
        today_shift_data = today_shifts.get(user["shift"], {})
        
        last_end = "00:00"
        for times in today_shift_data.values():
            if times["end"] > last_end:
                last_end = times["end"]
                
        if now_time > last_end:
            # Уроки кончились — показываем следующий учебный день
            if weekday == 4:      # Пятница → Понедельник
                show_day = 0
            elif weekday == 5:    # Суббота → Понедельник
                show_day = 0
            else:
                show_day = weekday + 1
            is_tomorrow = True

    day_names = DAY_NAMES_RU if lang == "ru" else DAY_NAMES_KK
    day_name = day_names[show_day]
    lessons = get_lessons(user.get("class_code", ""), show_day)
    
    # Теперь получаем шифты именно для того дня, который будем показывать
    shifts = get_shifts(bell_mode, show_day)
    shift_data = shifts.get(user["shift"], {})
    if not lessons:
        await message.answer(t("no_lessons", lang), parse_mode=ParseMode.HTML)
        return
    lines = [f"📆 <b>{day_name}</b>\n"]
    for ls in lessons:
        num = ls["lesson_num"]
        time_info = shift_data.get(num, {})
        start = time_info.get("start", "—")
        end = time_info.get("end", "—")
        connector = "└" if ls == lessons[-1] else "├"
        
        lesson_name = ls["lesson_name"]
        if lang == "ru":
            from translations import LESSON_TRANSLATIONS
            lesson_name = LESSON_TRANSLATIONS.get(lesson_name, lesson_name)

        is_finished = (not is_tomorrow) and (end != "—") and (now_time > end)
        
        if is_finished:
            lines.append(f"{connector} {num}. <s><b>{lesson_name}</b>  ({start}–{end})</s>")
        else:
            lines.append(f"{connector} {num}. <b>{lesson_name}</b>  ({start}–{end})")
    mode_label = t(BELL_MODE_LABEL.get(bell_mode, "bell_standard"), lang)
    lines.append(f"\n<i>{mode_label}</i>")
    header_key = "schedule_tomorrow" if is_tomorrow else "schedule_today"
    text = t(header_key, lang).format(lessons="\n".join(lines))
    await message.answer(text, parse_mode=ParseMode.HTML)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👤 ПРОФИЛЬ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.in_(BTN("menu_profile")))
async def cmd_profile(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user:
        await message.answer(t("not_registered", "ru"), parse_mode=ParseMode.HTML)
        return
    lang = user["lang"]
    role_label = t(ROLE_MAP.get(user["role"], "role_student"), lang)
    text = t("profile_card", lang).format(
        name=user["full_name"],
        role=role_label,
        class_code=format_class(user.get("class_code")),
        shift=user["shift"],
        lang=LANG_LABEL.get(lang, lang),
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ НАСТРОЙКИ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.in_(BTN("menu_settings")))
async def cmd_settings(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user:
        await message.answer(t("not_registered", "ru"), parse_mode=ParseMode.HTML)
        return
    lang = user["lang"]
    new_lang = "kk" if lang == "ru" else "ru"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{LANG_LABEL[new_lang]}",
            callback_data=f"set_lang_{new_lang}",
        )],
    ])
    await message.answer(
        t("settings_text", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@router.callback_query(F.data.in_({"set_lang_ru", "set_lang_kk"}))
async def process_change_lang(callback: CallbackQuery):
    new_lang = callback.data.split("_")[-1]
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    update_user_lang(callback.from_user.id, new_lang)
    user["lang"] = new_lang
    await callback.message.edit_text(
        t("lang_changed", new_lang),
        parse_mode=ParseMode.HTML,
    )
    await callback.message.answer("👌", reply_markup=menu_for_user(user))
    await callback.answer()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🆘 ПОМОЩЬ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.in_(BTN("menu_help")))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    await message.answer(t("help_text", lang), parse_mode=ParseMode.HTML)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  РЕЖИМ ЗВОНКОВ (только завуч)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.in_(BTN("menu_bell_mode")))
async def btn_bell_mode(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user or (user["role"] != "zavuch" and message.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return
    lang = user["lang"]
    current_mode = get_setting("bell_mode", "standard")
    current_label = t(BELL_MODE_LABEL.get(current_mode, "bell_standard"), lang)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("bell_standard", lang),
            callback_data="bell_set_standard",
        )],
        [InlineKeyboardButton(
            text=t("bell_short", lang),
            callback_data="bell_set_short",
        )],
        [InlineKeyboardButton(
            text=t("bell_custom", lang),
            callback_data="bell_set_custom",
        )],
    ])
    await message.answer(
        t("bell_mode_status", lang).format(current=current_label),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@router.callback_query(F.data.in_({"bell_set_standard", "bell_set_short", "bell_set_custom"}))
async def process_bell_mode(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user or user["role"] != "zavuch":
        await callback.answer()
        return
    lang = user["lang"]
    new_mode = callback.data.replace("bell_set_", "")
    set_setting("bell_mode", new_mode)
    mode_label = t(BELL_MODE_LABEL[new_mode], lang)
    await callback.message.edit_text(
        t("bell_mode_changed", lang).format(mode=mode_label),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(F.text.in_(BTN("menu_stats")))
async def btn_stats(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user or (user["role"] != "zavuch" and message.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return

    lang = user["lang"]
    stats = get_bot_stats()
    
    res = t("stats_title", lang)
    res += t("stats_users_total", lang).format(total=stats["total"])
    res += t("stats_roles", lang).format(
        students=stats["roles"].get("student", 0),
        teachers=stats["roles"].get("teacher", 0),
        zavuchs=stats["roles"].get("zavuch", 0)
    )
    
    if stats["classes"]:
        res += t("stats_classes_title", lang)
        for c in stats["classes"]:
            res += t("stats_class_item", lang).format(
                class_name=format_class(c["class_code"]),
                count=c["count"]
            )
            
    await message.answer(res, parse_mode=ParseMode.HTML)
    # Уведомить всех пользователей
    all_users = get_all_users()
    sent = 0
    for u in all_users:
        u_lang = u.get("lang", "ru")
        u_mode_label = t(BELL_MODE_LABEL[new_mode], u_lang)
        text = t("bell_mode_notify", u_lang).format(mode=u_mode_label)
        try:
            await send_to_user(bot, u, text, parse_mode=ParseMode.HTML)
            sent += 1
            if sent % 25 == 0:
                await asyncio.sleep(1)
        except Exception:
            pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✏️ ИЗМЕНЕНИЕ РАСПИСАНИЯ (INLINE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.in_(BTN("menu_edit_schedule")))
async def btn_edit_schedule_inline(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user or (user["role"] != "zavuch" and message.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return
        
    lang = user["lang"]
    from db import get_all_classes
    classes = get_all_classes()
    
    keyboard = []
    row = []
    for c in classes:
        row.append(KeyboardButton(text=c))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="Отмена")])
    
    kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    await message.answer("Для какого класса вы хотите изменить расписание? (Выберите из списка)", reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(EditScheduleInline.choosing_class)

@router.message(StateFilter(EditScheduleInline.choosing_class))
async def edit_schedule_inline_select_class(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    if message.text.lower() in ("отмена", "cancel", "болдырмау"):
        await state.clear()
        await message.answer("🚫", reply_markup=menu_for_user(user))
        return
        
    class_code = format_class(message.text.strip().upper())
    await state.update_data(edit_class=class_code)
    
    # Важно: убираем Reply-клавиатуру, чтобы оставить только Inline
    await message.answer(f"Выбран класс: <b>{class_code}</b>", reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.HTML)
    
    days = DAY_NAMES_RU if lang == "ru" else DAY_NAMES_KK
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=days[0], callback_data="es_day_0"), InlineKeyboardButton(text=days[1], callback_data="es_day_1")],
        [InlineKeyboardButton(text=days[2], callback_data="es_day_2"), InlineKeyboardButton(text=days[3], callback_data="es_day_3")],
        [InlineKeyboardButton(text=days[4], callback_data="es_day_4"), InlineKeyboardButton(text=days[5], callback_data="es_day_5")],
    ])
    
    await message.answer("Выберите день недели:", reply_markup=kb)

@router.callback_query(F.data.startswith("es_day_"))
async def edit_schedule_inline_select_day(callback: CallbackQuery, state: FSMContext):
    day_idx = int(callback.data.split("_")[2])
    await state.update_data(edit_day_idx=day_idx)
    data = await state.get_data()
    class_code = data.get("edit_class")
    if not class_code:
        await callback.answer("Ошибка: Класс не выбран.", show_alert=True)
        return
        
    user = get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    days = DAY_NAMES_RU if lang == "ru" else DAY_NAMES_KK
    
    from db import get_lessons
    lessons = get_lessons(class_code, day_idx)
    # create a map of lesson_num to lesson_name
    lesson_map = {ls["lesson_num"]: ls["lesson_name"] for ls in lessons}
    
    kb_rows = []
    for i in range(1, 11):
        name = lesson_map.get(i, "➕ Пусто")
        btn_text = f"{i}. {name}"
        kb_rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"es_les_{i}")])
        
    kb_rows.append([InlineKeyboardButton(text="🔙 К выбору дня", callback_data="es_back_day")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await callback.message.edit_text(f"📆 <b>{days[day_idx]}</b> ({class_code})\nВыберите урок для изменения:", reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(F.data == "es_back_day")
async def edit_schedule_inline_back_day(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    days = DAY_NAMES_RU if lang == "ru" else DAY_NAMES_KK
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=days[0], callback_data="es_day_0"), InlineKeyboardButton(text=days[1], callback_data="es_day_1")],
        [InlineKeyboardButton(text=days[2], callback_data="es_day_2"), InlineKeyboardButton(text=days[3], callback_data="es_day_3")],
        [InlineKeyboardButton(text=days[4], callback_data="es_day_4"), InlineKeyboardButton(text=days[5], callback_data="es_day_5")],
    ])
    await callback.message.edit_text("Выберите день недели:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("es_les_"))
async def edit_schedule_inline_select_lesson(callback: CallbackQuery, state: FSMContext):
    lesson_num = int(callback.data.split("_")[2])
    await state.update_data(edit_lesson_num=lesson_num)
    
    from db import get_all_subjects
    subjects = get_all_subjects()
    await state.update_data(subject_list=subjects)
    
    kb_rows = []
    row = []
    for i, subj in enumerate(subjects):
        row.append(InlineKeyboardButton(text=subj, callback_data=f"es_subj_{i}"))
        if len(row) == 2:
            kb_rows.append(row)
            row = []
    if row:
        kb_rows.append(row)
        
    kb_rows.append([
        InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="es_manual"),
        InlineKeyboardButton(text="🗑 Очистить урок", callback_data="es_clear")
    ])
    kb_rows.append([InlineKeyboardButton(text="🔙 Назад к урокам", callback_data="es_back_les")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(f"Урок <b>№{lesson_num}</b>.\nВыберите предмет из списка или введите вручную:", reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(F.data == "es_back_les")
async def edit_schedule_inline_back_les(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    day_idx = data.get("edit_day_idx")
    if day_idx is not None:
        callback.data = f"es_day_{day_idx}"
        await edit_schedule_inline_select_day(callback, state)
    else:
        await callback.answer("Ошибка. Начните сначала.", show_alert=True)

@router.callback_query(F.data.startswith("es_subj_"))
async def edit_schedule_inline_set_subject(callback: CallbackQuery, state: FSMContext):
    subj_idx = int(callback.data.split("_")[2])
    data = await state.get_data()
    subjects = data.get("subject_list", [])
    if subj_idx >= len(subjects):
        await callback.answer("Ошибка индекса предмета.", show_alert=True)
        return
        
    subj_name = subjects[subj_idx]
    class_code = data["edit_class"]
    day_idx = data["edit_day_idx"]
    lesson_num = data["edit_lesson_num"]
    
    from db import update_single_lesson
    update_single_lesson(class_code, day_idx, lesson_num, subj_name)
    
    await callback.answer(f"✅ Сохранено: {subj_name}")
    callback.data = f"es_day_{day_idx}"
    await edit_schedule_inline_select_day(callback, state)

@router.callback_query(F.data == "es_clear")
async def edit_schedule_inline_clear(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    class_code = data["edit_class"]
    day_idx = data["edit_day_idx"]
    lesson_num = data["edit_lesson_num"]
    
    from db import delete_single_lesson
    delete_single_lesson(class_code, day_idx, lesson_num)
    
    await callback.answer("🗑 Урок удалён (пусто)")
    callback.data = f"es_day_{day_idx}"
    await edit_schedule_inline_select_day(callback, state)

@router.callback_query(F.data == "es_manual")
async def edit_schedule_inline_manual(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditScheduleInline.entering_custom_subject)
    
    # We edit text and wait for user's message
    await callback.message.edit_text("✍️ Напишите название предмета в чат (или нажмите Отмена):")
    await callback.answer()

@router.message(StateFilter(EditScheduleInline.entering_custom_subject))
async def edit_schedule_inline_manual_text(message: Message, state: FSMContext):
    subj_name = message.text.strip()
    data = await state.get_data()
    class_code = data.get("edit_class")
    day_idx = data.get("edit_day_idx")
    lesson_num = data.get("edit_lesson_num")
    
    if not class_code or day_idx is None or not lesson_num:
        await message.answer("Произошла ошибка сессии. Начните заново из меню.")
        await state.clear()
        return
    
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    
    if subj_name.lower() in ("отмена", "cancel", "болдырмау"):
        await state.set_state(None)
        await message.answer("🚫", reply_markup=menu_for_user(user))
        return
        
    from db import update_single_lesson
    update_single_lesson(class_code, day_idx, lesson_num, subj_name)
    
    try:
        await message.delete()
    except Exception:
        pass
        
    days = DAY_NAMES_RU if lang == "ru" else DAY_NAMES_KK
    from db import get_lessons
    lessons = get_lessons(class_code, day_idx)
    lesson_map = {ls["lesson_num"]: ls["lesson_name"] for ls in lessons}
    
    kb_rows = []
    for i in range(1, 11):
        name = lesson_map.get(i, "➕ Пусто")
        btn_text = f"{i}. {name}"
        kb_rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"es_les_{i}")])
        
    kb_rows.append([InlineKeyboardButton(text="🔙 К выбору дня", callback_data="es_back_day")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await message.answer("✅ Вручную сохранено: " + subj_name, reply_markup=menu_for_user(user))
    await state.set_state(None)
    await message.answer(f"📆 <b>{days[day_idx]}</b> ({class_code})\nВыберите урок для изменения:", reply_markup=kb, parse_mode=ParseMode.HTML)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔑 ГЕНЕРАЦИЯ КОДОВ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.in_(BTN("menu_gen_teacher_code")))
async def btn_gen_teacher_code(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user or user["role"] != "zavuch":
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return
    await state.update_data(gen_role="teacher", gen_reusable=False)
    lang = user["lang"]
    await message.answer(t("gen_code_ask_class", lang), parse_mode=ParseMode.HTML)
    await state.set_state(GenCode.entering_class_code)


@router.message(F.text.in_(BTN("menu_gen_student_code")))
async def btn_gen_student_code(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user or user["role"] not in ("zavuch", "teacher"):
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return
    lang = user["lang"]
    if user["role"] == "teacher" and user.get("class_code"):
        code = create_invite_code(
            role="student",
            class_code=user["class_code"],
            shift=user["shift"],
            created_by=message.from_user.id,
            reusable=True,
        )
        link = make_invite_link(code)
        role_label = t("role_student", lang)
        await message.answer(
            t("code_generated", lang).format(
                role=role_label,
                class_code=user["class_code"],
                shift=user["shift"],
                code=code,
                link=link,
            ),
            parse_mode=ParseMode.HTML,
        )
        return
    await state.update_data(gen_role="student", gen_reusable=True)
    await message.answer(t("gen_code_ask_class", lang), parse_mode=ParseMode.HTML)
    await state.set_state(GenCode.entering_class_code)


@router.message(GenCode.entering_class_code)
async def gen_code_class(message: Message, state: FSMContext):
    if not message.text:
        return
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    class_code = message.text.strip().upper()
    await state.update_data(gen_class_code=class_code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣ Смена", callback_data="gen_shift_1"),
            InlineKeyboardButton(text="2️⃣ Смена", callback_data="gen_shift_2"),
        ]
    ])
    await message.answer(
        t("gen_code_ask_shift", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await state.set_state(GenCode.choosing_shift)


@router.callback_query(GenCode.choosing_shift, F.data.in_({"gen_shift_1", "gen_shift_2"}))
async def gen_code_shift(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    shift = int(callback.data.split("_")[-1])
    gen_role = data["gen_role"]
    gen_reusable = data.get("gen_reusable", False)
    class_code = data["gen_class_code"]

    code = create_invite_code(
        role=gen_role,
        class_code=class_code,
        shift=shift,
        created_by=callback.from_user.id,
        reusable=gen_reusable,
    )
    link = make_invite_link(code)
    role_label = t(ROLE_MAP.get(gen_role, "role_student"), lang)
    await callback.message.edit_text(
        t("code_generated", lang).format(
            role=role_label,
            class_code=class_code,
            shift=shift,
            code=code,
            link=link,
        ),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()
    await state.clear()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📋 МОИ КОДЫ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.in_(BTN("menu_my_codes")))
async def btn_my_codes(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user or user["role"] != "teacher":
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return
    lang = user["lang"]
    codes = get_active_codes_by_creator(message.from_user.id)
    if not codes:
        await message.answer(t("no_codes", lang), parse_mode=ParseMode.HTML)
        return
    lines = [t("my_codes_title", lang)]
    for i, c in enumerate(codes, 1):
        role_label = t(ROLE_MAP.get(c["role"], "role_student"), lang)
        connector = "└" if i == len(codes) else "├"
        reuse_icon = "♾" if c["reusable"] else "1️⃣"
        link = make_invite_link(c["code"])
        lines.append(
            f'{connector} {reuse_icon} <code>{c["code"]}</code> — {role_label} · {c["class_code"]} · 👥 {c["use_count"]}'
        )
        lines.append(f'   🔗 {link}')
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📢 РАССЫЛКА с подтверждением
# Завуч → всем | Завуч → классу | Учитель → своему классу
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.in_(BTN("menu_send_all")))
async def btn_send_all(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user or (user["role"] != "zavuch" and message.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return
    lang = user["lang"]
    await message.answer(t("send_all_prompt", lang), parse_mode=ParseMode.HTML)
    await state.set_state(Broadcast.waiting_text_all)


@router.message(Broadcast.waiting_text_all)
async def broadcast_all_confirm(message: Message, state: FSMContext):
    if not message.text:
        return
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    all_users = get_all_users()
    preview = message.text[:200] + ("..." if len(message.text) > 200 else "")
    await state.update_data(broadcast_text=message.text, broadcast_target="all")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_confirm_send", lang), callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text=t("btn_cancel_send", lang), callback_data="broadcast_cancel")],
    ])
    await message.answer(
        t("broadcast_confirm", lang).format(count=len(all_users), text=preview),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@router.message(F.text.in_(BTN("menu_send_class")), StateFilter(None))
async def btn_send_class_teacher(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user or user["role"] != "teacher":
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return
    lang = user["lang"]
    await message.answer(t("send_class_prompt", lang), parse_mode=ParseMode.HTML)
    await state.set_state(Broadcast.waiting_text_class)


@router.message(Broadcast.waiting_text_class)
async def broadcast_class_confirm(message: Message, state: FSMContext):
    if not message.text:
        return
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    if not user or not user["class_code"]:
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        await state.clear()
        return
    class_users = get_users_by_class(user["class_code"])
    preview = message.text[:200] + ("..." if len(message.text) > 200 else "")
    await state.update_data(
        broadcast_text=message.text,
        broadcast_target="class",
        broadcast_class=user["class_code"],
        broadcast_sender_name=user["full_name"],
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_confirm_send", lang), callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text=t("btn_cancel_send", lang), callback_data="broadcast_cancel")],
    ])
    await message.answer(
        t("broadcast_confirm", lang).format(count=len(class_users), text=preview),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


# ━━ Завуч → конкретный класс ━━


@router.message(F.text.in_(BTN("menu_send_class_zavuch")))
async def btn_send_class_zavuch(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user or (user["role"] != "zavuch" and message.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await message.answer(t("no_permission", lang), parse_mode=ParseMode.HTML)
        return
    lang = user["lang"]
    await message.answer(t("send_class_ask", lang), parse_mode=ParseMode.HTML)
    await state.set_state(Broadcast.waiting_class_code_zavuch)


@router.message(Broadcast.waiting_class_code_zavuch)
async def broadcast_zavuch_class_code(message: Message, state: FSMContext):
    if not message.text:
        return
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    class_code = message.text.strip().upper()
    await state.update_data(broadcast_class=class_code, broadcast_sender_name=user["full_name"])
    await message.answer(t("send_class_prompt", lang), parse_mode=ParseMode.HTML)
    await state.set_state(Broadcast.waiting_text_class_zavuch)


@router.message(Broadcast.waiting_text_class_zavuch)
async def broadcast_zavuch_class_confirm(message: Message, state: FSMContext):
    if not message.text:
        return
    data = await state.get_data()
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    class_code = data["broadcast_class"]
    class_users = get_users_by_class(class_code)
    preview = message.text[:200] + ("..." if len(message.text) > 200 else "")
    await state.update_data(broadcast_text=message.text, broadcast_target="class")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_confirm_send", lang), callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text=t("btn_cancel_send", lang), callback_data="broadcast_cancel")],
    ])
    await message.answer(
        t("broadcast_confirm", lang).format(count=len(class_users), text=preview),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


# ━━ Подтверждение / Отмена рассылки ━━


@router.callback_query(F.data == "broadcast_confirm")
async def broadcast_execute(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    text = data.get("broadcast_text", "")
    target = data.get("broadcast_target", "all")

    if target == "all":
        recipients = get_all_users()
        template_key = "broadcast_admin"
        format_args = lambda u_lang: {"text": text}
    else:
        class_code = data.get("broadcast_class", "")
        recipients = get_users_by_class(class_code)
        sender_name = data.get("broadcast_sender_name", "—")
        template_key = "broadcast_teacher"
        format_args = lambda u_lang: {"name": sender_name, "text": text}

    count = 0
    errors = 0
    for u in recipients:
        u_lang = u.get("lang", "ru")
        msg_text = t(template_key, u_lang).format(**format_args(u_lang))
        try:
            await send_to_user(bot, u, msg_text, parse_mode=ParseMode.HTML)
            count += 1
            if count % 25 == 0:
                await asyncio.sleep(1)
        except Exception:
            errors += 1

    result = t("broadcast_done", lang).format(count=count)
    if errors:
        result += f"\n⚠️ Ошибок: {errors}"
    await callback.message.edit_text(result, parse_mode=ParseMode.HTML)
    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    await callback.message.edit_text(
        t("broadcast_cancelled", lang),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()
    await state.clear()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CATCH-ALL: кнопка меню во время FSM → отмена
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# Redundant handler removed to fix 2-click bug


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUTO SCHEDULE NOTIFIER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def schedule_notifier():
    while True:
        await asyncio.sleep(60)
        try:
            now_time = get_now_almaty()
            weekday = get_weekday_almaty()

            if weekday >= 6:
                continue

            bell_mode = get_setting("bell_mode", "standard")
            all_users = get_all_users()
            shifts = get_shifts(bell_mode, weekday)

            # Оптимизация: кешируем уроки для каждого класса на эту итерацию
            class_lessons_cache = {}

            for shift_num, shift_lessons in shifts.items():
                shift_users = [u for u in all_users if u["shift"] == shift_num]
                if not shift_users:
                    continue

                for lesson_num, times in shift_lessons.items():
                    is_start = now_time == times["start"]
                    is_end = now_time == times["end"]

                    if not is_start and not is_end:
                        continue

                    sent = 0
                    for user in shift_users:
                        class_code = user.get("class_code")
                        if not class_code:
                            continue

                        # Получаем уроки класса
                        if class_code not in class_lessons_cache:
                            class_lessons_cache[class_code] = {
                                l["lesson_num"]: l["lesson_name"]
                                for l in get_lessons(class_code, weekday)
                            }
                        
                        lessons_map = class_lessons_cache[class_code]

                        # Если этого урока нет в расписании класса — НЕ уведомляем
                        if lesson_num not in lessons_map:
                            continue

                        lang = user["lang"]
                        if is_start:
                            text = t("lesson_start", lang).format(
                                num=lesson_num,
                                name=lessons_map[lesson_num],
                                start=times["start"],
                                end=times["end"],
                            )
                        else:  # is_end
                            text = t("lesson_end", lang).format(num=lesson_num)

                        try:
                            await send_to_user(bot, user, text, parse_mode=ParseMode.HTML)
                            sent += 1
                            if sent % 25 == 0:
                                await asyncio.sleep(1)
                        except Exception as e:
                            logger.error(f"Notify error {user['tg_id']}: {e}")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")


async def auto_backup_task():
    """Daily automated backup sent to ADMIN_ID."""
    import json
    import tempfile
    from aiogram.types import FSInputFile
    
    while True:
        now = datetime.now(ALMATY_TZ)
        # Calculate time until next target (e.g., 03:00 AM)
        target = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
            
        delay = (target - now).total_seconds()
        logger.info(f"Next automated backup scheduled in {delay/3600:.2f} hours")
        await asyncio.sleep(delay)
        
        try:
            data = get_full_backup()
            
            def default_serializer(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return str(obj)
                
            json_str = json.dumps(data, default=default_serializer, ensure_ascii=False, indent=2)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                f.write(json_str)
                temp_path = f.name
                
            name = f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            db_file = FSInputFile(temp_path, filename=name)
            await bot.send_document(
                chat_id=ADMIN_ID, 
                document=db_file, 
                caption=f"📦 Автоматическая резервная копия ({now.strftime('%d.%m.%Y %H:%M')})"
            )
            os.remove(temp_path)
            logger.info("Automated daily backup successful")
        except Exception as e:
            logger.error(f"Auto backup failed: {e}")
            try:
                await bot.send_message(chat_id=ADMIN_ID, text=f"❌ Ошибка автоматического бэкапа: {e}")
            except:
                pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STARTUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def on_startup():
    init_db()
    await set_bot_commands(bot)
    asyncio.create_task(schedule_notifier())
    asyncio.create_task(auto_backup_task())
    logger.info("Bot started, commands set, scheduler running.")


async def main():
    dp.startup.register(on_startup)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8080, log_level="info")
    # web_server = uvicorn.Server(config)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
