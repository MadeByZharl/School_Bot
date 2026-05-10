"""🥚 Пасхалки: изолированные команды и реакции на ключевые слова.

Все хендлеры этого модуля не зависят от state/кешей основного бота — достаточно
того, что они умеют отвечать на message. Регистрируется в main через include_router.
"""
import asyncio
import random as _rng

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from db import get_user

router = Router()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Команды
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(Command("hack"))
async def easter_hack(message: Message):
    """Fake hacking animation."""
    msg = await message.answer("🖥 <code>Инициализация взлома...</code>", parse_mode=ParseMode.HTML)
    await asyncio.sleep(1)
    await msg.edit_text("🖥 <code>Инициализация взлома...\n[██░░░░░░░░] 15%</code>", parse_mode=ParseMode.HTML)
    await asyncio.sleep(1)
    await msg.edit_text("🖥 <code>Инициализация взлома...\n[████░░░░░░] 40%\nОбход файрвола школы...</code>", parse_mode=ParseMode.HTML)
    await asyncio.sleep(1)
    await msg.edit_text("🖥 <code>Инициализация взлома...\n[███████░░░] 70%\nОбход файрвола школы...\nВзлом оценок...</code>", parse_mode=ParseMode.HTML)
    await asyncio.sleep(1)
    await msg.edit_text("🖥 <code>Инициализация взлома...\n[██████████] 99%\nОбход файрвола школы...\nВзлом оценок...\n\n⚠️ ОБНАРУЖЕН ЗАВУЧ!</code>", parse_mode=ParseMode.HTML)
    await asyncio.sleep(1)
    await msg.edit_text("😂 <b>Шучу!</b>\n\nУчи уроки, хакер 📚", parse_mode=ParseMode.HTML)


@router.message(Command("coin"))
async def easter_coin(message: Message):
    result = _rng.choice(["🪙 <b>Орёл!</b>", "🪙 <b>Решка!</b>", "😱 <b>Монетка встала на ребро!</b> (1 из 6000)"])
    await message.answer(result, parse_mode=ParseMode.HTML)


@router.message(Command("dice"))
async def easter_dice(message: Message):
    faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    n = _rng.randint(0, 5)
    await message.answer(f"🎲 {faces[n]} — выпало <b>{n+1}</b>!", parse_mode=ParseMode.HTML)


@router.message(Command("8ball"))
async def easter_8ball(message: Message):
    answers = [
        "🎱 Однозначно да!",
        "🎱 Скорее да",
        "🎱 Без сомнений!",
        "🎱 Спроси у завуча 😏",
        "🎱 Не сейчас...",
        "🎱 Даже не думай",
        "🎱 100%!",
        "🎱 Лучше подготовься к уроку",
        "🎱 Звёзды говорят — да ⭐",
        "🎱 Пятёрка обеспечена!",
        "🎱 Нет, и домашку сделай",
        "🎱 Попробуй после каникул",
    ]
    await message.answer(_rng.choice(answers))


@router.message(Command("wisdom"))
async def easter_wisdom(message: Message):
    wisdoms = [
        "📖 <i>«Образование — лучший друг. Образованного человека уважают везде.»</i>\n— Чанакья",
        "🧠 <i>«Учись так, словно будешь жить вечно.»</i>\n— Махатма Ганди",
        "🎓 <i>«Корень учения горек, а плод его сладок.»</i>\n— Аристотель",
        "💡 <i>«Знание — сила.»</i>\n— Фрэнсис Бэкон",
        "🌟 <i>«Тот, кто учится, но не думает — потерян.»</i>\n— Конфуций",
        "📚 <i>«Я знаю, что ничего не знаю.»</i>\n— Сократ",
        "🔥 <i>«Нет ничего невозможного. Само слово говорит «Я возможно!»»</i>\n— Одри Хепбёрн",
        "⏰ <i>«Не откладывай на завтра то, что можно сделать сегодня.»</i>\n— Бенджамин Франклин",
    ]
    await message.answer(_rng.choice(wisdoms), parse_mode=ParseMode.HTML)


@router.message(Command("rate"))
async def easter_rate(message: Message):
    """Random grade generator."""
    grade = _rng.choices([2, 3, 4, 5], weights=[5, 15, 35, 45])[0]
    emojis = {2: "💀", 3: "😬", 4: "😊", 5: "🔥"}
    comments = {
        2: "Ну... бывает. Учебник открой хотя бы 📖",
        3: "Тройка — стабильность! Но можно лучше 💪",
        4: "Хорошо! Чуть-чуть до пятёрки! ✨",
        5: "ОТЛИЧНО! Ты гений! 🧠👑",
    }
    await message.answer(
        f"{emojis[grade]} Твоя оценка: <b>{grade}</b>\n\n<i>{comments[grade]}</i>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("excuse"))
async def easter_excuse(message: Message):
    excuses = [
        "🐕 Собака съела мою домашку!",
        "💻 Компьютер обновлялся 12 часов...",
        "👽 Инопланетяне похитили мою тетрадь",
        "🌪 Ветер унёс листочки по дороге в школу",
        "🔋 Телефон сел, а домашка была в нём",
        "😴 Я делал домашку во сне, но забыл записать",
        "🧊 Тетрадь замёрзла на морозе и текст исчез",
        "📱 WhatsApp не загрузил фото задания",
        "🤖 ИИ сказал что домашка необязательная",
        "⚡ Свет выключили ровно в 20:00",
        "🎮 Мне нужно было спасти мир в Minecraft",
        "📚 Я читал другой учебник... случайно...",
    ]
    await message.answer(
        f"📝 <b>Отмазка дня:</b>\n\n<i>{_rng.choice(excuses)}</i>\n\n⚠️ <i>Мы не несём ответственности за последствия</i>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("rps"))
async def easter_rps(message: Message):
    bot_choice = _rng.choice(["камень", "ножницы", "бумага"])
    emojis = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}
    await message.answer(
        f"Я выбрал: {emojis[bot_choice]} <b>{bot_choice}</b>!\n\n"
        f"Напиши камень, ножницы или бумагу в ответ ✊✌️🖐",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("love"))
async def easter_love(message: Message):
    percent = _rng.randint(1, 100)
    if percent < 20:
        bar, comment = "💔💔💔💔💔", "Не судьба... 😢"
    elif percent < 50:
        bar, comment = "❤️💔💔💔💔", "Есть шанс! 🤞"
    elif percent < 75:
        bar, comment = "❤️❤️❤️💔💔", "Почти! 😍"
    elif percent < 95:
        bar, comment = "❤️❤️❤️❤️💔", "Любовь витает в воздухе! 💕"
    else:
        bar, comment = "❤️❤️❤️❤️❤️", "ИДЕАЛЬНАЯ ПАРА! 💍"

    await message.answer(
        f"💘 <b>Калькулятор любви</b>\n\n"
        f"{bar}\n"
        f"Совместимость: <b>{percent}%</b>\n\n"
        f"<i>{comment}</i>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("who"))
async def easter_who(message: Message):
    things = [
        "будет отвечать у доски",
        "забудет домашку",
        "получит пятёрку",
        "уснёт на уроке",
        "станет директором",
        "будет миллионером",
        "выиграет олимпиаду",
        "опоздает завтра",
        "съест в столовой 3 порции",
        "первым сдаст контрольную",
    ]
    await message.answer(
        f"🎯 <b>Кто сегодня {_rng.choice(things)}?</b>\n\n"
        f"<i>Отправь это в групповой чат и узнай! 😏</i>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("fact"))
async def easter_fact(message: Message):
    facts = [
        "🧠 Мозг потребляет 20% всей энергии тела, хотя весит всего 2%",
        "📚 Самая длинная книга — «В поисках утраченного времени» — 9 609 000 символов",
        "🔢 Число 111,111,111 × 111,111,111 = 12345678987654321",
        "🌍 В школах Финляндии нет домашних заданий до 16 лет",
        "⚡ Мозг генерирует электричество — хватит чтобы зажечь лампочку!",
        "📖 Средний ученик за 12 лет проводит в школе 15 000 часов",
        "🐙 У осьминога 3 сердца и голубая кровь",
        "🌡 Температура молнии — 30 000°C, это в 5 раз горячее Солнца",
        "🎵 Музыка помогает запоминать информацию на 40% лучше",
        "💡 Эйнштейн не мог запомнить свой номер телефона",
        "🧮 Слово «алгебра» пришло из арабского — «аль-джабр» (восстановление)",
        "🏫 Первая школа появилась в Шумере 5500 лет назад",
    ]
    await message.answer(f"💡 <b>Факт дня:</b>\n\n{_rng.choice(facts)}", parse_mode=ParseMode.HTML)


@router.message(Command("flip"))
async def easter_flip(message: Message):
    text = message.text.replace("/flip", "").strip() or "Привет"
    flip_map = str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz∀qƆpƎℲ⅁HIſʞ˥WNOԀQɹS⊥∩ΛMX⅄Z",
    )
    flipped = text.translate(flip_map)[::-1]
    await message.answer(f"🙃 {flipped}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Keyword reactions (regex-less triggers)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.lower().contains("бот ты тупой"))
async def easter_bot_stupid(message: Message):
    replies = [
        "😤 Я не тупой, я просто... <i>творческий!</i>",
        "🤖 Error 404: обида не найдена. Но домашку проверю!",
        "😎 Я бот, а ты домашку сделал?",
        "🥲 Больно. Но я всё равно покажу тебе расписание.",
    ]
    await message.answer(_rng.choice(replies), parse_mode=ParseMode.HTML)


@router.message(F.text.lower().contains("каникулы"))
async def easter_holidays(message: Message):
    await message.answer(
        "🏖 <b>Каникулы...</b>\n\n<i>*мечтательно смотрит в окно*</i>\n\nА пока — учись! 📚",
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text.lower().in_({"пятница", "жұма", "ура пятница", "friday"}))
async def easter_friday(message: Message):
    await message.answer("🎉🎉🎉\n\n<b>ПЯТНИЦА!</b>\n\nОсталось пережить уроки — и свобода! 🕺", parse_mode=ParseMode.HTML)


@router.message(F.text.lower().in_({"камень", "ножницы", "бумага"}))
async def easter_rps_play(message: Message):
    """RPS result."""
    user_choice = message.text.lower()
    bot_choice = _rng.choice(["камень", "ножницы", "бумага"])
    emojis = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}

    if user_choice == bot_choice:
        result = "🤝 <b>Ничья!</b>"
    elif (user_choice == "камень" and bot_choice == "ножницы") or \
         (user_choice == "ножницы" and bot_choice == "бумага") or \
         (user_choice == "бумага" and bot_choice == "камень"):
        result = "🎉 <b>Ты победил!</b> Красавчик!"
    else:
        result = "😈 <b>Я победил!</b> Не расстраивайся!"

    await message.answer(
        f"Ты: {emojis[user_choice]}  vs  Бот: {emojis[bot_choice]}\n\n{result}",
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text.lower().contains("домашка"))
async def easter_homework(message: Message):
    replies = [
        "📝 Домашка? Какая домашка? Я ничего не видел... 👀",
        "📚 Домашка — это добровольное приключение! ... правда?",
        "😤 Домашка придумана для того, чтобы мы не скучали!",
        "🤓 Домашка = 10% знаний, 90% страданий",
    ]
    await message.answer(_rng.choice(replies))


@router.message(F.text.lower().contains("спать"))
async def easter_sleep(message: Message):
    replies = [
        "😴 Zzz... Подожди, я тоже задремал...",
        "🛏 Сон — лучший предмет в школе!",
        "💤 8 часов сна = 5 по контрольной. Наука!",
        "😪 Если ты хочешь спать — значит мозг устал учиться. Или не начинал.",
    ]
    await message.answer(_rng.choice(replies))


@router.message(F.text.lower().contains("скучно"))
async def easter_bored(message: Message):
    replies = [
        "🥱 Скучно? Попробуй /hack — взломай школу!",
        "🎲 Скучно? Кинь /dice или /coin!",
        "🎱 Задай вопрос судьбе — /8ball",
        "📝 Скучно? Сгенерируй отмазку — /excuse",
        "💘 Скучно? Проверь любовь — /love",
        "🧠 Скучно? Узнай факт — /fact",
    ]
    await message.answer(_rng.choice(replies))


@router.message(F.text.lower().contains("спасибо"))
async def easter_thanks(message: Message):
    replies = [
        "☺️ Всегда пожалуйста!",
        "🤗 Обращайся!",
        "💪 Рад помочь!",
        "🫡 Служу школьникам!",
        "😊 Не за что! Учись на 5!",
    ]
    await message.answer(_rng.choice(replies))


@router.message(F.text.lower().in_({"привет", "салем", "хай", "hello", "hi", "сәлем"}))
async def easter_hello(message: Message):
    user = get_user(message.from_user.id)
    name = user["full_name"] if user else "друг"
    greetings = [
        f"👋 Привет, <b>{name}</b>! Как дела?",
        f"🫡 Салют, <b>{name}</b>!",
        f"✌️ Йоу, <b>{name}</b>! Готов к урокам?",
        f"😎 Здарова, <b>{name}</b>! Что новенького?",
    ]
    await message.answer(_rng.choice(greetings), parse_mode=ParseMode.HTML)


@router.message(F.text.lower().in_({"пока", "бай", "bye", "сау бол"}))
async def easter_bye(message: Message):
    replies = [
        "👋 Пока! Не забудь домашку!",
        "✌️ Бай! Увидимся на уроке!",
        "😢 Уходишь? Ладно... <i>*грустит*</i>",
        "🫡 До встречи, солдат знаний!",
    ]
    await message.answer(_rng.choice(replies), parse_mode=ParseMode.HTML)


@router.message(F.text.lower().contains("столовая"))
async def easter_food(message: Message):
    replies = [
        "🍽 Столовая... Место где мечты о еде разбиваются о запеканку",
        "🥘 В столовой сегодня... а впрочем, лучше не знать 😂",
        "🍕 Мечта любого школьника — пицца в столовой!",
        "🫣 Компот из столовой = зелье храбрости",
    ]
    await message.answer(_rng.choice(replies))


@router.message(F.text.lower().contains("контрольная"))
async def easter_test(message: Message):
    replies = [
        "📝 Контрольная? Главное не паниковать! ... <i>*паникует*</i>",
        "😨 КОНТРОЛЬНАЯ?! Я... я не готов!",
        "🧘 Вдох-выдох... Ты всё знаешь... наверное...",
        "🍀 Удачи на контрольной! Вот тебе клевер!",
        "🙏 Пусть учитель забудет про контрольную. Аминь.",
    ]
    await message.answer(_rng.choice(replies), parse_mode=ParseMode.HTML)


@router.message(F.sticker)
async def easter_sticker(message: Message):
    """React to stickers with a small chance."""
    reactions = ["😄", "👍", "🤣", "🔥", "❤️", "😎", "🤔", "👀"]
    if _rng.random() < 0.3:
        await message.answer(_rng.choice(reactions))
