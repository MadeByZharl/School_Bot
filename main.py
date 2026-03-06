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
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent
from typing import Callable, Dict, Any, Awaitable
from cachetools import TTLCache

from db import (
    init_db, seed_demo_data, add_user, get_user,
    get_all_users, get_users_by_class, get_lessons, get_all_classes,
    create_invite_code, use_invite_code, get_active_codes_by_creator,
    get_setting, set_setting, delete_user, set_weekly_schedule,
    format_class, update_user_lang, get_bot_stats, get_full_backup,
    get_user_setting, get_user_settings_bulk, set_user_setting,
)
from schedule_config import get_shifts, get_now_almaty, get_weekday_almaty
from translations import TEXTS

from wa_client import send_msg as wa_send_msg, html_to_wa

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

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7903470823"))
WEBAPP_URL = "https://your-fastapi-site.com"
BOT_USERNAME = os.getenv("BOT_USERNAME", "OquBot")

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

ALL_MENU_BUTTONS = frozenset().union(*(BTN(k) for k in [
    "menu_schedule", "menu_profile", "menu_settings", "menu_help",
    "menu_gen_student_code", "menu_gen_teacher_code", "menu_send_class",
    "menu_send_all", "menu_my_codes", "menu_bell_mode", "menu_send_class_zavuch",
    "menu_edit_schedule", "menu_stats"
]))

router = Router()


spam_cache = TTLCache(maxsize=2000, ttl=0.3)
warning_cache = TTLCache(maxsize=2000, ttl=2.0)

# Stores last notification message_id per user to delete before sending new one
_last_notif = TTLCache(maxsize=20000, ttl=60 * 60 * 24 * 2)

class AntiSpamMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        # Ignore anti-spam for main menu reply buttons to prevent ghosting
        if isinstance(event, Message) and event.text and event.text in ALL_MENU_BUTTONS:
            return await handler(event, data)
        # Игнорируем анти-спам для инлайн кнопок главного меню
        if isinstance(event, CallbackQuery) and event.data and event.data.startswith("main_menu_"):
            return await handler(event, data)
            
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
                    # Показываем уведомление сверху (toast), а не всплывающим окном
                    await event.answer(t("spam_warning", lang), show_alert=False)
            return
            
        # Register the action
        spam_cache[user_id] = True
        return await handler(event, data)

dp.message.middleware(AntiSpamMiddleware())
dp.callback_query.middleware(AntiSpamMiddleware())
dp.include_router(router)


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


def get_main_menu_inline(lang: str = "ru", role: str = "student", is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=t("menu_schedule", lang), callback_data="main_menu_schedule"),
            InlineKeyboardButton(text="⏰ " + ("Таймер" if lang == "ru" else "Таймер"), callback_data="main_menu_timer"),
        ],
        [
            InlineKeyboardButton(text=t("menu_profile", lang), callback_data="main_menu_profile"),
            InlineKeyboardButton(text=t("menu_settings", lang), callback_data="main_menu_settings"),
        ],
        [
            InlineKeyboardButton(text=t("menu_help", lang), callback_data="main_menu_help"),
        ],
    ]
    
    if role == "teacher":
        rows.append([
            InlineKeyboardButton(text=t("menu_gen_student_code", lang), callback_data="main_menu_gen_student_code"),
            InlineKeyboardButton(text=t("menu_send_class", lang), callback_data="main_menu_send_class"),
        ])
        rows.append([
            InlineKeyboardButton(text=t("menu_my_codes", lang), callback_data="main_menu_my_codes"),
        ])
    elif role == "zavuch" or is_admin: 
        rows.append([
            InlineKeyboardButton(text=t("menu_gen_student_code", lang), callback_data="main_menu_gen_student_code"),
            InlineKeyboardButton(text=t("menu_gen_teacher_code", lang), callback_data="main_menu_gen_teacher_code"),
        ])
        rows.append([
            InlineKeyboardButton(text=t("menu_send_all", lang), callback_data="main_menu_send_all"),
            InlineKeyboardButton(text=t("menu_send_class_zavuch", lang), callback_data="main_menu_send_class_zavuch"),
        ])
        rows.append([
            InlineKeyboardButton(text=t("menu_my_codes", lang), callback_data="main_menu_my_codes"),
            InlineKeyboardButton(text=t("menu_bell_mode", lang), callback_data="main_menu_bell_mode"),
        ])
        rows.append([
            InlineKeyboardButton(text=t("menu_edit_schedule", lang), callback_data="main_menu_edit_schedule"),
            InlineKeyboardButton(text=t("menu_stats", lang), callback_data="main_menu_stats"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def menu_for_user_inline(user: dict) -> InlineKeyboardMarkup:
    tg_id = user.get("tg_id") or user.get("user_id")
    is_admin = (tg_id == ADMIN_ID)
    return get_main_menu_inline(user.get("lang", "ru"), user.get("role", "student"), is_admin=is_admin)


def make_invite_link(code: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start={code}"


async def set_bot_commands(b: Bot):
    commands_ru = [
        BotCommand(command="start", description="🔄 Перезапуск"),
        BotCommand(command="menu", description="📱 Главное меню")
    ]
    commands_kk = [
        BotCommand(command="start", description="🔄 Қайта бастау"),
        BotCommand(command="menu", description="📱 Басты мәзір")
    ]
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
        msg = await message.answer(
            t("already_registered", lang) + "\n\n<i>Открываю главное меню...</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=menu_for_user_inline(existing),
        )
        await state.update_data(main_msg_id=msg.message_id)
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

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы.\nВведите /start", reply_markup=ReplyKeyboardRemove())
        return
    
    lang = user.get("lang", "ru")
    text = "🌟 <b>Главное меню</b> 🌟" if lang == "ru" else "🌟 <b>Басты мәзір</b> 🌟"
    msg = await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=menu_for_user_inline(user))
    await state.update_data(main_msg_id=msg.message_id)


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
            text_msg = t(f"code_accepted_{role}", lang).format(class_code=format_class(code_data.get("class_code", "")))
            text_msg += "\n\n"
            text_msg += t("ask_name_student", lang) if role == "student" else t("ask_name_teacher", lang)
            
            await callback.message.edit_text(text_msg, parse_mode=ParseMode.HTML)
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
    text_msg = t(f"code_accepted_{role}", lang).format(class_code=format_class(code_data.get("class_code", "")))
    text_msg += "\n\n"
    text_msg += t("ask_name_student", lang) if role == "student" else t("ask_name_teacher", lang)
    
    await message.answer(text_msg, parse_mode=ParseMode.HTML)
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
    msg = await message.answer(
        t("registration_done", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=menu_for_user_inline(user),
    )
    await state.clear()
    await state.update_data(main_msg_id=msg.message_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📅 РАСПИСАНИЕ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_schedule")
async def cmd_schedule(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    lang = user["lang"]
    bell_mode = get_setting("bell_mode", "standard")
    weekday = get_weekday_almaty()
    now_time = get_now_almaty()
    show_day = weekday
    is_tomorrow = False

    # Уроки по расписанию заканчиваются примерно к 15:00, 
    # поэтому показываем расписание следующего дня после 15:00
    if now_time >= "15:00":
        if weekday >= 4:      # Пятница, Суббота, Воскресенье → Понедельник
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
        await callback.message.edit_text(t("no_lessons", lang), parse_mode=ParseMode.HTML, reply_markup=menu_for_user_inline(user))
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
    # Fallback keys since old ones might not exist directly
    header_text_ru = "📅 Расписание на завтра:\n\n{lessons}" if is_tomorrow else "📅 Расписание на сегодня:\n\n{lessons}"
    header_text_kk = "📅 Ертеңгі сабақ кестесі:\n\n{lessons}" if is_tomorrow else "📅 Бүгінгі сабақ кестесі:\n\n{lessons}"
    
    text_template = header_text_ru if lang == "ru" else header_text_kk
    text = text_template.format(lessons="\n".join(lines))
    
    kb_rows = [
        [InlineKeyboardButton(text="📅 Вся неделя" if lang == "ru" else "📅 Бүкіл апта", callback_data="main_menu_schedule_week")],
    ]
    kb_rows.append([InlineKeyboardButton(text="🔙 " + ("Назад" if lang == "ru" else "Артқа"), callback_data="main_menu_profile")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👤 ПРОФИЛЬ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_profile")
async def cmd_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
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
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=menu_for_user_inline(user))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ НАСТРОЙКИ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_settings")
async def cmd_settings(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    lang = user["lang"]
    new_lang = "kk" if lang == "ru" else "ru"
    kb_rows = [
        [InlineKeyboardButton(
            text=f"{LANG_LABEL[new_lang]}",
            callback_data=f"set_lang_{new_lang}",
        )]
    ]
    
    tg_id = user.get("tg_id") or user.get("user_id")
    if str(tg_id) == str(ADMIN_ID) or user.get("role") == "zavuch":
        agg_warn = get_setting("aggressive_warning", "off")
        agg_warn_text = t("setting_aggressive_warn_on", lang) if agg_warn == "on" else t("setting_aggressive_warn_off", lang)
        kb_rows.append([InlineKeyboardButton(text=agg_warn_text, callback_data="toggle_agg_warn")])

    kb_rows.append([InlineKeyboardButton(
        text="🔔 " + ("Уведомления" if lang == "ru" else "Хабарламалар"),
        callback_data="notif_settings",
    )])
    # Append a "Back to Menu" button for settings
    kb_rows.append([InlineKeyboardButton(text="🔙 " + ("Назад в меню" if lang == "ru" else "Мәзірге қайту"), callback_data="main_menu_profile")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(
        t("settings_text", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )

@router.callback_query(F.data == "toggle_agg_warn")
async def toggle_agg_warn_callback(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        return
    tg_id = user.get("tg_id") or user.get("user_id")
    if str(tg_id) != str(ADMIN_ID) and user.get("role") != "zavuch":
        await callback.answer("Нет прав", show_alert=True)
        return
        
    current = get_setting("aggressive_warning", "off")
    new_val = "on" if current == "off" else "off"
    set_setting("aggressive_warning", new_val)
    
    await callback.answer(t("aggressive_warn_toggled", user["lang"]))
    
    lang = user["lang"]
    new_lang = "kk" if lang == "ru" else "ru"
    kb_rows = [
        [InlineKeyboardButton(
            text=f"{LANG_LABEL[new_lang]}",
            callback_data=f"set_lang_{new_lang}",
        )]
    ]
    agg_warn_text = t("setting_aggressive_warn_on", lang) if new_val == "on" else t("setting_aggressive_warn_off", lang)
    kb_rows.append([InlineKeyboardButton(text=agg_warn_text, callback_data="toggle_agg_warn")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    try:
        await callback.message.edit_text(
            t("settings_text", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
    except Exception:
        pass


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
        reply_markup=menu_for_user_inline(user)
    )
    await callback.answer()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔔 НАСТРОЙКИ УВЕДОМЛЕНИЙ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NOTIF_KEYS = [
    ("notif_start", "notif_start_label"),
    ("notif_end", "notif_end_label"),
    ("notif_warning", "notif_warning_label"),
]


def _build_notif_kb(tg_id: int, lang: str) -> InlineKeyboardMarkup:
    """Build the notification settings keyboard with current toggle states."""
    settings = get_user_settings_bulk([tg_id], [key for key, _ in NOTIF_KEYS]).get(tg_id, {})
    kb_rows = []
    for key, label_key in NOTIF_KEYS:
        current = settings.get(key, "on")
        icon = "✅" if current == "on" else "❌"
        kb_rows.append([InlineKeyboardButton(
            text=f"{icon} {t(label_key, lang)}",
            callback_data=f"toggle_notif_{key}",
        )])
    kb_rows.append([InlineKeyboardButton(
        text="🔙 " + ("Назад" if lang == "ru" else "Артқа"),
        callback_data="main_menu_settings",
    )])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.callback_query(F.data == "notif_settings")
async def notif_settings(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    lang = user["lang"]
    kb = _build_notif_kb(callback.from_user.id, lang)
    await callback.message.edit_text(t("notif_settings_title", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_notif_"))
async def toggle_notif(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        return
    lang = user["lang"]
    key = callback.data.replace("toggle_notif_", "")  # e.g. "notif_start"
    current = get_user_setting(callback.from_user.id, key, "on")
    new_val = "off" if current == "on" else "on"
    set_user_setting(callback.from_user.id, key, new_val)
    kb = _build_notif_kb(callback.from_user.id, lang)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer(t("notif_updated", lang))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📅 РАСПИСАНИЕ НА НЕДЕЛЮ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_schedule_week")
async def schedule_week(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    lang = user["lang"]
    class_code = user.get("class_code", "")
    day_names = DAY_NAMES_RU if lang == "ru" else DAY_NAMES_KK
    bell_mode = get_setting("bell_mode", "standard")

    lines = [t("schedule_week_title", lang)]
    for day_idx in range(6):  # Mon-Sat
        day_lessons = get_lessons(class_code, day_idx)
        shifts = get_shifts(bell_mode, day_idx)
        shift_data = shifts.get(user["shift"], {})
        lines.append(f"\n📆 <b>{day_names[day_idx]}</b>")
        if not day_lessons:
            lines.append("   —")
            continue
        for ls in day_lessons:
            num = ls["lesson_num"]
            time_info = shift_data.get(num, {})
            start = time_info.get("start", "")
            end = time_info.get("end", "")

            lesson_name = ls["lesson_name"]
            if lang == "ru":
                from translations import LESSON_TRANSLATIONS
                lesson_name = LESSON_TRANSLATIONS.get(lesson_name, lesson_name)

            time_str = f"  <i>{start}–{end}</i>" if start else ""
            lines.append(f"   {num}. {lesson_name}{time_str}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 " + ("Назад" if lang == "ru" else "Артқа"), callback_data="main_menu_schedule")],
    ])
    await callback.message.edit_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⏰ ТАЙМЕР УРОКА
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_timer")
async def lesson_timer(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Not registered", show_alert=True)
        return
    lang = user["lang"]
    weekday = get_weekday_almaty()

    if weekday >= 6:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 " + ("Назад" if lang == "ru" else "Артқа"), callback_data="main_menu_profile")],
        ])
        await callback.message.edit_text(t("timer_weekend", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
        await callback.answer()
        return

    bell_mode = get_setting("bell_mode", "standard")
    shifts = get_shifts(bell_mode, weekday)
    shift_data = shifts.get(user["shift"], {})
    now_time = get_now_almaty()
    class_code = user.get("class_code", "")

    lessons_map = {l["lesson_num"]: l["lesson_name"] for l in get_lessons(class_code, weekday)}
    if lang == "ru":
        from translations import LESSON_TRANSLATIONS
        lessons_map = {k: LESSON_TRANSLATIONS.get(v, v) for k, v in lessons_map.items()}

    # Parse current time
    now_h, now_m = map(int, now_time.split(":"))
    now_minutes = now_h * 60 + now_m

    # Sort lessons by start time
    sorted_lessons = sorted(shift_data.items(), key=lambda x: x[1]["start"])

    text = None
    for lesson_num, times in sorted_lessons:
        s_h, s_m = map(int, times["start"].split(":"))
        e_h, e_m = map(int, times["end"].split(":"))
        start_min = s_h * 60 + s_m
        end_min = e_h * 60 + e_m

        if now_minutes < start_min:
            # Before this lesson starts
            remaining = start_min - now_minutes
            if lesson_num == sorted_lessons[0][0]:
                text = t("timer_not_started", lang).format(mins=remaining)
            else:
                text = t("timer_in_break", lang).format(num=lesson_num, mins=remaining)
            break

        if start_min <= now_minutes < end_min:
            # Currently in this lesson
            remaining = end_min - now_minutes
            name = lessons_map.get(lesson_num, f"Урок {lesson_num}")
            text = t("timer_in_lesson", lang).format(
                num=lesson_num,
                name=name,
                start=times["start"],
                end=times["end"],
                mins=remaining,
            )
            break

    if text is None:
        text = t("timer_no_lessons", lang)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 " + ("Обновить" if lang == "ru" else "Жаңарту"), callback_data="main_menu_timer")],
        [InlineKeyboardButton(text="🔙 " + ("Назад" if lang == "ru" else "Артқа"), callback_data="main_menu_profile")],
    ])
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🆘 ПОМОЩЬ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_help")
async def cmd_help(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user:
        await callback.message.edit_text("Введите /start для регистрации.")
        await callback.answer()
        return
    lang = user["lang"] if user else "ru"
    await callback.message.edit_text(t("help_text", lang), parse_mode=ParseMode.HTML, reply_markup=menu_for_user_inline(user))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  РЕЖИМ ЗВОНКОВ (только завуч)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_bell_mode")
async def btn_bell_mode(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user or (user["role"] != "zavuch" and callback.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await callback.answer(t("no_permission", lang), show_alert=True)
        return
    lang = user["lang"]
    current_mode = get_setting("bell_mode", "standard")
    current_label = t(BELL_MODE_LABEL.get(current_mode, "bell_standard"), lang)
    kb_rows = [
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
        [InlineKeyboardButton(text="🔙 " + ("Назад", "Мәзірге")[lang=="kk"], callback_data="main_menu_profile")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(
        t("bell_mode_status", lang).format(current=current_label),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@router.callback_query(F.data.in_({"bell_set_standard", "bell_set_short", "bell_set_custom"}))
async def process_bell_mode(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user or (user["role"] != "zavuch" and callback.from_user.id != ADMIN_ID):
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


@router.callback_query(F.data == "main_menu_stats")
async def btn_stats(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user or (user["role"] != "zavuch" and callback.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await callback.answer(t("no_permission", lang), show_alert=True)
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
            
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu_profile")]])
    await callback.message.edit_text(res, parse_mode=ParseMode.HTML, reply_markup=kb)



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✏️ ИЗМЕНЕНИЕ РАСПИСАНИЯ (INLINE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.callback_query(F.data == "main_menu_edit_schedule")
async def btn_edit_schedule_inline(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user or (user["role"] != "zavuch" and callback.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await callback.answer(t("no_permission", lang), show_alert=True)
        return
        
    lang = user["lang"]
    from db import get_all_classes
    classes = get_all_classes()
    
    kb_rows = []
    row = []
    for c in classes:
        row.append(InlineKeyboardButton(text=c, callback_data=c))
        if len(row) == 3:
            kb_rows.append(row)
            row = []
    if row:
        kb_rows.append(row)
    
    kb_rows.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu_profile")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await callback.message.edit_text("Для какого класса вы хотите изменить расписание? (Выберите из списка)", reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(EditScheduleInline.choosing_class)

@router.callback_query(StateFilter(EditScheduleInline.choosing_class))
async def edit_schedule_inline_select_class(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    class_code = callback.data.strip()
    
    # Check if they pressed cancel / back
    if class_code == "main_menu_profile":
        await state.clear()
        await cmd_profile(callback, state)
        return
        
    await state.update_data(edit_class=class_code)
    days = DAY_NAMES_RU if lang == "ru" else DAY_NAMES_KK
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=days[0], callback_data="es_day_0"), InlineKeyboardButton(text=days[1], callback_data="es_day_1")],
        [InlineKeyboardButton(text=days[2], callback_data="es_day_2"), InlineKeyboardButton(text=days[3], callback_data="es_day_3")],
        [InlineKeyboardButton(text=days[4], callback_data="es_day_4"), InlineKeyboardButton(text=days[5], callback_data="es_day_5")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu_profile")]
    ])
    msg_text = f"Выбран класс: <b>{class_code}</b>\n\nВыберите день недели:"
    await callback.message.edit_text(msg_text, reply_markup=kb, parse_mode=ParseMode.HTML)

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
    kb_rows.append([InlineKeyboardButton(text="❌ Выйти", callback_data="es_cancel")])
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
        [InlineKeyboardButton(text="❌ Выйти", callback_data="es_cancel")],
    ])
    await callback.message.edit_text("Выберите день недели:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "es_cancel")
async def edit_schedule_inline_cancel(callback: CallbackQuery, state: FSMContext):
    await cmd_profile(callback, state)

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
        try:
            main_msg_id = data.get("main_msg_id")
            await message.delete()
            if main_msg_id:
                await bot.edit_message_text(chat_id=message.from_user.id, message_id=main_msg_id, text="🚫", reply_markup=menu_for_user_inline(user))
        except Exception:
            pass
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
    
    await state.set_state(None)
    
    try:
        main_msg_id = data.get("main_msg_id")
        text_content = f"✅ Вручную сохранено: {subj_name}\n\n📆 <b>{days[day_idx]}</b> ({class_code})\nВыберите урок для изменения:"
        if main_msg_id:
            await bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=main_msg_id,
                text=text_content,
                reply_markup=kb,
                parse_mode=ParseMode.HTML
            )
        else:
            msg = await message.answer(text_content, reply_markup=kb, parse_mode=ParseMode.HTML)
            await state.update_data(main_msg_id=msg.message_id)
    except Exception:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔑 ГЕНЕРАЦИЯ КОДОВ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_gen_teacher_code")
async def btn_gen_teacher_code(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user or (user["role"] != "zavuch" and callback.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await callback.answer(t("no_permission", lang), show_alert=True)
        return
    await state.update_data(gen_role="teacher", gen_reusable=False)
    lang = user["lang"]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu_profile")]])
    await callback.message.edit_text(t("gen_code_ask_class", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.set_state(GenCode.entering_class_code)


@router.callback_query(F.data == "main_menu_gen_student_code")
async def btn_gen_student_code(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user or user["role"] not in ("zavuch", "teacher"):
        lang = user["lang"] if user else "ru"
        await callback.answer(t("no_permission", lang), show_alert=True)
        return
    lang = user["lang"]
    if user["role"] == "teacher" and user.get("class_code"):
        code = create_invite_code(
            role="student",
            class_code=user["class_code"],
            shift=user["shift"],
            created_by=callback.from_user.id,
            reusable=True,
        )
        link = make_invite_link(code)
        role_label = t("role_student", lang)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu_profile")]])
        await callback.message.edit_text(
            t("code_generated", lang).format(
                role=role_label,
                class_code=user["class_code"],
                shift=user["shift"],
                code=code,
                link=link,
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        return
    await state.update_data(gen_role="student", gen_reusable=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu_profile")]])
    await callback.message.edit_text(t("gen_code_ask_class", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
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
        ],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu_profile")]
    ])
    try:
        data = await state.get_data()
        main_msg_id = data.get("main_msg_id")
        await message.delete()
        if main_msg_id:
            await bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=main_msg_id,
                text=t("gen_code_ask_shift", lang),
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        else:
            msg = await message.answer(t("gen_code_ask_shift", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
            await state.update_data(main_msg_id=msg.message_id)
    except Exception as e:
        logger.error(f"Error in gen_code_class: {e}")
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
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu_profile")]])
    await callback.message.edit_text(
        t("code_generated", lang).format(
            role=role_label,
            class_code=class_code,
            shift=shift,
            code=code,
            link=link,
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    await callback.answer()
    await state.clear()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📋 МОИ КОДЫ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_my_codes")
async def btn_my_codes(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user or (user["role"] not in ("teacher", "zavuch") and callback.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await callback.answer(t("no_permission", lang), show_alert=True)
        return
    lang = user["lang"]
    codes = get_active_codes_by_creator(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu_profile")]])
    if not codes:
        await callback.message.edit_text(t("no_codes", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
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
    await callback.message.edit_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=kb)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📢 РАССЫЛКА с подтверждением
# Завуч → всем | Завуч → классу | Учитель → своему классу
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.callback_query(F.data == "main_menu_send_all")
async def btn_send_all(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user or (user["role"] != "zavuch" and callback.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await callback.answer(t("no_permission", lang), show_alert=True)
        return
    lang = user["lang"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu_profile")]])
    await callback.message.edit_text(t("send_all_prompt", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.set_state(Broadcast.waiting_text_all)


@router.message(Broadcast.waiting_text_all)
async def broadcast_all_confirm(message: Message, state: FSMContext):
    if not message.text:
        return
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    all_users = get_all_users()
    preview = message.text[:200] + ("..." if len(message.text) > 200 else "")
    sender_username = f"@{message.from_user.username}" if message.from_user.username else user["full_name"]
    await state.update_data(
        broadcast_text=message.text, 
        broadcast_target="all",
        broadcast_sender_name=sender_username
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_confirm_send", lang), callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text=t("btn_cancel_send", lang), callback_data="broadcast_cancel")],
    ])
    
    try:
        data = await state.get_data()
        main_msg_id = data.get("main_msg_id")
        await message.delete()
        text_content = t("broadcast_confirm", lang).format(count=len(all_users), text=preview)
        if main_msg_id:
            await bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=main_msg_id,
                text=text_content,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        else:
            msg = await message.answer(text_content, parse_mode=ParseMode.HTML, reply_markup=kb)
            await state.update_data(main_msg_id=msg.message_id)
    except Exception as e:
        logger.error(f"Error in broadcast_all_confirm: {e}")


@router.callback_query(F.data == "main_menu_send_class")
async def btn_send_class_teacher(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if not user or user["role"] != "teacher":
        lang = user["lang"] if user else "ru"
        await callback.answer(t("no_permission", lang), show_alert=True)
        return
    lang = user["lang"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu_profile")]])
    await callback.message.edit_text(t("send_class_prompt", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
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
    sender_username = f"@{message.from_user.username}" if message.from_user.username else user["full_name"]
    await state.update_data(
        broadcast_text=message.text,
        broadcast_target="class",
        broadcast_class=user["class_code"],
        broadcast_sender_name=sender_username,
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_confirm_send", lang), callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text=t("btn_cancel_send", lang), callback_data="broadcast_cancel")],
    ])
    
    try:
        data = await state.get_data()
        main_msg_id = data.get("main_msg_id")
        await message.delete()
        text_content = t("broadcast_confirm", lang).format(count=len(class_users), text=preview)
        if main_msg_id:
            await bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=main_msg_id,
                text=text_content,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        else:
            msg = await message.answer(text_content, parse_mode=ParseMode.HTML, reply_markup=kb)
            await state.update_data(main_msg_id=msg.message_id)
    except Exception as e:
        logger.error(f"Error in broadcast_class_confirm: {e}")


# ━━ Завуч → конкретный класс ━━


@router.callback_query(F.data == "main_menu_send_class_zavuch")
async def btn_send_class_zavuch(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    if not user or (user["role"] != "zavuch" and callback.from_user.id != ADMIN_ID):
        lang = user["lang"] if user else "ru"
        await callback.answer(t("no_permission", lang), show_alert=True)
        return
    lang = user["lang"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu_profile")]])
    await callback.message.edit_text(t("send_class_ask", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
    await state.set_state(Broadcast.waiting_class_code_zavuch)


@router.message(Broadcast.waiting_class_code_zavuch)
async def broadcast_zavuch_class_code(message: Message, state: FSMContext):
    if not message.text:
        return
    user = get_user(message.from_user.id)
    lang = user["lang"] if user else "ru"
    class_code = message.text.strip().upper()
    await state.update_data(broadcast_class=class_code, broadcast_sender_name=user["full_name"])
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu_profile")]])
    try:
        data = await state.get_data()
        main_msg_id = data.get("main_msg_id")
        await message.delete()
        if main_msg_id:
            await bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=main_msg_id,
                text=t("send_class_prompt", lang),
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        else:
            msg = await message.answer(t("send_class_prompt", lang), parse_mode=ParseMode.HTML, reply_markup=kb)
            await state.update_data(main_msg_id=msg.message_id)
    except Exception as e:
        logger.error(f"Error in broadcast_zavuch_class_code: {e}")
        
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
    
    try:
        main_msg_id = data.get("main_msg_id")
        await message.delete()
        text_content = t("broadcast_confirm", lang).format(count=len(class_users), text=preview)
        if main_msg_id:
            await bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=main_msg_id,
                text=text_content,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        else:
            msg = await message.answer(text_content, parse_mode=ParseMode.HTML, reply_markup=kb)
            await state.update_data(main_msg_id=msg.message_id)
    except Exception as e:
        logger.error(f"Error in broadcast_zavuch_class_confirm: {e}")


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
        sender_name = data.get("broadcast_sender_name", "Администратор")
        format_args = lambda u_lang: {"name": sender_name, "text": text}
    else:
        class_code = data.get("broadcast_class", "")
        recipients = get_users_by_class(class_code)
        sender_name = data.get("broadcast_sender_name", "Учитель")
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
        
    kb_rows = [[InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu_profile")]]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(result, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user["lang"] if user else "ru"
    kb_rows = [[InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu_profile")]]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await callback.message.edit_text(
        t("broadcast_cancelled", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    await callback.answer()
    await state.clear()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CATCH-ALL: кнопка меню во время FSM → отмена
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.in_(ALL_MENU_BUTTONS))
async def legacy_menu_fallback(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Введите /start", reply_markup=ReplyKeyboardRemove())
        return
        
    lang = user.get("lang", "ru")
    await message.answer(
        "🔄 Интерфейс обновлён! Убираю старую клавиатуру..." if lang == "ru" else "🔄 Интерфейс жаңартылды! Ескі пернетақтаны алып тастау...", 
        reply_markup=ReplyKeyboardRemove()
    )
    
    text = "🌟 <b>Главное меню</b> 🌟" if lang == "ru" else "🌟 <b>Басты мәзір</b> 🌟"
    msg2 = await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=menu_for_user_inline(user))
    await state.update_data(main_msg_id=msg2.message_id)

@router.message()
async def any_other_message(message: Message):
    # Ignore unhandled text to prevent console spam
    pass


@router.callback_query()
async def catch_all_callbacks(callback: CallbackQuery):
    """Fallback handler for old or unhandled inline buttons to stop loading spinners."""
    try:
        await callback.answer("Эта кнопка больше не работает.", show_alert=False)
    except Exception:
        pass


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
            shifts = get_shifts(bell_mode, weekday)

            triggered_events = []
            for shift_num, shift_lessons in shifts.items():
                for lesson_num, times in shift_lessons.items():
                    start_time = times.get("start")
                    end_time = times.get("end")
                    pre_lesson_time = ""
                    if start_time:
                        try:
                            start_dt = datetime.strptime(start_time, "%H:%M")
                            pre_lesson_time = (start_dt - timedelta(minutes=2)).strftime("%H:%M")
                        except Exception:
                            pre_lesson_time = ""

                    if now_time == start_time:
                        triggered_events.append((shift_num, lesson_num, "start", times))
                    if now_time == end_time:
                        triggered_events.append((shift_num, lesson_num, "end", times))
                    if pre_lesson_time and now_time == pre_lesson_time:
                        triggered_events.append((shift_num, lesson_num, "warning", times))

            # Skip expensive DB calls when there are no notifications to send this minute.
            if not triggered_events:
                continue

            all_users = get_all_users()
            if not all_users:
                continue

            users_by_shift: dict[int, list[dict]] = {}
            users_with_class_ids: list[int] = []
            for user in all_users:
                shift_num = user.get("shift")
                users_by_shift.setdefault(shift_num, []).append(user)
                if user.get("class_code"):
                    users_with_class_ids.append(user["tg_id"])

            notif_settings = get_user_settings_bulk(
                users_with_class_ids,
                ["notif_start", "notif_end", "notif_warning"],
            )
            aggressive_warning = (
                get_setting("aggressive_warning", "off")
                if any(event_type == "warning" for _, _, event_type, _ in triggered_events)
                else "off"
            )

            # Оптимизация: кешируем уроки для каждого класса на эту итерацию
            class_lessons_cache = {}

            for shift_num, lesson_num, event_type, times in triggered_events:
                shift_users = users_by_shift.get(shift_num, [])
                if not shift_users:
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

                    # ── Проверка пользовательских настроек уведомлений ──
                    uid = user["tg_id"]
                    user_notif = notif_settings.get(uid, {})
                    if event_type == "start" and user_notif.get("notif_start", "on") == "off":
                        continue
                    if event_type == "end" and user_notif.get("notif_end", "on") == "off":
                        continue
                    if event_type == "warning" and user_notif.get("notif_warning", "on") == "off":
                        continue

                    lang = user["lang"]
                    if event_type == "start":
                        text = t("lesson_start", lang).format(
                            num=lesson_num,
                            name=lessons_map[lesson_num],
                            start=times["start"],
                            end=times["end"],
                        )
                    elif event_type == "warning":
                        if aggressive_warning == "on":
                            text = t("lesson_warning_aggressive", lang).format(
                                num=lesson_num,
                                name=lessons_map[lesson_num],
                            )
                        else:
                            text = t("lesson_warning", lang).format(
                                num=lesson_num,
                                name=lessons_map[lesson_num],
                            )
                    else:  # end
                        text = t("lesson_end", lang).format(num=lesson_num)

                    try:
                        platform = user.get("platform", "telegram")
                        # Delete old notification to keep chat clean
                        if platform == "telegram" and uid in _last_notif:
                            try:
                                await bot.delete_message(uid, _last_notif[uid])
                            except Exception:
                                pass  # message already deleted or too old

                        if platform == "telegram":
                            msg = await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
                            _last_notif[uid] = msg.message_id
                        else:
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
# ERROR HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.errors()
async def global_error_handler(event: ErrorEvent):
    if isinstance(event.exception, TelegramBadRequest):
        if "message is not modified" in str(event.exception).lower():
            # User clicked the same inline button, safely ignore
            return
    # Log other unhandled exceptions
    logger.error(f"Update {event.update.update_id} caused error: {event.exception}", exc_info=True)


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

    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
