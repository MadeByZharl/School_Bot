"""Unit-тесты для чистых функций (без реальной БД)."""
import os
import sys
from pathlib import Path

# Позволяем pytest находить пакет без установки
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_has_bad_words_basic():
    from utils.validators import has_bad_words

    assert has_bad_words("блять") is True
    assert has_bad_words("ты ебанутый") is True
    assert has_bad_words("пиздец полный") is True
    assert has_bad_words("дерьмо какое-то") is True


def test_has_bad_words_false_positives():
    """Раньше substring-match ловил 'скука' как ругательство — теперь не должен."""
    from utils.validators import has_bad_words

    assert has_bad_words("скука") is False
    assert has_bad_words("Привет, как дела?") is False
    assert has_bad_words("") is False
    assert has_bad_words("Иванов Иван Петрович") is False


def test_validate_fio_ok():
    from utils.validators import validate_fio

    assert validate_fio("Иванов Иван") is True
    assert validate_fio("Ахметов Нурбол Серикович") is True


def test_validate_fio_fail():
    from utils.validators import validate_fio

    assert validate_fio("") is False
    assert validate_fio("иванов") is False          # одно слово
    assert validate_fio("иванов иван") is False     # маленькая буква
    assert validate_fio("Иванов 123") is False      # цифры
    assert validate_fio("Иванов Иван1") is False


def test_normalize_class_code():
    """Нормализация: убираем пробелы, кавычки, приводим к верхнему регистру."""
    # Не импортируем db на верхнем уровне, чтобы не требовать env-переменных БД
    # когда достаточно env для валидатора.
    os.environ.setdefault("DB_HOST", "x")
    os.environ.setdefault("DB_USER", "x")
    os.environ.setdefault("DB_PASSWORD", "x")
    os.environ.setdefault("DB_NAME", "x")
    from db import normalize_class_code

    assert normalize_class_code("8Ә") == "8Ә"
    assert normalize_class_code(" 8 ә ") == "8Ә"
    assert normalize_class_code('"8ә"') == "8Ә"
    assert normalize_class_code("'8ә'") == "8Ә"
    assert normalize_class_code(None) is None
    assert normalize_class_code("") is None


def test_html_to_wa():
    """Telegram HTML → WhatsApp markdown."""
    from wa_client import html_to_wa

    assert html_to_wa("<b>жирный</b>") == "*жирный*"
    assert html_to_wa("<i>курсив</i>") == "_курсив_"
    assert html_to_wa("<s>зачёрк</s>") == "~зачёрк~"
    assert html_to_wa("<code>код</code>") == "код"
    assert html_to_wa("<tg-spoiler>спойлер</tg-spoiler>") == "спойлер"
    # неизвестные теги вырезаются
    assert html_to_wa('<a href="https://x">link</a>') == "link"
