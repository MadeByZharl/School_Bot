from datetime import datetime
import pytz

ALMATY_TZ = pytz.timezone("Asia/Almaty")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# СТАНДАРТ — 45-минутные уроки
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STANDARD_SHIFT_1 = {
    1: {"start": "08:00", "end": "08:45"},
    2: {"start": "08:50", "end": "09:35"},
    3: {"start": "09:45", "end": "10:30"},
    4: {"start": "10:40", "end": "11:25"},
    5: {"start": "11:30", "end": "12:15"},
    6: {"start": "12:15", "end": "12:55"},
    7: {"start": "13:00", "end": "13:40"},
    8: {"start": "13:45", "end": "14:25"},
}

MONDAY_SHIFT_1 = {
    1: {"start": "08:00", "end": "08:15"}, # Сынып сағаты 15 мин
    2: {"start": "08:20", "end": "09:05"},
    3: {"start": "09:15", "end": "10:00"},
    4: {"start": "10:10", "end": "10:55"},
    5: {"start": "11:00", "end": "11:45"},
    6: {"start": "11:45", "end": "12:25"},
    7: {"start": "12:30", "end": "13:10"},
    8: {"start": "13:15", "end": "13:55"},
}

STANDARD_SHIFT_2 = {
    1: {"start": "13:30", "end": "14:15"},
    2: {"start": "14:20", "end": "15:05"},
    3: {"start": "15:15", "end": "16:00"},
    4: {"start": "16:10", "end": "16:55"},
    5: {"start": "17:00", "end": "17:40"},
    6: {"start": "17:45", "end": "18:25"},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# СОКРАЩЁННЫЙ — 30-минутные уроки
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SHORT_SHIFT_1 = {
    1: {"start": "08:00", "end": "08:30"},
    2: {"start": "08:35", "end": "09:05"},
    3: {"start": "09:15", "end": "09:45"},
    4: {"start": "09:55", "end": "10:25"},
    5: {"start": "10:30", "end": "11:00"},
    6: {"start": "11:05", "end": "11:35"},
    7: {"start": "11:40", "end": "12:10"},
    8: {"start": "12:15", "end": "12:45"},
}

SHORT_MONDAY_SHIFT_1 = {
    1: {"start": "08:00", "end": "08:15"}, # Сынып сағаты 15 мин
    2: {"start": "08:20", "end": "08:50"},
    3: {"start": "09:00", "end": "09:30"},
    4: {"start": "09:40", "end": "10:10"},
    5: {"start": "10:15", "end": "10:45"},
    6: {"start": "10:50", "end": "11:20"},
    7: {"start": "11:25", "end": "11:55"},
    8: {"start": "12:00", "end": "12:30"},
}

SHORT_SHIFT_2 = {
    1: {"start": "12:30", "end": "13:00"},
    2: {"start": "13:05", "end": "13:35"},
    3: {"start": "13:45", "end": "14:15"},
    4: {"start": "14:25", "end": "14:55"},
    5: {"start": "15:00", "end": "15:30"},
    6: {"start": "15:35", "end": "16:05"},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ЗАВТРАШНИЙ (С 09:00)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CUSTOM_SHIFT_1 = {
    1: {"start": "09:00", "end": "09:30"},
    2: {"start": "09:35", "end": "10:05"},
    3: {"start": "10:10", "end": "10:40"},
    4: {"start": "10:45", "end": "11:15"},
    5: {"start": "11:20", "end": "11:50"},
    6: {"start": "11:55", "end": "12:25"},
    7: {"start": "12:30", "end": "13:00"},
    8: {"start": "13:05", "end": "13:35"},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# РЕЖИМЫ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BELL_MODES = {
    "standard": {1: STANDARD_SHIFT_1, 2: STANDARD_SHIFT_2},
    "short": {1: SHORT_SHIFT_1, 2: SHORT_SHIFT_2},
    "custom": {1: CUSTOM_SHIFT_1, 2: STANDARD_SHIFT_2},
}


def get_shifts(mode: str = "standard", weekday: int = -1) -> dict:
    shifts = BELL_MODES.get(mode, BELL_MODES["standard"]).copy()
    if weekday == 0:  # Понедельник
        if mode == "short":
            shifts[1] = SHORT_MONDAY_SHIFT_1
        elif mode == "custom":
            pass # keep CUSTOM_SHIFT_1 for custom mode even on Monday
        else:
            shifts[1] = MONDAY_SHIFT_1
    return shifts


def get_now_almaty() -> str:
    now = datetime.now(ALMATY_TZ)
    return now.strftime("%H:%M")


def get_weekday_almaty() -> int:
    return datetime.now(ALMATY_TZ).weekday()
