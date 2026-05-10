"""Shared validators: fio, bad words filter."""
import re

# Корни ругательств — подбираем так, чтобы ловить словоформы (ебанутый, пиздец, залупа).
# Используем substring-match по нижнему регистру, но с ограничением на кириллицу вокруг,
# чтобы снизить false-positive вроде "скука".
_BAD_ROOTS = (
    "блят", "сук", "хуй", "пизд", "ебан", "нахуй", "залуп", "ёб", "еб", "дерьм",
)
_BAD_RE = re.compile(
    r"(?:^|(?<=[^а-яёa-z]))(?:" + "|".join(_BAD_ROOTS) + r")",
    re.IGNORECASE,
)


def has_bad_words(text: str) -> bool:
    """True, если в тексте встречается корень из списка (по границе слова)."""
    if not text:
        return False
    return bool(_BAD_RE.search(text.lower()))


def validate_fio(text: str) -> bool:
    """Проверка ФИО: >=2 слов, каждое с большой буквы, только буквы."""
    if not text:
        return False
    parts = text.strip().split()
    if len(parts) < 2:
        return False
    for p in parts:
        if not p or not p[0].isupper():
            return False
        if not all(c.isalpha() for c in p):
            return False
    return True
