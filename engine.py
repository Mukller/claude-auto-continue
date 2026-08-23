# -*- coding: utf-8 -*-
"""engine — чистая логика claude-auto-continue без tkinter/UIA (#12).

Модуль импортирует только стандартную библиотеку: тестируется на CI без
дисплея и переиспользуется и GUI, и CLI-режимом.
"""

import datetime
import re

# ── Кнопка "Try again" (тексты для UIA/шаблонного поиска) ────────────────────
TRY_AGAIN_LABELS = ['Try again', 'try again', 'Retry', 'Попробовать снова']

# ── Профили приложений (универсальный auto-continue) ────────────────────────
# Каждый профиль описывает, КАК находить окно приложения, кнопку повтора,
# поле ввода и навигацию сайдбара. Claude Desktop - эталонный профиль;
# остальные - экспериментальные (дерево UIA у них не сверялось поэлементно).
DEFAULT_PROFILE = 'claude'

APP_PROFILES = {
    'claude': {
        'label': 'Claude Desktop',
        'process': ['claude.exe'],
        'exclude_process_substrings': ['claude-code'],
        'button_labels': ['Try again', 'try again', 'Retry',
                          'Попробовать снова'],
        'input_names': ['Prompt'],
        'sidebar_chrome': {
            'back', 'collapse sidebar', 'expand sidebar', 'forward', 'menu',
            'search', 'sidebar', 'mode', 'chat', 'code', 'cowork',
            'new session', 'routines', 'dispatch', 'dispatch beta', 'beta',
            'customize', 'more navigation items', 'pinned', 'recents',
            'filter', 'home', 'new',
        },
        'sidebar_prefixes': ('more options for ', 'show more', 'show less',
                             'show all', 'relaunch to update'),
        'window_title_hint': None,
        'experimental': False,
    },
    'cursor': {
        'label': 'Cursor',
        'process': ['cursor.exe'],
        'exclude_process_substrings': [],
        'button_labels': ['Try again', 'try again', 'Retry', 'Resume',
                          'Continue'],
        'input_names': ['Prompt', 'Chat input', 'Ask anything'],
        'sidebar_chrome': {
            'back', 'forward', 'search', 'settings', 'history', 'chats',
            'new chat', 'more options', 'pinned', 'recents', 'home',
        },
        'sidebar_prefixes': ('more options for ',),
        'window_title_hint': None,
        'experimental': True,
    },
    'windsurf': {
        'label': 'Windsurf',
        'process': ['windsurf.exe'],
        'exclude_process_substrings': [],
        'button_labels': ['Try again', 'try again', 'Retry', 'Resume',
                          'Continue'],
        'input_names': ['Prompt', 'Chat input', 'Cascade input'],
        'sidebar_chrome': {
            'back', 'forward', 'search', 'settings', 'history', 'chats',
            'new chat', 'more options', 'pinned', 'recents', 'home',
        },
        'sidebar_prefixes': ('more options for ',),
        'window_title_hint': None,
        'experimental': True,
    },
    'copilot': {
        'label': 'VS Code Copilot Chat',
        # code.exe - весь редактор: без window_title_hint поймаем любое окно
        'process': ['code.exe'],
        'exclude_process_substrings': ['code - tunnel'],
        'button_labels': ['Retry', 'Try again', 'Resume', 'Continue'],
        'input_names': ['Prompt', 'Chat input', 'Ask Copilot'],
        'sidebar_chrome': {
            'back', 'forward', 'search', 'settings', 'history', 'chats',
            'new chat', 'more actions', 'pinned', 'home',
        },
        'sidebar_prefixes': ('more options for ',),
        'window_title_hint': 'Visual Studio Code',
        'experimental': True,
    },
}


def profile_names():
    """Отсортированные ключи реестра (для UI и argparse choices)."""
    return sorted(APP_PROFILES)


def resolve_profile(name):
    """Профиль по имени; неизвестное/пустое -> эталонный claude."""
    key = (name or DEFAULT_PROFILE).strip().lower()
    if key not in APP_PROFILES:
        key = DEFAULT_PROFILE
    return APP_PROFILES[key]


# ── Парсер времени сброса лимита ─────────────────────────────────────────────
_LIMIT_ABS = [
    # "resets at 3:45 PM", "resets at 5 PM", "resets at 15:30"
    re.compile(r'resets?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*([APap]\.?\s?[Mm]\.?)?', re.I),
    re.compile(r'available\s+(?:again\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*([APap]\.?\s?[Mm]\.?)?', re.I),
    re.compile(r'try\s+again\s+after\s+(\d{1,2})(?::(\d{2}))?\s*([APap]\.?\s?[Mm]\.?)?', re.I),
    re.compile(r'try\s+again\s+at\s+(\d{1,2})(?::(\d{2}))?\s*([APap]\.?\s?[Mm]\.?)?', re.I),
    # Russian: "сбросится в 15:30"
    re.compile(r'сбросится\s+в\s+(\d{1,2}):(\d{2})', re.I),
    re.compile(r'обновится\s+в\s+(\d{1,2}):(\d{2})', re.I),
    re.compile(r'станет\s+доступно\s+в\s+(\d{1,2}):(\d{2})', re.I),
    re.compile(r'доступно\s+в\s+(\d{1,2}):(\d{2})', re.I),
]
_LIMIT_DUR_SPECIALS_PRE = [
    (re.compile(r'half\s+an?\s+hour', re.I), 30),   # "in half an hour"
    (re.compile(r'полчаса', re.I), 30),             # "через полчаса"
    (re.compile(r'полтора\s+часа', re.I), 90),      # "через полтора часа"
]
_LIMIT_DUR = [
    # "in 3 hours 45 minutes" / "in 45 minutes" / "in 3 hours"
    re.compile(r'in\s+(\d+)\s+hours?\s+(?:and\s+)?(\d+)\s+minutes?', re.I),
    # \b + lookahead не дают откатиться к «in 3 hour» на строке
    # "in 3 hours and 45 minutes"
    re.compile(r'in\s+(\d+)\s+hours?\b(?!\s+(?:and\s+)?\d)', re.I),
    re.compile(r'in\s+(\d+)\s+minutes?', re.I),
    # Словесные формы: "in an hour" / "через час" (после цифровых!)
    re.compile(r'in\s+an?\s+hour', re.I),
    re.compile(r'через\s+час\b', re.I),
    # Russian
    re.compile(r'через\s+(\d+)\s+час[а-я]*\s+(?:и\s+)?(\d+)\s+минут', re.I),
    re.compile(r'через\s+(\d+)\s+час[а-я]*\b(?!\s+(?:и\s+)?\d)', re.I),
    re.compile(r'через\s+(\d+)\s+минут', re.I),
]

# Контекст настоящих сообщений об ограничении (#16): рядом со временем
# сброса почти всегда есть слово про лимит/usage/исчерпание.
_LIMIT_CONTEXT_RE = re.compile(
    r'limit|usage|лимит|исчерпан|ограничен|попробуйте|превышен', re.I)
_CONTEXT_WINDOW_CHARS = 120


def has_limit_context(text: str, start: int, end: int,
                      window: int = _CONTEXT_WINDOW_CHARS) -> bool:
    """Есть ли рядом со срезом [start:end) слова про лимит/usage."""
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    return bool(_LIMIT_CONTEXT_RE.search(text[lo:hi]))


def next_reset_occurrence(h: int, m: int) -> datetime.datetime:
    """Ближайший момент суток HH:MM: сегодня, а если прошёл — завтра.

    Строки HH:MM сравнивать нельзя: два скана внутри одного окна сброса
    всегда дают одну строку. Дубль = тот же сброс со сроком в будущем."""
    now = datetime.datetime.now()
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t <= now:
        t += datetime.timedelta(days=1)
    return t


def parse_limit_text(text: str, now=None, require_context: bool = False):
    """Чистая функция (без UIA): текст окна → (hour, minute) или None.
    Сначала абсолютное время ('resets at HH:MM'), потом относительное
    ('in X hours Y minutes') от переданного/текущего момента.

    require_context=True — матч принимается только если рядом (±120 знаков)
    есть слова про лимит/usage (#16): иначе старое сообщение в истории чата
    «мы обсуждали resets at 3 PM» даёт фантомный сброс."""
    if not text:
        return None

    now = now or datetime.datetime.now()

    def _ok(s: int, e: int) -> bool:
        return (not require_context) or has_limit_context(text, s, e)

    # Словесные формы без чисел ("in half an hour", "через полчаса")
    low = text.lower()
    offset = len(text) - len(low)
    for pat, minutes in _LIMIT_DUR_SPECIALS_PRE:
        m = pat.search(low)
        if m and _ok(m.start() + offset, m.end() + offset):
            reset_dt = now + datetime.timedelta(minutes=minutes)
            return (reset_dt.hour, reset_dt.minute)

    for pat in _LIMIT_ABS:
        for m in pat.finditer(text):
            if not _ok(m.start(), m.end()):
                continue
            gs = m.groups()
            h = int(gs[0])
            mn = int(gs[1]) if len(gs) > 1 and gs[1] else 0
            ampm = (gs[2] or '').replace('.', '').replace(' ', '').upper() \
                if len(gs) > 2 else ''
            if ampm == 'PM' and h < 12:
                h += 12
            elif ampm == 'AM' and h == 12:
                h = 0
            if 0 <= h <= 23 and 0 <= mn <= 59:
                return (h, mn)

    for pat in _LIMIT_DUR:
        for m in pat.finditer(text):
            if not _ok(m.start(), m.end()):
                continue
            groups = [int(x) for x in m.groups() if x is not None]
            if len(groups) == 2:
                delta = datetime.timedelta(hours=groups[0], minutes=groups[1])
            elif len(groups) == 1:
                # определяем - часы это или минуты - по группе паттерна
                src = pat.pattern.lower()
                delta = (datetime.timedelta(hours=groups[0])
                         if 'hour' in src or 'час' in src
                         else datetime.timedelta(minutes=groups[0]))
            else:
                continue
            reset_dt = now + delta
            return (reset_dt.hour, reset_dt.minute)

    return None


# ── CLI-хелперы ──────────────────────────────────────────────────────────────

def cli_target(at_str):
    """'HH:MM' -> ближайший будущий datetime; None при невалидной строке."""
    m = re.fullmatch(r'(\d{1,2}):(\d{2})', str(at_str).strip())
    if not m:
        return None
    h, mn = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mn <= 59):
        return None
    now = datetime.datetime.now()
    t = now.replace(hour=h, minute=mn, second=0, microsecond=0)
    if t <= now:
        t += datetime.timedelta(days=1)
    return t
