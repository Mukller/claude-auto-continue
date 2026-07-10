#!/usr/bin/env python3
"""Claude Code Auto-Continue — v3.8
Windows: автопоиск кнопки через UI Automation + переключение чатов в сайдбаре.
macOS:   поиск окна через pgrep/osascript, поиск кнопки по скриншоту-шаблону.
"""

import sys, os

IS_WIN = sys.platform == 'win32'
IS_MAC = sys.platform == 'darwin'

def _fatal(msg):
    try:
        import tkinter.messagebox as mb
        import tkinter as tk
        r = tk.Tk(); r.withdraw()
        mb.showerror("Ошибка запуска", msg)
    except Exception:
        pass
    sys.exit(1)

try:
    import tkinter as tk
except ImportError:
    _fatal("tkinter не найден. Переустановите Python с поддержкой Tkinter.")

import threading, time, datetime, math, ctypes, json
from collections import deque
if IS_WIN:
    from ctypes import wintypes
    try:
        import winreg
    except ImportError:
        winreg = None
else:
    winreg = None

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None

try:
    from PIL import Image, ImageGrab, ImageTk
except ImportError:
    Image = ImageGrab = ImageTk = None

HAS_CV2 = False
try:
    import cv2  # noqa: F401
    HAS_CV2 = True
except ImportError:
    pass

try:
    import uiautomation as auto
    HAS_UIA = True
except ImportError:
    auto = None
    HAS_UIA = False

try:
    import pystray
    HAS_TRAY = True
except ImportError:
    pystray = None
    HAS_TRAY = False

try:
    from plyer import notification as _plyer_notif
    HAS_NOTIF = True
except ImportError:
    _plyer_notif = None
    HAS_NOTIF = False

# ── Темы ──────────────────────────────────────────────────────────────────────
THEMES = {
    'dark':  dict(BG='#0d1117', C1='#161b22', C2='#21262d', BRD='#30363d',
                  TXT='#e6edf3', DIM='#8b949e', ACC='#58a6ff',
                  SUC='#3fb950', ERR='#f85149', WARN='#e3b341'),
    'light': dict(BG='#dce1e8', C1='#f0f4f8', C2='#c4cdd8', BRD='#8fa0b0',
                  TXT='#0f1923', DIM='#384553', ACC='#1a5fb4',
                  SUC='#1a6e35', ERR='#b81c2e', WARN='#7a4200'),
}

# ── Палитра (по умолчанию dark; перезаписывается _apply_theme_vars) ───────────
BG, C1, C2 = "#0d1117", "#161b22", "#21262d"
ACC, TXT, DIM = "#58a6ff", "#e6edf3", "#8b949e"
SUC, ERR, WARN, BRD = "#3fb950", "#f85149", "#e3b341", "#30363d"

# ── Переводы интерфейса (меню/кнопки/статусы) ────────────────────────────────
# Движок (find_claude_windows/run_cycle и т.п.) логирует диагностику только
# на русском — переключатель распространяется на меню приложения, не на
# внутренний технический лог.
I18N = {
    'ru': {
        'missing': '⚠ Не хватает: {deps}\npip install {installs}',
        'ring_idle': 'Не запущено',
        'ring_waiting': 'Ждём {time}',
        'ring_firing': 'Нажимаем…',
        'ring_done': 'Готово×{n}',
        'ring_fail': 'Не найдено',
        'trigger_at': 'Нажать в:',
        'now_btn': '↻ Сейчас',
        'start_btn': '▶   СТАРТ',
        'stop_btn': '⏹   СТОП',
        'watch_label': 'Наблюдение — каждые',
        'sec': 'сек',
        'find_btn': '↻  Найти',
        'app_not_found': '⚠ Claude Desktop не найден. Открой приложение и нажми «Найти».',
        'app_found_chats': '✓ {title}  —  чатов в сайдбаре: {n}',
        'app_found_no_sidebar': '✓ {title}  —  сайдбар не обнаружен, работаем с текущим видом',
        'switch_first': 'Переключаться на первые',
        'chats_word': 'чатов',
        'more_chats': '  … ещё {n}',
        'per_chat': 'В каждом чате:',
        'try_again_desc': ' — найти и нажать кнопку (ошибка лимита сервера)',
        'continue_desc': ' — нажать Enter (продолжить сессию, кнопки не нужно)',
        'check_now_btn': '🔍  Проверить сейчас',
        'fallback_title': 'Резервный вариант (если авто-поиск не найдёт кнопку)',
        'accuracy': 'Точность',
        'log_title': 'Лог',
        'clear_btn': '✕ очистить',
        'badge_sidebar': 'Сайдбар',
        'badge_uia': 'UIA-поиск',
        'badge_template': 'Шаблон (резерв)',
        'tpl_not_set': 'не задан',
        'tpl_not_set_optional': 'не задан (необязательно)',
        'tpl_read_error': 'ошибка чтения',
        'capture_btn': '📷 Захватить',
        'log_stopped': 'Остановлено.',
        'log_started': 'Запущено → {time}',
        'log_no_uia': '⚠ uiautomation не установлен: pip install uiautomation',
        'log_time_search': 'Время! Ищу окно и чаты…',
        'log_attempt': 'Попытка {n}/3:',
        'log_success': '✓  Успех — обработано {n} чат(ов)!',
        'log_fail': '✗  Ничего не сделано. Проверь, что Claude Desktop открыт.',
        'log_watch': 'Наблюдение каждые {n}с.',
        'log_now': 'Ищу и нажимаю прямо сейчас…',
        'log_test': 'Тестовый поиск кнопки Try again (без переключения чатов, без Enter)…',
        'log_no_app': 'Claude Desktop не найден.',
        'log_btn_found': '✓ Кнопка "Try again" найдена на экране в области ({x}, {y})',
        'log_btn_not_found': 'Кнопка "Try again" не найдена в текущем виде окна '
                             '(это нормально, если нет активной ошибки лимита).',
        'log_cont_note': 'Continue включён: при СТАРТ/Сейчас в каждом чате '
                         'будет нажат Enter независимо от результата поиска выше.',
        'log_capture_cancelled': 'Захват отменён.',
        'log_capture_saved': '✓ Шаблон "{label}" сохранён ({w}×{h})',
        'log_capture_error': 'Ошибка сохранения шаблона: {e}',
        'log_no_pillow': 'Pillow не установлен — захват недоступен.',
        'capture_hint': 'Выдели рамкой кнопку  •  Esc — отмена',
        'chat_list_title': 'Список чатов',
        'plan_title': 'План запусков (циклы)',
        'plan_add_btn': '+ Добавить',
        'plan_empty': 'Время в плане не добавлено',
        'plan_repeat': 'Повторять ежедневно',
        'plan_start_btn': '▶  Запустить план',
        'plan_stop_btn': '⏹  Остановить план',
        'plan_status_idle': 'План не запущен',
        'plan_status_next': 'Следующий запуск плана: {time} (через {left})',
        'plan_left_fmt': '{h}ч {m}м',
        'plan_left_fmt_m': '{m}м',
        'log_plan_started': 'План запущен, времён в списке: {n}',
        'log_plan_stopped': 'План остановлен.',
        'log_plan_trigger': 'План: время {time} — ищу окно и чаты…',
        'log_plan_done': 'План выполнен — все разовые запуски отработали.',
        'log_plan_already_running': '⚠ Нельзя запустить план — уже идёт одиночный запуск (СТАРТ).',
        'log_single_blocked_by_plan': '⚠ Нельзя нажать СТАРТ — сейчас работает план.',
        'theme_dark': '☾ Тёмная',
        'theme_light': '☀ Светлая',
        'autostart_on':  '⏻ Автозапуск: ВКЛ',
        'autostart_off': '⏻ Автозапуск: ВЫКЛ',
        'chat_sel_all': 'Все',
        'chat_sel_none': 'Снять',
        'chat_selected': 'Выбрано: {n} из {total}',
        'switch_first': 'Чаты для обработки:',
        'stats_session': 'Сессия: {clicks} цикл(ов), {ok} успешно ({pct}%)',
        'history_title': 'История срабатываний',
        'history_empty': 'Срабатываний ещё не было',
        'history_ok': '✓ {n} чат(ов)',
        'history_fail': '✗ не сделано',
        'tray_show': 'Открыть',
        'tray_quit': 'Выход',
        'tray_minimize': 'Свернуть в трей при закрытии',
        'notif_title': 'Claude Auto-Continue',
        'notif_ok': 'Успешно обработано чатов: {n}',
        'notif_fail': 'Ни одного чата не обработано',
    },
    'en': {
        'missing': '⚠ Missing: {deps}\npip install {installs}',
        'ring_idle': 'Not started',
        'ring_waiting': 'Waiting for {time}',
        'ring_firing': 'Triggering…',
        'ring_done': 'Done×{n}',
        'ring_fail': 'Not found',
        'trigger_at': 'Trigger at:',
        'now_btn': '↻ Now',
        'start_btn': '▶   START',
        'stop_btn': '⏹   STOP',
        'watch_label': 'Watch mode — every',
        'sec': 'sec',
        'find_btn': '↻  Find',
        'app_not_found': '⚠ Claude Desktop not found. Open the app and click "Find".',
        'app_found_chats': '✓ {title}  —  chats in sidebar: {n}',
        'app_found_no_sidebar': '✓ {title}  —  sidebar not detected, using current view',
        'switch_first': 'Switch to the first',
        'chats_word': 'chats',
        'more_chats': '  … {n} more',
        'per_chat': 'For each chat:',
        'try_again_desc': ' — find and click the button (server rate-limit error)',
        'continue_desc': ' — press Enter (resume session, no button needed)',
        'check_now_btn': '🔍  Check now',
        'fallback_title': 'Fallback option (if auto-search can\'t find the button)',
        'accuracy': 'Accuracy',
        'log_title': 'Log',
        'clear_btn': '✕ clear',
        'badge_sidebar': 'Sidebar',
        'badge_uia': 'UIA search',
        'badge_template': 'Template (fallback)',
        'tpl_not_set': 'not set',
        'tpl_not_set_optional': 'not set (optional)',
        'tpl_read_error': 'read error',
        'capture_btn': '📷 Capture',
        'log_stopped': 'Stopped.',
        'log_started': 'Started → {time}',
        'log_no_uia': '⚠ uiautomation not installed: pip install uiautomation',
        'log_time_search': 'Time\'s up! Looking for window and chats…',
        'log_attempt': 'Attempt {n}/3:',
        'log_success': '✓  Success — processed {n} chat(s)!',
        'log_fail': '✗  Nothing done. Check that Claude Desktop is open.',
        'log_watch': 'Watching every {n}s.',
        'log_now': 'Searching and clicking right now…',
        'log_test': 'Test search for the Try again button (no chat switching, no Enter)…',
        'log_no_app': 'Claude Desktop not found.',
        'log_btn_found': '✓ "Try again" button found on screen at ({x}, {y})',
        'log_btn_not_found': '"Try again" button not found in the current view '
                             '(this is normal if there\'s no active rate-limit error).',
        'log_cont_note': 'Continue is enabled: on START/Now, Enter will be pressed '
                         'in each chat regardless of the search result above.',
        'log_capture_cancelled': 'Capture cancelled.',
        'log_capture_saved': '✓ Template "{label}" saved ({w}×{h})',
        'log_capture_error': 'Error saving template: {e}',
        'log_no_pillow': 'Pillow not installed — capture unavailable.',
        'capture_hint': 'Drag a box around the button  •  Esc — cancel',
        'chat_list_title': 'Chat list',
        'plan_title': 'Scheduled plan (cycles)',
        'plan_add_btn': '+ Add',
        'plan_empty': 'No times added to the plan yet',
        'plan_repeat': 'Repeat daily',
        'plan_start_btn': '▶  Start plan',
        'plan_stop_btn': '⏹  Stop plan',
        'plan_status_idle': 'Plan not running',
        'plan_status_next': 'Next plan trigger: {time} (in {left})',
        'plan_left_fmt': '{h}h {m}m',
        'plan_left_fmt_m': '{m}m',
        'log_plan_started': 'Plan started, {n} time(s) queued',
        'log_plan_stopped': 'Plan stopped.',
        'log_plan_trigger': 'Plan: time {time} — looking for window and chats…',
        'log_plan_done': 'Plan finished — all one-off triggers ran.',
        'log_plan_already_running': '⚠ Can\'t start the plan — a single run (START) is already active.',
        'log_single_blocked_by_plan': '⚠ Can\'t click START — the plan is currently running.',
        'theme_dark': '☾ Dark',
        'theme_light': '☀ Light',
        'autostart_on':  '⏻ Autostart: ON',
        'autostart_off': '⏻ Autostart: OFF',
        'chat_sel_all': 'All',
        'chat_sel_none': 'None',
        'chat_selected': 'Selected: {n} of {total}',
        'switch_first': 'Chats to process:',
        'stats_session': 'Session: {clicks} cycle(s), {ok} successful ({pct}%)',
        'history_title': 'Trigger history',
        'history_empty': 'No triggers yet',
        'history_ok': '✓ {n} chat(s)',
        'history_fail': '✗ nothing done',
        'tray_show': 'Show',
        'tray_quit': 'Exit',
        'tray_minimize': 'Minimize to tray on close',
        'notif_title': 'Claude Auto-Continue',
        'notif_ok': 'Successfully processed {n} chat(s)',
        'notif_fail': 'No chats were processed',
    },
}

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TPL_DIR = os.path.join(APP_DIR, 'templates')
SETTINGS_FILE = os.path.join(APP_DIR, 'settings.json')
os.makedirs(TPL_DIR, exist_ok=True)

# "Continue" больше не ищется как кнопка (см. auto_continue в run_cycle) —
# после лимита Claude Code обычно просто ждёт Enter, без всякой кнопки.
# Шаблон нужен только для запасного варианта поиска "Try again".
TEMPLATES = {
    'try_again': {'label': 'Try again', 'file': os.path.join(TPL_DIR, 'try_again.png')},
}


# ══════════════════════════════════════════════════════════════════════════════
#  ПОИСК ОКНА CLAUDE DESKTOP
# ══════════════════════════════════════════════════════════════════════════════

def get_process_exe(hwnd: int) -> str:
    """Полный путь к exe владельца окна (по hwnd), без внешних зависимостей."""
    if not IS_WIN:
        return ''
    try:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        hproc = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not hproc:
            return ''
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
            hproc, 0, buf, ctypes.byref(size))
        ctypes.windll.kernel32.CloseHandle(hproc)
        return buf.value if ok else ''
    except Exception:
        return ''


def _find_claude_windows_mac(log_fn):
    import subprocess as _sp
    try:
        r = _sp.run(['pgrep', '-i', '-x', 'Claude'],
                    capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            return [{'title': 'Claude Desktop', 'ctrl': None, 'hwnd': None}]
    except Exception as e:
        log_fn(f'  Mac: поиск Claude: {e}', 'dim')
    return []


def _bring_to_foreground_mac(log_fn):
    import subprocess as _sp
    try:
        _sp.run(['osascript', '-e', 'tell application "Claude" to activate'],
                capture_output=True, timeout=3)
        time.sleep(0.3)
        return True
    except Exception as e:
        log_fn(f'  Mac: активация окна: {e}', 'dim')
        return False


def bring_to_foreground(hwnd, log_fn=lambda *a, **k: None) -> bool:
    """SetForegroundWindow из фонового процесса часто молча игнорируется
    Windows (защита от кражи фокуса) — окно может остаться перекрытым
    другим окном (напр. видеозвонком), и клики попадут не туда.
    Стандартный обход: временно прицепиться к очереди ввода активного
    потока через AttachThreadInput."""
    if IS_MAC:
        return _bring_to_foreground_mac(log_fn)
    if not IS_WIN:
        return True
    try:
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)

        fg_hwnd = user32.GetForegroundWindow()
        cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)

        user32.AttachThreadInput(cur_tid, fg_tid, True)
        user32.AttachThreadInput(cur_tid, target_tid, True)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.AttachThreadInput(cur_tid, fg_tid, False)
        user32.AttachThreadInput(cur_tid, target_tid, False)

        time.sleep(0.25)
        ok = user32.GetForegroundWindow() == hwnd
        if not ok:
            log_fn('  ⚠ Не удалось вывести окно Claude на передний план '
                  '(возможно, оно перекрыто другим окном)', 'warn')
        return ok
    except Exception as e:
        log_fn(f'  Ошибка активации окна: {e}', 'dim')
        return False


def find_claude_windows(log_fn=lambda *a, **k: None) -> list:
    """Найти окна процесса Claude.exe (официальное десктоп-приложение)."""
    if IS_MAC:
        return _find_claude_windows_mac(log_fn)
    wins = []
    if not HAS_UIA:
        return wins
    try:
        auto.SetGlobalSearchTimeout(1)
        ctrl = auto.GetRootControl().GetFirstChildControl()
        while ctrl:
            hwnd = ctrl.NativeWindowHandle
            if hwnd:
                exe = get_process_exe(hwnd).lower()
                # claude-code (CLI) тоже заканчивается на claude.exe — исключаем его
                if exe.endswith('\\claude.exe') and 'claude-code' not in exe:
                    wins.append({'title': ctrl.Name or 'Claude', 'hwnd': hwnd, 'ctrl': ctrl})
            ctrl = ctrl.GetNextSiblingControl()
    except Exception as e:
        log_fn(f'  Ошибка поиска окна Claude: {e}', 'dim')
    return wins


# ══════════════════════════════════════════════════════════════════════════════
#  ПОИСК ЧАТОВ В САЙДБАРЕ (переключение внутри одного окна)
# ══════════════════════════════════════════════════════════════════════════════

# Названия элементов навигации сайдбара, которые НЕ являются чатами
# (Claude Desktop не даёт им отдельной ARIA-роли, поэтому фильтруем по Name)
SIDEBAR_CHROME = {
    'back', 'collapse sidebar', 'expand sidebar', 'forward', 'menu', 'search',
    'sidebar', 'mode', 'chat', 'code', 'cowork', 'new session', 'routines',
    'dispatch', 'dispatch beta', 'beta', 'customize', 'more navigation items',
    'pinned', 'recents', 'filter',
}
SIDEBAR_CHROME_PREFIXES = ('more options for ', 'show ', 'relaunch to update')


def _is_real_chat_name(name: str) -> bool:
    low = name.strip().lower()
    if not low or low in SIDEBAR_CHROME:
        return False
    if any(low.startswith(p) for p in SIDEBAR_CHROME_PREFIXES):
        return False
    return True


def _find_sidebar_container(window_ctrl, max_depth=15):
    """BFS по геометрии, а не по имени — в дереве бывает несколько узлов
    с именем 'Sidebar' (напр. вложенные панели файлов в артефактах кода).
    Настоящий навигационный сайдбар: левый край у края окна, узкая
    фиксированная ширина, занимает почти всю высоту окна."""
    try:
        wrect = window_ctrl.BoundingRectangle
    except Exception:
        return None
    queue = deque([(window_ctrl, 0)])
    while queue:
        ctrl, depth = queue.popleft()
        if depth > max_depth:
            continue
        try:
            rect = ctrl.BoundingRectangle
            if (ctrl is not window_ctrl and rect
                    and rect.left - wrect.left < 60
                    and 200 <= rect.width() <= 360
                    and rect.height() > 300):
                return ctrl
            child = ctrl.GetFirstChildControl()
            while child:
                queue.append((child, depth + 1))
                child = child.GetNextSiblingControl()
        except Exception:
            continue
    return None


def find_message_input(window_ctrl, log_fn, max_nodes=6000, time_budget=3.0):
    """Найти поле ввода сообщения ('Prompt') — без клика в него фокус остаётся
    на элементе сайдбара после переключения чата, и Enter улетает в никуда,
    сообщение не отправляется."""
    if not HAS_UIA:
        return None
    start = time.time()
    stack = [window_ctrl]
    visited = 0
    while stack:
        if time.time() - start > time_budget or visited > max_nodes:
            log_fn('  Поиск поля ввода: превышен лимит (время/узлы)', 'dim')
            break
        ctrl = stack.pop()
        visited += 1
        try:
            if ctrl.ControlTypeName == 'GroupControl' and (ctrl.Name or '').strip() == 'Prompt':
                rect = ctrl.BoundingRectangle
                if rect and rect.width() > 0 and rect.height() > 0:
                    return rect
            child = ctrl.GetFirstChildControl()
            kids = []
            while child:
                kids.append(child)
                child = child.GetNextSiblingControl()
            stack.extend(kids)
        except Exception:
            continue
    return None


def find_sidebar_chats(window_ctrl, log_fn, max_nodes=6000, time_budget=4.0) -> list:
    """Список чатов — кнопки внутри навигационного сайдбара, отфильтрованные
    от обвязки (Pinned/Recents/More options/Relaunch to update и т.п.)."""
    if not HAS_UIA:
        return []

    root = _find_sidebar_container(window_ctrl) or window_ctrl
    start = time.time()
    stack = [root]
    visited = 0
    found = []
    seen_keys = set()

    while stack:
        if time.time() - start > time_budget or visited > max_nodes:
            log_fn('  Поиск сайдбара: превышен лимит (время/узлы)', 'dim')
            break
        ctrl = stack.pop()
        visited += 1
        try:
            if ctrl.ControlTypeName == 'ButtonControl':
                name = (ctrl.Name or '').strip()
                rect = ctrl.BoundingRectangle
                if (rect and 20 <= rect.height() <= 32 and rect.width() >= 150
                        and _is_real_chat_name(name)):
                    key = (name, rect.top // 10)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        clean = name[8:] if name.startswith('Running ') else name
                        found.append({'name': clean, 'rect': rect, 'top': rect.top})
            child = ctrl.GetFirstChildControl()
            kids = []
            while child:
                kids.append(child)
                child = child.GetNextSiblingControl()
            stack.extend(kids)
        except Exception:
            continue

    found.sort(key=lambda x: x['top'])
    return found


# ══════════════════════════════════════════════════════════════════════════════
#  АВТОПОИСК КНОПКИ ПО ТЕКСТУ (UI Automation, без шаблонов)
# ══════════════════════════════════════════════════════════════════════════════

def find_button_uia(root_ctrl, labels: list, log_fn,
                    max_nodes=8000, time_budget=5.0, min_w=50, min_h=18):
    """DFS в обратном порядке детей (сначала последние — обычно низ чата,
    где и появляется кнопка). Совпадение по Name на ЛЮБОМ типе контрола —
    Electron/React часто не проставляет ControlType=Button корректно.

    Точное совпадение возвращается сразу. Частичное — только как запасной
    вариант, с фильтром по минимальному размеру (иначе ловим случайные
    18×18 иконки типа "More options for ..." с посторонним текстом)."""
    if not HAS_UIA:
        return None, None
    start = time.time()
    stack = [root_ctrl]
    visited = 0
    labels_lower = [l.lower() for l in labels]
    loose_match = None

    while stack:
        if time.time() - start > time_budget:
            log_fn('  UIA-поиск: истёк лимит времени', 'dim')
            break
        if visited > max_nodes:
            log_fn('  UIA-поиск: превышен лимит узлов', 'dim')
            break
        ctrl = stack.pop()
        visited += 1
        try:
            name = (ctrl.Name or '').strip()
            if name:
                low = name.lower()
                rect = ctrl.BoundingRectangle
                if rect and rect.width() >= min_w and rect.height() >= min_h:
                    for lbl in labels_lower:
                        if low == lbl:
                            return ctrl, rect
                        if loose_match is None and lbl in low and len(low) <= len(lbl) + 15:
                            loose_match = (ctrl, rect)
            child = ctrl.GetFirstChildControl()
            kids = []
            while child:
                kids.append(child)
                child = child.GetNextSiblingControl()
            stack.extend(kids)  # extend в обычном порядке → pop() берёт последнего ребёнка первым
        except Exception:
            continue

    return loose_match if loose_match else (None, None)


def click_rect(rect, log_fn, press_enter_after=False) -> bool:
    if pyautogui is None or rect is None:
        return False
    try:
        cx = int(rect.xcenter()) if hasattr(rect, 'xcenter') else int((rect.left + rect.right) / 2)
        cy = int(rect.ycenter()) if hasattr(rect, 'ycenter') else int((rect.top + rect.bottom) / 2)
        pyautogui.moveTo(cx, cy, duration=0.12)
        time.sleep(0.05)
        pyautogui.click(cx, cy)
        log_fn(f'  ✓ Клик в ({cx}, {cy})', 'success')
        if press_enter_after:
            time.sleep(0.45)
            pyautogui.press('enter')
            log_fn('  → Enter отправлен', 'dim')
        return True
    except Exception as e:
        log_fn(f'  Клик не удался: {e}', 'error')
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  РЕЗЕРВНЫЙ ВАРИАНТ: ПОИСК ПО СКРИНШОТУ (шаблон)
# ══════════════════════════════════════════════════════════════════════════════

def find_matches(template_path: str, confidence: float, log_fn) -> list:
    if pyautogui is None or not os.path.isfile(template_path):
        return []
    try:
        if HAS_CV2:
            boxes = list(pyautogui.locateAllOnScreen(
                template_path, confidence=confidence, grayscale=True))
        else:
            boxes = list(pyautogui.locateAllOnScreen(template_path))
    except Exception as e:
        log_fn(f'  Поиск шаблона: {e}', 'dim')
        return []

    out = []
    for b in boxes:
        cx, cy = b.left + b.width / 2, b.top + b.height / 2
        if not any(abs(cx - (e.left + e.width/2)) < 12 and abs(cy - (e.top + e.height/2)) < 12
                  for e in out):
            out.append(b)
    return out


def click_box(box, log_fn, press_enter_after=False) -> bool:
    if pyautogui is None:
        return False
    try:
        cx, cy = box.left + box.width // 2, box.top + box.height // 2
        pyautogui.moveTo(cx, cy, duration=0.15)
        time.sleep(0.05)
        pyautogui.click(cx, cy)
        log_fn(f'  ✓ Клик по шаблону в ({cx}, {cy})', 'success')
        if press_enter_after:
            time.sleep(0.45)
            pyautogui.press('enter')
            log_fn('  → Enter отправлен', 'dim')
        return True
    except Exception as e:
        log_fn(f'  Клик не удался: {e}', 'error')
        return False


def template_fallback_click(labels: list, confidence: float,
                            press_enter_after: bool, log_fn, badge_fn=None) -> bool:
    all_boxes = []
    for key in labels:
        tpl = TEMPLATES.get(key)
        if not tpl or not os.path.isfile(tpl['file']):
            continue
        boxes = find_matches(tpl['file'], confidence, log_fn)
        all_boxes.extend(boxes)
    if not all_boxes:
        return False
    all_boxes.sort(key=lambda b: (b.top, b.left))
    if badge_fn: badge_fn(2, 'trying')
    ok = click_box(all_boxes[0], log_fn, press_enter_after)
    if badge_fn: badge_fn(2, 'ok' if ok else 'fail')
    return ok


# ══════════════════════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ ЦИКЛ: НАЙТИ ЧАТЫ → ПЕРЕКЛЮЧИТЬСЯ → НАЙТИ КНОПКУ → КЛИК
# ══════════════════════════════════════════════════════════════════════════════

TRY_AGAIN_LABELS = ['Try again', 'try again', 'Retry', 'Попробовать снова']


def run_cycle(n_or_indices, search_try_again: bool, auto_continue: bool, confidence: float,
             log_fn, badge_fn=None) -> int:
    """search_try_again — искать и кликать реальную кнопку "Try again" (лимит запросов).
    auto_continue — после захода в чат нажать Enter НЕЗАВИСИМО от того, нашлась ли
    кнопка: обычно после исчерпания лимита Claude Code просто ждёт ввода без всякой
    кнопки, и "продолжить" — это буквально нажать Enter в пустом поле ввода."""
    if IS_WIN and not HAS_UIA:
        log_fn('  uiautomation не установлен — авто-поиск недоступен', 'error')
        return 0

    windows = find_claude_windows(log_fn)
    if not windows:
        log_fn('  ⚠ Приложение Claude Desktop не найдено', 'error')
        return 0

    window = windows[0]
    log_fn(f'  Окно: {(window["title"] or "Claude")[:50]}', 'dim')

    if not bring_to_foreground(window['hwnd'], log_fn):
        log_fn('  Продолжаю всё равно — но клики могут промахнуться', 'warn')

    if badge_fn: badge_fn(0, 'trying')
    chats = find_sidebar_chats(window['ctrl'], log_fn)
    if badge_fn: badge_fn(0, 'ok' if chats else 'idle')

    ok = 0

    def process_current_view() -> bool:
        nonlocal ok
        did_something = False

        if search_try_again:
            if badge_fn: badge_fn(1, 'trying')
            _, rect = find_button_uia(window['ctrl'], TRY_AGAIN_LABELS, log_fn)
            if rect:
                if badge_fn: badge_fn(1, 'ok')
                if click_rect(rect, log_fn, press_enter_after=False):
                    did_something = True
            else:
                if badge_fn: badge_fn(1, 'idle')
                if template_fallback_click(['try_again'], confidence, False, log_fn, badge_fn):
                    did_something = True

        if auto_continue and pyautogui is not None:
            if did_something:
                time.sleep(0.4)  # дать кнопке отработать перед Enter
            input_rect = find_message_input(window['ctrl'], log_fn)
            if input_rect:
                click_rect(input_rect, log_fn, press_enter_after=False)
                time.sleep(0.2)
            else:
                log_fn('  ⚠ Поле ввода не найдено, жму Enter вслепую', 'warn')
            pyautogui.press('enter')
            log_fn('  → Enter отправлен (продолжить)', 'success')
            did_something = True

        if did_something:
            ok += 1
        return did_something

    if chats:
        if isinstance(n_or_indices, list):
            targets = [chats[i] for i in n_or_indices if i < len(chats)] or chats[:1]
        else:
            targets = chats[:max(1, n_or_indices)]
        log_fn(f'  Чатов в сайдбаре: {len(chats)}, целевых: {len(targets)}', 'dim')
        for i, chat in enumerate(targets):
            log_fn(f'  [{i+1}] {chat["name"][:44]}', 'dim')
            click_rect(chat['rect'], log_fn)
            time.sleep(0.7)
            if not process_current_view():
                log_fn('       ничего не сделано в этом чате', 'dim')
    else:
        log_fn('  Сайдбар с чатами не обнаружен — работаем с текущим видом окна', 'dim')
        process_current_view()

    return ok


# ══════════════════════════════════════════════════════════════════════════════
#  ЗАХВАТ ШАБЛОНА (для резервного варианта)
# ══════════════════════════════════════════════════════════════════════════════

class RegionCapture:
    def __init__(self, root: tk.Tk, on_done, hint_text='Drag a box around the button  •  Esc — cancel'):
        self.root = root
        self.on_done = on_done
        self.start = None
        self.rect_id = None

        self.top = tk.Toplevel(root)
        self.top.attributes('-fullscreen', True)
        self.top.attributes('-alpha', 0.30)
        self.top.attributes('-topmost', True)
        self.top.configure(bg='gray12')
        self.top.config(cursor='crosshair')

        self.canvas = tk.Canvas(self.top, bg='gray12', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.create_text(
            self.top.winfo_screenwidth() // 2, 40,
            text=hint_text,
            fill='white', font=('Segoe UI', 14, 'bold'))

        self.canvas.bind('<ButtonPress-1>', self._down)
        self.canvas.bind('<B1-Motion>', self._move)
        self.canvas.bind('<ButtonRelease-1>', self._up)
        self.top.bind('<Escape>', lambda e: self._cancel())

    def _down(self, e):
        self.start = (e.x_root, e.y_root)
        self.rect_id = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline=ACC, width=2)

    def _move(self, e):
        if self.start and self.rect_id:
            sx, sy = self.start
            self.canvas.coords(self.rect_id,
                               sx - self.top.winfo_rootx(), sy - self.top.winfo_rooty(),
                               e.x, e.y)

    def _up(self, e):
        if not self.start:
            return
        x1, y1 = self.start
        x2, y2 = e.x_root, e.y_root
        left, top, right, bottom = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        self.top.destroy()
        if right - left > 8 and bottom - top > 8:
            self.root.after(150, lambda: self.on_done((left, top, right, bottom)))
        else:
            self.on_done(None)

    def _cancel(self):
        self.top.destroy()
        self.on_done(None)


# ══════════════════════════════════════════════════════════════════════════════
#  ВИДЖЕТЫ
# ══════════════════════════════════════════════════════════════════════════════

class RingTimer(tk.Canvas):
    SZ, R, W = 200, 80, 10

    def __init__(self, parent, **kw):
        super().__init__(parent, width=self.SZ, height=self.SZ,
                         bg=BG, highlightthickness=0, **kw)
        self.draw(0, '--:--:--', 'Не запущено', DIM)

    def draw(self, pct, main, sub, color):
        self.delete('all')
        cx = cy = self.SZ // 2
        r, w = self.R, self.W
        self.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, extent=360,
                        style='arc', outline=C2, width=w)
        if pct > 0.5:
            self.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, extent=-pct*3.6,
                            style='arc', outline=color, width=w)
            if 2 < pct < 98:
                ang = math.radians(90 - pct*3.6)
                ex, ey = cx + r*math.cos(ang), cy - r*math.sin(ang)
                self.create_oval(ex-w//2, ey-w//2, ex+w//2, ey+w//2, fill=color, outline='')
        self.create_text(cx, cy-12, text=main, fill=color, font=('Segoe UI Mono', 22, 'bold'))
        self.create_text(cx, cy+16, text=sub, fill=DIM, font=('Segoe UI', 8))


class Spinner(tk.Frame):
    """+/- кнопки, а число — редактируемое поле: клик и ввод цифр напрямую,
    Enter или клик мимо (потеря фокуса) подтверждает и обрезает по диапазону."""

    def __init__(self, parent, lo=0, hi=23, val=0, on_change=None, big=True, **kw):
        super().__init__(parent, bg=C1, **kw)
        self._lo, self._hi, self._v = lo, hi, val
        self._sv = tk.StringVar(value=f'{val:02d}')
        self._cb = on_change
        fs, px = (20, 8) if big else (13, 6)

        def btn(t, cmd):
            b = tk.Label(self, text=t, bg=C2, fg=DIM,
                         font=('Segoe UI', fs), padx=px, pady=4, cursor='hand2')
            b.bind('<Button-1>', lambda _: cmd())
            b.bind('<Enter>', lambda _, w=b: w.config(fg=TXT, bg=BRD))
            b.bind('<Leave>', lambda _, w=b: w.config(fg=DIM, bg=C2))
            return b

        btn('−', self._dec).pack(side='left')

        self._entry = tk.Entry(self, textvariable=self._sv, bg=C2, fg=TXT,
                               font=('Segoe UI Mono', fs, 'bold'), width=2,
                               justify='center', relief='flat', bd=0,
                               insertbackground=TXT, highlightthickness=1,
                               highlightbackground=C2, highlightcolor=ACC,
                               cursor='xterm')
        self._entry.pack(side='left', padx=2, ipady=3)
        self._entry.bind('<FocusIn>', lambda e: self._entry.select_range(0, 'end'))
        self._entry.bind('<Return>', lambda e: (self._commit(), self.focus_set()))
        self._entry.bind('<FocusOut>', lambda e: self._commit())
        self._entry.bind('<Up>', lambda e: self._inc())
        self._entry.bind('<Down>', lambda e: self._dec())

        btn('+', self._inc).pack(side='left')

    def _commit(self):
        try:
            v = int(self._sv.get().strip() or self._v)
        except ValueError:
            v = self._v
        self.set(v)
        if self._cb: self._cb(self._v)

    def _inc(self):
        self._v = self._lo if self._v >= self._hi else self._v + 1
        self._sv.set(f'{self._v:02d}')
        if self._cb: self._cb(self._v)

    def _dec(self):
        self._v = self._hi if self._v <= self._lo else self._v - 1
        self._sv.set(f'{self._v:02d}')
        if self._cb: self._cb(self._v)

    def get(self): return self._v
    def set(self, v):
        self._v = max(self._lo, min(self._hi, v))
        self._sv.set(f'{self._v:02d}')


def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(c))) for c in rgb)


def _lerp_color(c1, c2, t):
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex((r1 + (r2-r1)*t, g1 + (g2-g1)*t, b1 + (b2-b1)*t))


def _darken(hexcolor, factor=0.85):
    r, g, b = _hex_to_rgb(hexcolor)
    return _rgb_to_hex((r*factor, g*factor, b*factor))


class FlatBtn(tk.Canvas):
    """Кнопка со скруглёнными углами (rounded rect на Canvas) и плавным
    переходом цвета при наведении/нажатии — сохраняет тот же интерфейс,
    что и раньше (.config(text=...), .recolor(...)), чтобы не трогать
    остальной код и раскладку."""

    RADIUS = 8
    _ANIM_STEPS = 7
    _ANIM_DELAY = 12

    def __init__(self, parent, text, cmd, bg, fg, hbg=None, hfg=None,
                font=('Segoe UI', 9), padx=14, pady=8, **kw):
        self._font = font
        self._padx, self._pady = padx, pady
        self._bg, self._fg = bg, fg
        self._hbg, self._hfg = hbg or bg, hfg or fg
        self._cur_bg = bg
        self._cmd = cmd
        self._text = text
        self._anim_job = None
        self._hovering = False

        outer = kw.pop('bg', None) or parent.cget('bg')
        tmp = tk.Label(parent, text=text, font=font)
        tmp.update_idletasks()
        bw = tmp.winfo_reqwidth() + padx * 2
        bh = tmp.winfo_reqheight() + pady * 2
        tmp.destroy()

        # NB: не называть self._w/self._h — эти имена зарезервированы
        # внутри tkinter.Misc (self._w хранит Tk-путь виджета) и будут
        # молча перезаписаны конструктором Canvas ниже.
        self._bw, self._bh = bw, bh
        super().__init__(parent, width=bw, height=bh, bg=outer,
                         highlightthickness=0, cursor='hand2', **kw)
        self._draw(bg, fg)

        self.bind('<Configure>', self._on_resize)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)

    # ── отрисовка ───────────────────────────────────────────────────────────

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        points = [
            x1+r, y1,  x2-r, y1,  x2, y1,  x2, y1+r,  x2, y2-r,  x2, y2,
            x2-r, y2,  x1+r, y2,  x1, y2,  x1, y2-r,  x1, y1+r,  x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _draw(self, bg_color, fg_color):
        self.delete('all')
        self._rounded_rect(0, 0, self._bw, self._bh, self.RADIUS,
                           fill=bg_color, outline=bg_color)
        self.create_text(self._bw/2, self._bh/2, text=self._text,
                         fill=fg_color, font=self._font)

    def _on_resize(self, event):
        if event.width > 1 and event.height > 1:
            self._bw, self._bh = event.width, event.height
            self._draw(self._cur_bg, self._fg)

    # ── анимация hover ──────────────────────────────────────────────────────

    def _animate_to(self, target_bg, target_fg):
        if self._anim_job:
            self.after_cancel(self._anim_job)
        start_bg = self._cur_bg

        def step(i):
            t = i / self._ANIM_STEPS
            color = _lerp_color(start_bg, target_bg, t)
            self._cur_bg = color
            self._draw(color, target_fg)
            if i < self._ANIM_STEPS:
                self._anim_job = self.after(self._ANIM_DELAY, lambda: step(i + 1))
            else:
                self._anim_job = None
        step(1)

    def _on_enter(self, _e):
        self._hovering = True
        self._animate_to(self._hbg, self._hfg)

    def _on_leave(self, _e):
        self._hovering = False
        self._animate_to(self._bg, self._fg)

    def _on_press(self, _e):
        if self._anim_job:
            self.after_cancel(self._anim_job)
            self._anim_job = None
        self._draw(_darken(self._hbg if self._hovering else self._bg), self._hfg)

    def _on_release(self, e):
        inside = 0 <= e.x <= self._bw and 0 <= e.y <= self._bh
        target_bg, target_fg = (self._hbg, self._hfg) if inside else (self._bg, self._fg)
        self._draw(target_bg, target_fg)
        self._cur_bg = target_bg
        if inside:
            self._cmd()

    # ── публичный интерфейс (совместим со старым Label-вариантом) ───────────

    def config(self, **kwargs):
        if 'text' in kwargs:
            self._text = kwargs.pop('text')
            self._draw(self._cur_bg, self._fg)
        if kwargs:
            super().config(**kwargs)

    configure = config

    def recolor(self, bg, fg, hbg=None):
        self._bg, self._fg, self._hbg = bg, fg, hbg or bg
        self._cur_bg = bg
        self._draw(bg, fg)


class Badge(tk.Frame):
    COLORS = {'idle': DIM, 'ok': SUC, 'fail': ERR, 'trying': WARN}

    def __init__(self, parent, name, **kw):
        super().__init__(parent, bg=C1, padx=10, pady=5,
                         highlightthickness=1, highlightbackground=BRD, **kw)
        self._dot = tk.Label(self, text='●', bg=C1, fg=DIM, font=('Segoe UI', 9))
        self._dot.pack(side='left')
        self._name_lbl = tk.Label(self, text=name, bg=C1, fg=DIM, font=('Segoe UI', 8))
        self._name_lbl.pack(side='left', padx=(4, 0))

    def set(self, state):
        self._dot.config(fg=self.COLORS.get(state, DIM))

    def set_name(self, name):
        self._name_lbl.config(text=name)


class RoundedCard(tk.Canvas):
    """Карточка со скруглёнными углами. Дочерние виджеты добавляются в .inner."""

    def __init__(self, master, radius=12, fill=C1, outline=BRD,
                 ipadx=18, ipady=12, **kw):
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, **kw)
        self._r  = radius
        self._fill = fill
        self._ol   = outline
        self.inner = tk.Frame(self, bg=fill, padx=ipadx, pady=ipady)
        self._wid  = self.create_window(radius, radius,
                                        window=self.inner, anchor='nw')
        self.bind('<Configure>', self._on_cv_cfg)
        self.inner.bind('<Configure>',
                        lambda _: self.after_idle(self._sync_height))

    # ── layout ──────────────────────────────────────────────────────────────

    def _on_cv_cfg(self, e=None):
        w = e.width if e else self.winfo_width()
        if w > 2 * self._r:
            self.itemconfigure(self._wid, width=w - 2 * self._r)
        self._draw()

    def _sync_height(self):
        ih = self.inner.winfo_reqheight()
        self.configure(height=ih + 2 * self._r)
        self._draw()

    # ── drawing ─────────────────────────────────────────────────────────────

    def _draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        self.delete('bg')
        r = self._r
        # Дублирование точек на прямых рёбрах «прижимает» B-сплайн к ним,
        # а одиночные угловые точки создают дугу скругления.
        pts = [
            r,0,   r,0,       # ┐ верхнее ребро (левый якорь)
            w-r,0, w-r,0,     # ┘ верхнее ребро (правый якорь)
            w,0,              # ○ угол top-right
            w,r,   w,r,       # ┐ правое ребро (верхний якорь)
            w,h-r, w,h-r,     # ┘ правое ребро (нижний якорь)
            w,h,              # ○ угол bottom-right
            w-r,h, w-r,h,     # ┐ нижнее ребро (правый якорь)
            r,h,   r,h,       # ┘ нижнее ребро (левый якорь)
            0,h,              # ○ угол bottom-left
            0,h-r, 0,h-r,     # ┐ левое ребро (нижний якорь)
            0,r,   0,r,       # ┘ левое ребро (верхний якорь)
            0,0,              # ○ угол top-left
        ]
        self.create_polygon(pts, smooth=True, fill=self._fill, outline=self._ol,
                            width=1, tags='bg')
        self.tag_lower('bg')

    # ── public API ───────────────────────────────────────────────────────────

    def set_outline(self, color):
        self._ol = color
        self._draw()

    def set_fill(self, color):
        self._fill = color
        self.inner.configure(bg=color)
        self._draw()


class TemplateRow(tk.Frame):
    def __init__(self, parent, key: str, app, **kw):
        super().__init__(parent, bg=C1, **kw)
        self.key, self.app, self.tpl = key, app, TEMPLATES[key]

        self.var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, variable=self.var, bg=C1, fg=DIM, selectcolor=C2,
                       activebackground=C1, font=('Segoe UI', 9), cursor='hand2'
                       ).pack(side='left')

        self.thumb = tk.Label(self, bg=C2, width=6, height=2)
        self.thumb.pack(side='left', padx=(2, 8))

        info = tk.Frame(self, bg=C1)
        info.pack(side='left', fill='x', expand=True)
        tk.Label(info, text=self.tpl['label'], bg=C1, fg=TXT,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        self.lbl_status = tk.Label(info, text=app.t('tpl_not_set'), bg=C1, fg=DIM, font=('Segoe UI', 7))
        self.lbl_status.pack(anchor='w')

        self.btn_capture = FlatBtn(self, app.t('capture_btn'), self._capture,
                                   bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                                   font=('Segoe UI', 8), padx=10, pady=5)
        self.btn_capture.pack(side='right', padx=(6, 0))
        self.refresh()

    def refresh(self):
        path = self.tpl['file']
        if os.path.isfile(path) and Image:
            try:
                img = Image.open(path)
                img.thumbnail((48, 28))
                self._photo = ImageTk.PhotoImage(img)
                self.thumb.config(image=self._photo, width=48, height=28)
                self.lbl_status.config(text=f'{img.width}×{img.height} px  ✓', fg=SUC)
            except Exception:
                self.lbl_status.config(text=self.app.t('tpl_read_error'), fg=ERR)
        else:
            self.thumb.config(image='', width=6, height=2)
            self.lbl_status.config(text=self.app.t('tpl_not_set_optional'), fg=DIM)

    def retranslate(self):
        self.btn_capture.config(text=self.app.t('capture_btn'))
        self.refresh()

    def _capture(self):
        self.app.capture_template(self.key, self.refresh)


# ══════════════════════════════════════════════════════════════════════════════
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════════════════════════════════════════

BADGE_KEYS = ['badge_sidebar', 'badge_uia', 'badge_template']


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title('Claude Code Auto-Continue')
        root.geometry('480x880')
        root.minsize(440, 620)

        self.lang = 'ru'
        self._theme = 'dark'
        self._running  = False
        self._stop_evt = threading.Event()
        self._target   = None
        self._total_s  = 1.0
        self._chats_preview = []
        self._last_windows = []
        self._selected_chat_idx: set = set()   # индексы выбранных чатов

        self._plan = []
        self._plan_running = False
        self._plan_stop_evt = threading.Event()
        self._plan_next_target = None

        self._stat_clicks = 0
        self._stat_ok = 0
        self._history: list = []   # [{ts, ok}], max 10

        self._tray_icon = None     # pystray.Icon или None
        self._tray_minimize = tk.BooleanVar(value=True)

        self._log_collapsed = False
        self._log_new_count = 0

        self._cfg: dict = {}       # загруженные настройки

        self._load_settings()
        self._apply_theme_vars()
        self._check_deps()
        self._build()
        self._tick()
        self._scan_now()
        root.protocol('WM_DELETE_WINDOW', self._on_close)

    def t(self, key, **kw):
        s = I18N[self.lang][key]
        return s.format(**kw) if kw else s

    def _check_deps(self):
        missing = []
        if pyautogui is None: missing.append('pyautogui')
        if IS_WIN and not HAS_UIA: missing.append('uiautomation')
        if Image is None: missing.append('pillow')
        self._missing = missing

    # ── Тема ────────────────────────────────────────────────────────────────

    def _apply_theme_vars(self):
        g = globals()
        for k, v in THEMES[self._theme].items():
            g[k] = v
        self.root.configure(bg=BG)

    def _set_theme(self, name: str):
        if name == self._theme:
            return
        self._cfg.update({
            'h':           self._sg('sp_h', self._cfg.get('h', 5)),
            'm':           self._sg('sp_m', self._cfg.get('m', 0)),
            'plan_h':      self._sg('sp_plan_h', self._cfg.get('plan_h', 5)),
            'plan_m':      self._sg('sp_plan_m', self._cfg.get('plan_m', 0)),
            'watch':       self._sgv('v_watch', self._cfg.get('watch', False)),
            'interval':    self._sgv('v_interval', self._cfg.get('interval', '30')),
            'btn_try':     self._sgv('v_btn_try', self._cfg.get('btn_try', True)),
            'btn_cont':    self._sgv('v_btn_cont', self._cfg.get('btn_cont', True)),
            'conf':        self._sgv('v_conf', self._cfg.get('conf', 0.82)),
            'plan_repeat': self._sgv('v_plan_repeat', self._cfg.get('plan_repeat', True)),
            'notif':       self._sgv('v_notif', self._cfg.get('notif', True)),
        })
        self._save_settings()
        self._theme = name
        for w in self.root.winfo_children():
            w.destroy()
        self._apply_theme_vars()
        self._build()

    # ── Настройки ───────────────────────────────────────────────────────────

    def _load_settings(self):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
        except Exception:
            d = {}
        self._cfg = d
        self.lang = d.get('lang', 'ru')
        self._theme = d.get('theme', 'dark')
        self._plan = [tuple(x) for x in d.get('plan', [])]
        self._history = d.get('history', [])[-10:]
        # tray_minimize доступна только после __init__ tk.BooleanVar; обновляем позже
        self._cfg_tray_minimize = d.get('tray_minimize', True)

    def _save_settings(self):
        d = {
            'lang': self.lang,
            'theme': self._theme,
            'h': self._sg('sp_h', 5),
            'm': self._sg('sp_m', 0),
            'watch': self._sgv('v_watch', False),
            'interval': self._sgv('v_interval', '30'),
            'btn_try': self._sgv('v_btn_try', True),
            'btn_cont': self._sgv('v_btn_cont', True),
            'conf': self._sgv('v_conf', 0.82),
            'plan_h': self._sg('sp_plan_h', 5),
            'plan_m': self._sg('sp_plan_m', 0),
            'plan_repeat': self._sgv('v_plan_repeat', True),
            'plan': list(self._plan),
            'history': self._history[-10:],
            'tray_minimize': self._tray_minimize.get(),
            'notif': self._sgv('v_notif', True),
        }
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _sg(self, attr, default):
        try: return getattr(self, attr).get()
        except Exception: return default

    def _sgv(self, attr, default):
        try: return getattr(self, attr).get()
        except Exception: return default

    def _on_close(self):
        if HAS_TRAY and self._tray_minimize.get():
            self._minimize_to_tray()
        else:
            self._quit_app()

    def _quit_app(self):
        self._save_settings()
        if self._tray_icon is not None:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        self.root.destroy()

    def _make_tray_image(self):
        """16×16 PNG-иконка для трея — синий круг."""
        if Image is None:
            return None
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        try:
            from PIL import ImageDraw
            d = ImageDraw.Draw(img)
            d.ellipse([4, 4, 60, 60], fill=(88, 166, 255, 255))
            d.text((22, 18), '▶', fill=(13, 17, 23, 255))
        except Exception:
            pass
        return img

    def _minimize_to_tray(self):
        if not HAS_TRAY:
            self._quit_app()
            return
        self.root.withdraw()
        if self._tray_icon is not None:
            return  # уже в трее
        img = self._make_tray_image()
        if img is None:
            self._quit_app()
            return
        menu = pystray.Menu(
            pystray.MenuItem(self.t('tray_show'), self._show_from_tray, default=True),
            pystray.MenuItem(self.t('tray_quit'), lambda _icon, _item: self._schedule_quit()),
        )
        icon = pystray.Icon('claude-auto-continue', img, 'Claude Auto-Continue', menu)
        self._tray_icon = icon
        threading.Thread(target=icon.run, daemon=True).start()

    def _show_from_tray(self, _icon=None, _item=None):
        self.root.after(0, self._restore_from_tray)

    def _restore_from_tray(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self._tray_icon is not None:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None

    def _schedule_quit(self):
        self.root.after(0, self._quit_app)

    # ── Уведомления Windows ────────────────────────────────────────────────

    def _notify(self, ok: int):
        if not HAS_NOTIF:
            return
        if not hasattr(self, 'v_notif') or not self.v_notif.get():
            return
        try:
            title = self.t('notif_title')
            msg = self.t('notif_ok', n=ok) if ok else self.t('notif_fail')
            _plyer_notif.notify(title=title, message=msg,
                                app_name='Claude Auto-Continue', timeout=5)
        except Exception:
            pass

    # ── Автозапуск (Windows + macOS) ──────────────────────────────────────

    def _get_autostart(self) -> bool:
        if IS_MAC:
            plist = os.path.expanduser('~/Library/LaunchAgents/com.claude.autocontinue.plist')
            return os.path.exists(plist)
        if winreg is None:
            return False
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_READ)
            winreg.QueryValueEx(k, 'ClaudeAutoContinue')
            winreg.CloseKey(k)
            return True
        except Exception:
            return False

    def _toggle_autostart(self):
        if IS_MAC:
            self._toggle_autostart_mac()
            return
        if winreg is None:
            self._log('winreg недоступен', 'error')
            return
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run', 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ)
            on = False
            try:
                winreg.QueryValueEx(k, 'ClaudeAutoContinue')
                on = True
            except FileNotFoundError:
                pass
            if on:
                winreg.DeleteValue(k, 'ClaudeAutoContinue')
            else:
                cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(k, 'ClaudeAutoContinue', 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(k)
            self._update_autostart_btn()
        except Exception as e:
            self._log(f'Autostart error: {e}', 'error')

    def _toggle_autostart_mac(self):
        import subprocess as _sp
        plist_dir = os.path.expanduser('~/Library/LaunchAgents')
        plist_path = os.path.join(plist_dir, 'com.claude.autocontinue.plist')
        if os.path.exists(plist_path):
            try:
                _sp.run(['launchctl', 'unload', plist_path], capture_output=True, timeout=5)
                os.remove(plist_path)
            except Exception as e:
                self._log(f'Autostart off error: {e}', 'error')
        else:
            try:
                os.makedirs(plist_dir, exist_ok=True)
                py = sys.executable
                script = os.path.abspath(__file__)
                plist = (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0"><dict>\n'
                    '  <key>Label</key><string>com.claude.autocontinue</string>\n'
                    f'  <key>ProgramArguments</key><array>'
                    f'<string>{py}</string><string>{script}</string></array>\n'
                    '  <key>RunAtLoad</key><true/>\n'
                    '</dict></plist>\n'
                )
                with open(plist_path, 'w') as f:
                    f.write(plist)
                _sp.run(['launchctl', 'load', plist_path], capture_output=True, timeout=5)
            except Exception as e:
                self._log(f'Autostart on error: {e}', 'error')
        self._update_autostart_btn()

    def _update_autostart_btn(self):
        if hasattr(self, 'btn_autostart'):
            on = self._get_autostart()
            self.btn_autostart.config(
                text=self.t('autostart_on') if on else self.t('autostart_off'))

    # ── Статистика и история ──────────────────────────────────────────────

    def _stat_click(self, ok_count: int):
        self._stat_clicks += 1
        if ok_count > 0:
            self._stat_ok += 1
        self.root.after(0, self._update_stats_label)

    def _update_stats_label(self):
        if not hasattr(self, 'lbl_stats'):
            return
        if self._stat_clicks == 0:
            self.lbl_stats.config(text='')
            return
        pct = int(self._stat_ok / self._stat_clicks * 100)
        self.lbl_stats.config(
            text=self.t('stats_session',
                        clicks=self._stat_clicks, ok=self._stat_ok, pct=pct),
            fg=SUC if pct >= 50 else WARN)

    def _add_history(self, ok: int):
        ts = datetime.datetime.now().strftime('%d.%m %H:%M')
        self._history.append({'ts': ts, 'ok': ok})
        self._history = self._history[-10:]
        self._save_settings()
        self.root.after(0, self._refresh_history)

    def _refresh_history(self):
        if not hasattr(self, 'history_list_frame'):
            return
        for w in self.history_list_frame.winfo_children():
            w.destroy()
        if not self._history:
            tk.Label(self.history_list_frame, text=self.t('history_empty'),
                     bg=BG, fg=DIM, font=('Segoe UI', 8)).pack(anchor='w')
            return
        for e in reversed(self._history):
            col = SUC if e['ok'] > 0 else ERR
            result = self.t('history_ok', n=e['ok']) if e['ok'] > 0 else self.t('history_fail')
            tk.Label(self.history_list_frame,
                     text=f"  {e['ts']}  →  {result}",
                     bg=BG, fg=col, font=('Segoe UI', 8)).pack(anchor='w')

    # ── Выбор чатов ───────────────────────────────────────────────────────

    def _chat_select_all(self):
        self._selected_chat_idx = set(range(len(self._chats_preview)))
        self._refresh_chat_list()

    def _chat_select_none(self):
        self._selected_chat_idx = set()
        self._refresh_chat_list()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Фиксированная шапка ─────────────────────────────────────────────
        langbar = tk.Frame(self.root, bg=BG, pady=5)
        langbar.pack(fill='x', side='top')

        # ── Левая часть: чекбоксы трей / уведомления ─────────────────────
        langleft = tk.Frame(langbar, bg=BG)
        langleft.pack(side='left', padx=14)
        self._tray_minimize.set(self._cfg_tray_minimize)
        if HAS_TRAY:
            tk.Checkbutton(langleft, text=self.t('tray_minimize'),
                           variable=self._tray_minimize,
                           bg=BG, fg=DIM, selectcolor=C2, activebackground=BG,
                           activeforeground=TXT, font=('Segoe UI', 8),
                           cursor='hand2').pack(anchor='w')
        self.v_notif = tk.BooleanVar(value=self._cfg.get('notif', True))
        if HAS_NOTIF:
            tk.Checkbutton(langleft,
                           text=('🔔 Уведомления' if self.lang == 'ru' else '🔔 Notifications'),
                           variable=self.v_notif,
                           bg=BG, fg=DIM, selectcolor=C2, activebackground=BG,
                           activeforeground=TXT, font=('Segoe UI', 8),
                           cursor='hand2').pack(anchor='w')

        langwrap = tk.Frame(langbar, bg=BG)
        langwrap.pack(side='right', padx=18)
        # Кнопки: тема / автозапуск / RU / EN
        next_theme = 'light' if self._theme == 'dark' else 'dark'
        self.btn_theme = FlatBtn(langwrap,
                                  self.t('theme_light') if self._theme == 'dark' else self.t('theme_dark'),
                                  lambda: self._set_theme(next_theme),
                                  bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                                  font=('Segoe UI', 8), padx=8, pady=3)
        self.btn_theme.pack(side='left', padx=(0, 6))
        on = self._get_autostart()
        self.btn_autostart = FlatBtn(langwrap,
                                      self.t('autostart_on') if on else self.t('autostart_off'),
                                      self._toggle_autostart,
                                      bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                                      font=('Segoe UI', 8), padx=8, pady=3)
        self.btn_autostart.pack(side='left', padx=(0, 6))
        self.btn_lang_ru = FlatBtn(langwrap, 'RU', lambda: self._set_lang('ru'),
                                   bg=ACC if self.lang == 'ru' else C2,
                                   fg=BG if self.lang == 'ru' else DIM,
                                   hbg=ACC, hfg=BG,
                                   font=('Segoe UI', 8, 'bold'), padx=10, pady=3)
        self.btn_lang_ru.pack(side='left', padx=(0, 3))
        self.btn_lang_en = FlatBtn(langwrap, 'EN', lambda: self._set_lang('en'),
                                   bg=ACC if self.lang == 'en' else C2,
                                   fg=BG if self.lang == 'en' else DIM,
                                   hbg=ACC, hfg=BG,
                                   font=('Segoe UI', 8, 'bold'), padx=10, pady=3)
        self.btn_lang_en.pack(side='left')

        hdr = tk.Frame(self.root, bg=C1, pady=12)
        hdr.pack(fill='x', side='top')
        tk.Label(hdr, text='⚡', bg=C1, fg=ACC, font=('Segoe UI', 16)).pack(side='left', padx=(20, 0))
        tk.Label(hdr, text='Claude Code  Auto-Continue', bg=C1, fg=TXT,
                 font=('Segoe UI', 12, 'bold')).pack(side='left', padx=10)
        tk.Frame(self.root, bg=ACC, height=2).pack(fill='x', side='top')

        # ── Кольцевой таймер (фиксированный, всегда виден) ──────────────────
        ring_frame = tk.Frame(self.root, bg=BG, pady=10)
        ring_frame.pack(side='top', fill='x')
        self.ring = RingTimer(ring_frame)
        self.ring.pack()
        self.lbl_hint = tk.Label(ring_frame, text='', bg=BG, fg=DIM,
                                 font=('Segoe UI', 8))
        self.lbl_hint.pack(pady=(2, 0))

        # ── Фиксированный лог внизу ─────────────────────────────────────────
        self._log_area = tk.Frame(self.root, bg=BG)
        self._log_area.pack(fill='both', side='bottom', expand=False)
        tk.Frame(self._log_area, bg=BRD, height=1).pack(fill='x')

        # Заголовок (всегда виден, кликабелен)
        lh = tk.Frame(self._log_area, bg=BG, padx=16, cursor='hand2')
        lh.pack(fill='x', pady=(4, 2))
        self._log_arrow = tk.Label(lh, text='▾', bg=BG, fg=DIM,
                                   font=('Segoe UI', 9), cursor='hand2')
        self._log_arrow.pack(side='left')
        self.lbl_log_title = tk.Label(lh, text=self.t('log_title'), bg=BG, fg=DIM,
                                      font=('Segoe UI', 8, 'bold'), cursor='hand2')
        self.lbl_log_title.pack(side='left', padx=(4, 0))
        self._log_badge = tk.Label(lh, text='', bg=ACC, fg=BG,
                                   font=('Segoe UI', 7, 'bold'), padx=5, pady=1)
        # badge упакуется позже когда нужен
        self.btn_clear = FlatBtn(lh, self.t('clear_btn'), self._clear_log,
                                 bg=BG, fg=DIM, hfg=TXT, font=('Segoe UI', 8))
        self.btn_clear.pack(side='right')
        for w in (lh, self._log_arrow, self.lbl_log_title):
            w.bind('<Button-1>', lambda _: self._toggle_log())

        # Тело лога (сворачивается)
        self._log_body = tk.Frame(self._log_area, bg=BG)
        self._log_body.pack(fill='both', expand=True)
        self.log = tk.Text(self._log_body, bg=C1, fg=TXT, font=('Consolas', 8),
                           relief='flat', bd=0, state='disabled', wrap='word',
                           insertbackground=TXT, height=7, padx=12, pady=6)
        self.log.pack(fill='both', expand=True)
        for tag, fg in [('success', SUC), ('error', ERR), ('warn', WARN),
                        ('dim', DIM), ('accent', ACC)]:
            self.log.tag_config(tag, foreground=fg)

        # Начальное состояние: лог пустой — сворачиваем
        self._log_collapsed = True
        self._log_body.pack_forget()
        self._log_arrow.config(text='▸')

        # ── Прокручиваемая средняя часть ────────────────────────────────────
        scroll_outer = tk.Frame(self.root, bg=BG)
        scroll_outer.pack(fill='both', expand=True, side='top')

        self._main_sb = tk.Scrollbar(scroll_outer, orient='vertical',
                                      bg=C2, troughcolor=BG, activebackground=BRD)
        self._main_sb.pack(side='right', fill='y')
        self._main_canvas = tk.Canvas(scroll_outer, bg=BG, highlightthickness=0,
                                       yscrollcommand=self._main_sb.set)
        self._main_canvas.pack(side='left', fill='both', expand=True)
        self._main_sb.config(command=self._main_canvas.yview)

        body = tk.Frame(self._main_canvas, bg=BG, padx=20)
        self._body_win = self._main_canvas.create_window((0, 0), window=body, anchor='nw')

        body.bind('<Configure>', lambda e: self._main_canvas.configure(
            scrollregion=self._main_canvas.bbox('all')))
        self._main_canvas.bind('<Configure>', lambda e: self._main_canvas.itemconfig(
            self._body_win, width=e.width))

        self.root.bind_all('<MouseWheel>', self._dispatch_scroll)

        # ── Предупреждение о зависимостях ───────────────────────────────────
        self.warn_frame = None
        self.lbl_missing = None
        if self._missing:
            self.warn_frame = tk.Frame(body, bg='#3d2f0a', padx=14, pady=10)
            self.warn_frame.pack(fill='x', pady=(14, 0))
            self.lbl_missing = tk.Label(
                self.warn_frame, text=self._missing_text(), bg='#3d2f0a', fg=WARN,
                font=('Segoe UI', 8), justify='left')
            self.lbl_missing.pack(anchor='w')

        tk.Frame(body, bg=BG, height=10).pack()

        # ── Карточка: одиночный запуск ───────────────────────────────────────
        self._tc = RoundedCard(body, radius=12, fill=C1, outline=BRD,
                               ipadx=18, ipady=12)
        self._tc.pack(fill='x')
        self.lbl_trigger_at = tk.Label(self._tc.inner, text=self.t('trigger_at'),
                                       bg=C1, fg=DIM, font=('Segoe UI', 9, 'bold'))
        self.lbl_trigger_at.pack(anchor='w', pady=(0, 8))
        trow = tk.Frame(self._tc.inner, bg=C1)
        trow.pack()
        self.sp_h = Spinner(trow, lo=0, hi=23, val=self._cfg.get('h', 5))
        self.sp_h.pack(side='left')
        tk.Label(trow, text=':', bg=C1, fg=TXT, font=('Segoe UI Mono', 22, 'bold')
                 ).pack(side='left', padx=10)
        self.sp_m = Spinner(trow, lo=0, hi=59, val=self._cfg.get('m', 0))
        self.sp_m.pack(side='left')
        self.btn_now = FlatBtn(trow, self.t('now_btn'), self._click_now,
                               bg=BG, fg=DIM, hbg=C2, hfg=TXT,
                               font=('Segoe UI', 9), padx=12, pady=8)
        self.btn_now.pack(side='left', padx=(18, 0))

        tk.Frame(body, bg=BG, height=10).pack()
        self.main_btn = FlatBtn(body, self.t('start_btn'), self._toggle, bg=ACC, fg=BG,
                                hbg='#79b8ff', hfg=BG,
                                font=('Segoe UI', 11, 'bold'), padx=20, pady=12)
        self.main_btn.pack(fill='x')

        tk.Frame(body, bg=BG, height=8).pack()
        opts = tk.Frame(body, bg=BG)
        opts.pack(fill='x')
        self.v_watch = tk.BooleanVar(value=self._cfg.get('watch', False))
        self.chk_watch = tk.Checkbutton(
            opts, text=self.t('watch_label'), variable=self.v_watch,
            bg=BG, fg=DIM, selectcolor=C2, activebackground=BG,
            activeforeground=TXT, font=('Segoe UI', 9), cursor='hand2')
        self.chk_watch.pack(side='left')
        self.v_interval = tk.StringVar(value=str(self._cfg.get('interval', '30')))
        tk.Spinbox(opts, from_=5, to=600, textvariable=self.v_interval, width=3,
                   bg=C2, fg=TXT, relief='flat', bd=0, font=('Segoe UI', 9),
                   buttonbackground=C2, insertbackground=TXT).pack(side='left', padx=6)
        self.lbl_sec = tk.Label(opts, text=self.t('sec'), bg=BG, fg=DIM, font=('Segoe UI', 9))
        self.lbl_sec.pack(side='left')

        # ── Карточка: план запусков ──────────────────────────────────────────
        tk.Frame(body, bg=BG, height=10).pack()
        self._pc = RoundedCard(body, radius=12, fill=C1, outline=BRD,
                               ipadx=18, ipady=12)
        self._pc.pack(fill='x')
        self.lbl_plan_title = tk.Label(self._pc.inner, text=self.t('plan_title'),
                                       bg=C1, fg=DIM, font=('Segoe UI', 9, 'bold'))
        self.lbl_plan_title.pack(anchor='w', pady=(0, 8))

        prow = tk.Frame(self._pc.inner, bg=C1)
        prow.pack(fill='x')
        self.sp_plan_h = Spinner(prow, lo=0, hi=23, val=self._cfg.get('plan_h', 5), big=False)
        self.sp_plan_h.pack(side='left')
        tk.Label(prow, text=':', bg=C1, fg=TXT, font=('Segoe UI Mono', 14, 'bold')
                 ).pack(side='left', padx=6)
        self.sp_plan_m = Spinner(prow, lo=0, hi=59, val=self._cfg.get('plan_m', 0), big=False)
        self.sp_plan_m.pack(side='left')
        self.btn_plan_add = FlatBtn(prow, self.t('plan_add_btn'), self._plan_add,
                                    bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                                    font=('Segoe UI', 9), padx=12, pady=6)
        self.btn_plan_add.pack(side='left', padx=(12, 0))

        self.plan_list_frame = tk.Frame(self._pc.inner, bg=C1)
        self.plan_list_frame.pack(fill='x', pady=(8, 0))

        self.v_plan_repeat = tk.BooleanVar(value=self._cfg.get('plan_repeat', True))
        self.chk_plan_repeat = tk.Checkbutton(
            self._pc.inner, text=self.t('plan_repeat'), variable=self.v_plan_repeat,
            bg=C1, fg=DIM, selectcolor=C2, activebackground=C1,
            activeforeground=TXT, font=('Segoe UI', 9), cursor='hand2')
        self.chk_plan_repeat.pack(anchor='w', pady=(8, 0))

        self.lbl_plan_status = tk.Label(self._pc.inner, text=self.t('plan_status_idle'),
                                        bg=C1, fg=DIM, font=('Segoe UI', 8),
                                        justify='left', anchor='w')
        self.lbl_plan_status.pack(fill='x', pady=(6, 4))

        self.btn_plan_start = FlatBtn(self._pc.inner, self.t('plan_start_btn'), self._toggle_plan,
                                      bg=C2, fg=TXT, hbg=BRD, hfg=TXT,
                                      font=('Segoe UI', 10, 'bold'), padx=16, pady=10)
        self.btn_plan_start.pack(fill='x')

        # ── Карточка: Claude Desktop + чаты ─────────────────────────────────
        tk.Frame(body, bg=BG, height=10).pack()
        _wc_card = RoundedCard(body, radius=12, fill=C1, outline=BRD,
                               ipadx=18, ipady=12)
        _wc_card.pack(fill='x')
        wc = _wc_card.inner

        wh = tk.Frame(wc, bg=C1)
        wh.pack(fill='x')
        tk.Label(wh, text='Claude Desktop', bg=C1, fg=DIM,
                 font=('Segoe UI', 9, 'bold')).pack(side='left')
        self.btn_find = FlatBtn(wh, self.t('find_btn'), self._scan_now,
                                bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                                font=('Segoe UI', 8), padx=10, pady=4)
        self.btn_find.pack(side='right')

        self.lbl_app_status = tk.Label(wc, text='…', bg=C1, fg=DIM,
                                       font=('Segoe UI', 8), justify='left', anchor='w')
        self.lbl_app_status.pack(fill='x', pady=(8, 0))

        nr = tk.Frame(wc, bg=C1)
        nr.pack(fill='x', pady=(10, 0))
        self.lbl_switch_first = tk.Label(nr, text=self.t('switch_first'), bg=C1, fg=DIM,
                                         font=('Segoe UI', 9))
        self.lbl_switch_first.pack(side='left')
        self.lbl_chat_selected = tk.Label(nr, text='', bg=C1, fg=ACC,
                                          font=('Segoe UI', 8))
        self.lbl_chat_selected.pack(side='left', padx=(8, 0))
        FlatBtn(nr, self.t('chat_sel_all'), self._chat_select_all,
                bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                font=('Segoe UI', 8), padx=8, pady=2).pack(side='right', padx=(4, 0))
        FlatBtn(nr, self.t('chat_sel_none'), self._chat_select_none,
                bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                font=('Segoe UI', 8), padx=8, pady=2).pack(side='right', padx=(4, 0))

        # Сворачиваемый список чатов
        self._chat_collapsed = False
        chat_hdr = tk.Frame(wc, bg=C1, cursor='hand2')
        chat_hdr.pack(fill='x', pady=(10, 0))
        self.chat_arrow = tk.Label(chat_hdr, text='▾', bg=C1, fg=ACC,
                                   font=('Segoe UI', 9), cursor='hand2')
        self.chat_arrow.pack(side='left')
        self.lbl_chat_list_title = tk.Label(chat_hdr, text=self.t('chat_list_title'),
                                            bg=C1, fg=DIM, font=('Segoe UI', 8),
                                            cursor='hand2')
        self.lbl_chat_list_title.pack(side='left', padx=(4, 0))

        def _chdr_enter(_e):
            chat_hdr.config(bg=C2)
            self.chat_arrow.config(bg=C2)
            self.lbl_chat_list_title.config(bg=C2)

        def _chdr_leave(_e):
            chat_hdr.config(bg=C1)
            self.chat_arrow.config(bg=C1)
            self.lbl_chat_list_title.config(bg=C1)

        for w in (chat_hdr, self.chat_arrow, self.lbl_chat_list_title):
            w.bind('<Button-1>', lambda _e: self._toggle_chat_list())
            w.bind('<Enter>', _chdr_enter)
            w.bind('<Leave>', _chdr_leave)

        self._sep_after_chats = tk.Frame(wc, bg=BRD, height=1)
        self._sep_after_chats.pack(fill='x', pady=(8, 6))

        self.chat_list_outer = tk.Frame(wc, bg=C1)
        self.chat_list_outer.pack(fill='x', pady=(4, 0), before=self._sep_after_chats)
        self._chat_canvas = tk.Canvas(self.chat_list_outer, bg=C1, height=90,
                                      highlightthickness=0)
        self._chat_scroll = tk.Scrollbar(self.chat_list_outer, orient='vertical',
                                         command=self._chat_canvas.yview)
        self.chat_list = tk.Frame(self._chat_canvas, bg=C1)
        self._chat_canvas_win = self._chat_canvas.create_window(
            (0, 0), window=self.chat_list, anchor='nw')
        self._chat_canvas.configure(yscrollcommand=self._chat_scroll.set)
        self._chat_canvas.pack(side='left', fill='both', expand=True)
        self._chat_scroll.pack(side='right', fill='y')

        self.chat_list.bind('<Configure>', lambda e: self._chat_canvas.configure(
            scrollregion=self._chat_canvas.bbox('all')))
        self._chat_canvas.bind('<Configure>', lambda e: self._chat_canvas.itemconfig(
            self._chat_canvas_win, width=e.width))

        brow = tk.Frame(wc, bg=C1)
        brow.pack(fill='x', pady=(4, 0))
        self.lbl_per_chat = tk.Label(brow, text=self.t('per_chat'), bg=C1, fg=DIM,
                                     font=('Segoe UI', 8, 'bold'))
        self.lbl_per_chat.pack(anchor='w')

        self.v_btn_try  = tk.BooleanVar(value=self._cfg.get('btn_try', True))
        row_try = tk.Frame(wc, bg=C1)
        row_try.pack(fill='x', pady=(5, 0))
        tk.Checkbutton(row_try, text='Try again', variable=self.v_btn_try,
                       bg=C1, fg=DIM, selectcolor=C2, activebackground=C1,
                       activeforeground=TXT, font=('Segoe UI', 9), cursor='hand2'
                       ).pack(side='left')
        self.lbl_try_desc = tk.Label(row_try, text=self.t('try_again_desc'),
                                     bg=C1, fg=DIM, font=('Segoe UI', 7))
        self.lbl_try_desc.pack(side='left')

        self.v_btn_cont = tk.BooleanVar(value=self._cfg.get('btn_cont', True))
        row_cont = tk.Frame(wc, bg=C1)
        row_cont.pack(fill='x', pady=(3, 0))
        tk.Checkbutton(row_cont, text='Continue', variable=self.v_btn_cont,
                       bg=C1, fg=DIM, selectcolor=C2, activebackground=C1,
                       activeforeground=TXT, font=('Segoe UI', 9), cursor='hand2'
                       ).pack(side='left')
        self.lbl_cont_desc = tk.Label(row_cont, text=self.t('continue_desc'),
                                      bg=C1, fg=DIM, font=('Segoe UI', 7))
        self.lbl_cont_desc.pack(side='left')

        self.btn_check_now = FlatBtn(wc, self.t('check_now_btn'), self._test_find,
                                     bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                                     font=('Segoe UI', 8), padx=10, pady=6)
        self.btn_check_now.pack(fill='x', pady=(10, 0))

        # ── Резервный вариант: шаблоны ───────────────────────────────────────
        tk.Frame(body, bg=BG, height=10).pack()
        _tc2_card = RoundedCard(body, radius=12, fill=C1, outline=BRD,
                                ipadx=18, ipady=12)
        _tc2_card.pack(fill='x')
        tc2 = _tc2_card.inner
        self.lbl_fallback_title = tk.Label(tc2, text=self.t('fallback_title'), bg=C1, fg=DIM,
                                           font=('Segoe UI', 8, 'bold'))
        self.lbl_fallback_title.pack(anchor='w', pady=(0, 8))
        self.tpl_rows = {}
        for key in TEMPLATES:
            row = TemplateRow(tc2, key, self)
            row.pack(fill='x', pady=3)
            self.tpl_rows[key] = row
        cr = tk.Frame(tc2, bg=C1)
        cr.pack(fill='x', pady=(8, 0))
        self.lbl_accuracy = tk.Label(cr, text=self.t('accuracy'), bg=C1, fg=DIM, font=('Segoe UI', 9))
        self.lbl_accuracy.pack(side='left')
        self.v_conf = tk.DoubleVar(value=self._cfg.get('conf', 0.82))
        tk.Scale(cr, from_=0.5, to=0.99, resolution=0.01, orient='horizontal',
                 variable=self.v_conf, bg=C1, fg=DIM, troughcolor=C2,
                 highlightthickness=0, bd=0, length=140, font=('Segoe UI', 7)
                 ).pack(side='left', padx=8)

        # ── Бейджи ───────────────────────────────────────────────────────────
        tk.Frame(body, bg=BG, height=8).pack()
        br = tk.Frame(body, bg=BG)
        br.pack(anchor='w')
        self.badges = [Badge(br, self.t(k)) for k in BADGE_KEYS]
        for b in self.badges: b.pack(side='left', padx=(0, 8))

        # ── Статистика сессии ─────────────────────────────────────────────────
        self.lbl_stats = tk.Label(body, text='', bg=BG, fg=SUC,
                                  font=('Segoe UI', 8), anchor='w')
        self.lbl_stats.pack(fill='x', padx=2, pady=(6, 0))

        # ── История срабатываний ──────────────────────────────────────────────
        tk.Frame(body, bg=BG, height=8).pack()
        _hist_card = RoundedCard(body, radius=12, fill=C1, outline=BRD,
                                 ipadx=14, ipady=10)
        _hist_card.pack(fill='x')
        tk.Label(_hist_card.inner, text=self.t('history_title'), bg=C1, fg=DIM,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 6))
        self.history_list_frame = tk.Frame(_hist_card.inner, bg=C1)
        self.history_list_frame.pack(fill='x')
        self._refresh_history()

        tk.Frame(body, bg=BG, height=12).pack()

    def _missing_text(self) -> str:
        return self.t('missing', deps=", ".join(self._missing),
                      installs=" ".join(self._missing))

    # ── Язык ────────────────────────────────────────────────────────────────

    def _set_lang(self, lang: str):
        if lang == self.lang:
            return
        self.lang = lang
        if lang == 'ru':
            self.btn_lang_ru.recolor(ACC, BG, hbg=ACC)
            self.btn_lang_en.recolor(C2, DIM, hbg=BRD)
        else:
            self.btn_lang_en.recolor(ACC, BG, hbg=ACC)
            self.btn_lang_ru.recolor(C2, DIM, hbg=BRD)

        if self.lbl_missing:
            self.lbl_missing.config(text=self._missing_text())
        self.lbl_trigger_at.config(text=self.t('trigger_at'))
        self.btn_now.config(text=self.t('now_btn'))
        self.main_btn.config(text=self.t('stop_btn') if self._running else self.t('start_btn'))
        self.chk_watch.config(text=self.t('watch_label'))
        self.lbl_sec.config(text=self.t('sec'))
        self.btn_find.config(text=self.t('find_btn'))
        self.lbl_switch_first.config(text=self.t('switch_first'))
        self._update_selected_label()
        self.lbl_per_chat.config(text=self.t('per_chat'))
        self.lbl_try_desc.config(text=self.t('try_again_desc'))
        self.lbl_cont_desc.config(text=self.t('continue_desc'))
        self.btn_check_now.config(text=self.t('check_now_btn'))
        self.lbl_fallback_title.config(text=self.t('fallback_title'))
        self.lbl_accuracy.config(text=self.t('accuracy'))
        self.lbl_log_title.config(text=self.t('log_title'))
        self.btn_clear.config(text=self.t('clear_btn'))
        self.lbl_chat_list_title.config(text=self.t('chat_list_title'))
        for b, k in zip(self.badges, BADGE_KEYS):
            b.set_name(self.t(k))
        for row in self.tpl_rows.values():
            row.retranslate()
        self.lbl_plan_title.config(text=self.t('plan_title'))
        self.btn_plan_add.config(text=self.t('plan_add_btn'))
        self.chk_plan_repeat.config(text=self.t('plan_repeat'))
        self.btn_plan_start.config(
            text=self.t('plan_stop_btn') if self._plan_running else self.t('plan_start_btn'))
        self._refresh_plan_list()
        self._update_plan_status()
        self._update_scan(self._last_windows, self._chats_preview)

    # ── Сворачиваемый / прокручиваемый список чатов ──────────────────────────

    def _dispatch_scroll(self, event):
        w = event.widget
        while w is not None:
            if w is getattr(self, '_chat_canvas', None):
                self._chat_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
                return
            if isinstance(w, tk.Text):
                return  # text widget handles it natively
            try:
                w = w.master
            except AttributeError:
                break
        if hasattr(self, '_main_canvas'):
            self._main_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _toggle_chat_list(self):
        self._chat_collapsed = not self._chat_collapsed
        if self._chat_collapsed:
            self.chat_list_outer.pack_forget()
            self.chat_arrow.config(text='▸')
        else:
            self.chat_list_outer.pack(fill='x', pady=(4, 0), before=self._sep_after_chats)
            self.chat_arrow.config(text='▾')
        if hasattr(self, '_main_canvas'):
            self.root.after(50, lambda: self._main_canvas.configure(
                scrollregion=self._main_canvas.bbox('all')))

    # ── Сканирование окна и чатов ────────────────────────────────────────────

    def _scan_now(self):
        def run():
            windows = find_claude_windows(self._slog)
            chats = []
            if windows:
                chats = find_sidebar_chats(windows[0]['ctrl'], self._slog)
            self.root.after(0, lambda: self._update_scan(windows, chats))
        threading.Thread(target=run, daemon=True).start()

    def _update_scan(self, windows, chats):
        self._last_windows = windows
        self._chats_preview = chats
        # Автовыбор первых 3 при первом обнаружении чатов
        if chats and not self._selected_chat_idx:
            self._selected_chat_idx = set(range(min(3, len(chats))))
        if not windows:
            self.lbl_app_status.config(text=self.t('app_not_found'), fg=WARN)
        else:
            title = (windows[0]['title'] or 'Claude')[:40]
            if chats:
                self.lbl_app_status.config(
                    text=self.t('app_found_chats', title=title, n=len(chats)), fg=SUC)
            else:
                self.lbl_app_status.config(
                    text=self.t('app_found_no_sidebar', title=title), fg=WARN)
        self._refresh_chat_list()

    def _refresh_chat_list(self):
        for w in self.chat_list.winfo_children():
            w.destroy()
        chats = self._chats_preview
        if not chats:
            if hasattr(self, 'lbl_chat_selected'):
                self.lbl_chat_selected.config(text='')
            return
        for i, c in enumerate(chats):
            active = i in self._selected_chat_idx
            row = tk.Frame(self.chat_list, bg=C1, cursor='hand2')
            row.pack(fill='x', pady=1)
            chk_var = tk.BooleanVar(value=active)

            def _toggle(idx=i, var=chk_var):
                if var.get():
                    self._selected_chat_idx.add(idx)
                else:
                    self._selected_chat_idx.discard(idx)
                self._update_selected_label()

            chk = tk.Checkbutton(row, variable=chk_var, bg=C1,
                                 activebackground=C2, selectcolor=C2,
                                 fg=ACC, activeforeground=ACC,
                                 command=_toggle, cursor='hand2')
            chk.pack(side='left')
            name = c['name'][:40] + ('…' if len(c['name']) > 40 else '')
            lbl = tk.Label(row, text=name, bg=C1,
                           fg=TXT if active else DIM, font=('Segoe UI', 8),
                           cursor='hand2')
            lbl.pack(side='left', padx=(2, 0))
            # Клик по тексту тоже переключает галочку
            lbl.bind('<Button-1>', lambda _e, v=chk_var, t=_toggle: (v.set(not v.get()), t()))
        self._update_selected_label()
        row_h = 22
        new_h = min(len(chats) * row_h + 4, 5 * row_h + 4)
        self._chat_canvas.configure(height=new_h)
        self._chat_canvas.yview_moveto(0)

    def _update_selected_label(self):
        if not hasattr(self, 'lbl_chat_selected'):
            return
        total = len(self._chats_preview)
        n = len(self._selected_chat_idx)
        if total == 0:
            self.lbl_chat_selected.config(text='')
        else:
            self.lbl_chat_selected.config(
                text=self.t('chat_selected', n=n, total=total))


    # ── Захват шаблона ──────────────────────────────────────────────────────

    def capture_template(self, key: str, on_refreshed):
        if ImageGrab is None:
            self._log(self.t('log_no_pillow'), 'error')
            return
        self.root.iconify()
        self.root.after(350, lambda: self._start_capture(key, on_refreshed))

    def _start_capture(self, key, on_refreshed):
        def done(bbox):
            self.root.deiconify()
            if not bbox:
                self._log(self.t('log_capture_cancelled'), 'dim')
                return
            try:
                img = ImageGrab.grab(bbox=bbox)
                img.save(TEMPLATES[key]['file'])
                self._log(self.t('log_capture_saved', label=TEMPLATES[key]['label'],
                                 w=img.width, h=img.height), 'success')
                on_refreshed()
            except Exception as e:
                self._log(self.t('log_capture_error', e=e), 'error')
        RegionCapture(self.root, done, hint_text=self.t('capture_hint'))

    # ── Лог ─────────────────────────────────────────────────────────────────

    def _toggle_log(self):
        if self._log_collapsed:
            self._log_expand()
        else:
            self._log_collapse()

    def _log_expand(self):
        if not self._log_collapsed:
            return
        self._log_collapsed = False
        self._log_new_count = 0
        self._log_badge.pack_forget()
        self._log_body.pack(fill='both', expand=True)
        self._log_arrow.config(text='▾')

    def _log_collapse(self):
        if self._log_collapsed:
            return
        self._log_collapsed = True
        self._log_body.pack_forget()
        self._log_arrow.config(text='▸')

    def _log(self, msg, tag=''):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.log.config(state='normal')
        self.log.insert('end', f'[{ts}]  {msg}\n', tag)
        self.log.see('end')
        self.log.config(state='disabled')
        if self._log_collapsed:
            self._log_new_count += 1
            self._log_badge.config(text=str(self._log_new_count))
            self._log_badge.pack(side='left', padx=(6, 0))

    def _slog(self, msg, tag=''):
        self.root.after(0, lambda m=msg, t=tag: self._log(m, t))

    def _clear_log(self):
        self.log.config(state='normal')
        self.log.delete('1.0', 'end')
        self.log.config(state='disabled')
        self._log_new_count = 0
        self._log_badge.pack_forget()
        # После очистки сворачиваем лог
        self.root.after(100, self._log_collapse)

    def _badge(self, i, state):
        self.root.after(0, lambda: self.badges[i].set(state))

    # ── Таймер ──────────────────────────────────────────────────────────────

    def _tick(self):
        if self._running and self._target:
            rem = (self._target - datetime.datetime.now()).total_seconds()
            if rem > 0:
                pct = max(0, min(100, (1 - rem / self._total_s) * 100))
                h, m, s = int(rem//3600), int((rem%3600)//60), int(rem%60)
                self.ring.draw(pct, f'{h:02d}:{m:02d}:{s:02d}',
                               self.t('ring_waiting', time=self._target.strftime("%H:%M")), ACC)
            else:
                self.ring.draw(100, '⏰', self.t('ring_firing'), WARN)
        elif not self._running:
            self.ring.draw(0, '--:--:--', self.t('ring_idle'), DIM)
        self.root.after(100, self._tick)

    # ── Управление ──────────────────────────────────────────────────────────

    def _get_target(self) -> datetime.datetime:
        h, m = self.sp_h.get(), self.sp_m.get()
        now = datetime.datetime.now()
        t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if t <= now: t += datetime.timedelta(days=1)
        return t

    def _toggle(self):
        if self._running:
            self._stop_evt.set()
            self._running = False
            self.main_btn.recolor(ACC, BG, '#79b8ff')
            self.main_btn.config(text=self.t('start_btn'))
            self.lbl_hint.config(text='')
            self._log(self.t('log_stopped'), 'dim')
            for b in self.badges: b.set('idle')
            self._tc.set_outline(BRD)
        else:
            self._start()

    def _start(self):
        if not HAS_UIA:
            self._log(self.t('log_no_uia'), 'error')
            return
        if self._plan_running:
            self._log(self.t('log_single_blocked_by_plan'), 'error')
            return
        self._stop_evt.clear()
        self._running = True
        self._target  = self._get_target()
        self._total_s = max(1.0, (self._target - datetime.datetime.now()).total_seconds())
        self.main_btn.recolor(ERR, '#fff', '#ff6b6b')
        self.main_btn.config(text=self.t('stop_btn'))
        self.lbl_hint.config(text=f'→ {self._target.strftime("%d.%m.%Y  %H:%M")}')
        self._log(self.t('log_started', time=self._target.strftime("%d.%m %H:%M")), 'accent')
        self._tc.set_outline(ACC)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while not self._stop_evt.is_set():
            rem = (self._target - datetime.datetime.now()).total_seconds()
            if rem <= 0: break
            self._stop_evt.wait(min(0.3, rem))
        if self._stop_evt.is_set(): return

        self._slog(self.t('log_time_search'), 'warn')
        indices = sorted(self._selected_chat_idx) or [0]
        try_again, auto_cont = self.v_btn_try.get(), self.v_btn_cont.get()
        conf = self.v_conf.get()

        ok = 0
        for attempt in range(1, 4):
            if self._stop_evt.is_set(): return
            self._slog(self.t('log_attempt', n=attempt), 'dim')
            ok = run_cycle(indices, try_again, auto_cont, conf, self._slog, self._badge)
            if ok: break
            if attempt < 3: self._stop_evt.wait(5)

        self._stat_click(ok)
        self._add_history(ok)
        self._notify(ok)
        if ok:
            self.root.after(0, lambda c=ok: self.ring.draw(100, '✓', self.t('ring_done', n=c), SUC))
            self._slog(self.t('log_success', n=ok), 'success')
        else:
            self.root.after(0, lambda: self.ring.draw(100, '✗', self.t('ring_fail'), ERR))
            self._slog(self.t('log_fail'), 'error')

        if self.v_watch.get() and not self._stop_evt.is_set():
            iv = int(self.v_interval.get() or 30)
            self._slog(self.t('log_watch', n=iv), 'dim')
            while not self._stop_evt.is_set():
                self._stop_evt.wait(iv)
                if self._stop_evt.is_set(): break
                watch_ok = run_cycle(sorted(self._selected_chat_idx) or [0],
                                     self.v_btn_try.get(), self.v_btn_cont.get(),
                                     self.v_conf.get(), self._slog, self._badge)
                self._stat_click(watch_ok)
                self._add_history(watch_ok)

        if not self._stop_evt.is_set():
            self._running = False
            self.root.after(0, lambda: [
                self.main_btn.recolor(ACC, BG, '#79b8ff'),
                self.main_btn.config(text=self.t('start_btn')),
                self.lbl_hint.config(text=''),
                self._tc.set_outline(BRD),
            ])

    def _click_now(self):
        self._log(self.t('log_now'), 'accent')
        indices = sorted(self._selected_chat_idx) or [0]
        try_again, auto_cont, conf = self.v_btn_try.get(), self.v_btn_cont.get(), self.v_conf.get()
        def _run():
            ok = run_cycle(indices, try_again, auto_cont, conf, self._slog, self._badge)
            self._stat_click(ok)
            self._add_history(ok)
            self._notify(ok)
        threading.Thread(target=_run, daemon=True).start()

    def _test_find(self):
        self._log(self.t('log_test'), 'accent')
        def run():
            windows = find_claude_windows(self._slog)
            if not windows:
                self._slog(self.t('log_no_app'), 'error')
                return
            self._badge(1, 'trying')
            _, rect = find_button_uia(windows[0]['ctrl'], TRY_AGAIN_LABELS, self._slog)
            if rect:
                self._badge(1, 'ok')
                self._slog(self.t('log_btn_found', x=int(rect.left), y=int(rect.top)), 'success')
            else:
                self._badge(1, 'idle')
                self._slog(self.t('log_btn_not_found'), 'dim')
            if self.v_btn_cont.get():
                self._slog(self.t('log_cont_note'), 'dim')
        threading.Thread(target=run, daemon=True).start()

    # ── План запусков (несколько времён/циклов) ──────────────────────────────

    def _plan_add(self):
        h, m = self.sp_plan_h.get(), self.sp_plan_m.get()
        if (h, m) not in self._plan:
            self._plan.append((h, m))
            self._plan.sort()
            self._refresh_plan_list()
            self._update_plan_status()

    def _plan_remove(self, hm):
        if hm in self._plan:
            self._plan.remove(hm)
            self._refresh_plan_list()
            self._update_plan_status()

    def _refresh_plan_list(self):
        for w in self.plan_list_frame.winfo_children():
            w.destroy()
        if not self._plan:
            tk.Label(self.plan_list_frame, text=self.t('plan_empty'),
                     bg=C1, fg=DIM, font=('Segoe UI', 8)).pack(anchor='w')
            return
        chips_row = tk.Frame(self.plan_list_frame, bg=C1)
        chips_row.pack(anchor='w', fill='x')
        for hm in self._plan:
            h, m = hm
            chip = tk.Frame(chips_row, bg=C2, padx=8, pady=4,
                            highlightthickness=1, highlightbackground=BRD)
            chip.pack(side='left', padx=(0, 6), pady=2)
            tk.Label(chip, text=f'{h:02d}:{m:02d}', bg=C2, fg=TXT,
                     font=('Segoe UI Mono', 9, 'bold')).pack(side='left')
            rm = tk.Label(chip, text=' ✕', bg=C2, fg=DIM, font=('Segoe UI', 8), cursor='hand2')
            rm.pack(side='left')
            rm.bind('<Button-1>', lambda _e, hm=hm: self._plan_remove(hm))
            rm.bind('<Enter>', lambda _e, w=rm: w.config(fg=ERR))
            rm.bind('<Leave>', lambda _e, w=rm: w.config(fg=DIM))

    def _plan_next_targets(self):
        """Ближайшее будущее срабатывание для каждого времени плана
        (сегодня, либо завтра, если время уже прошло)."""
        now = datetime.datetime.now()
        targets = []
        for h, m in self._plan:
            t = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if t <= now:
                t += datetime.timedelta(days=1)
            targets.append(t)
        targets.sort()
        return targets

    def _update_plan_status(self):
        if self._plan_running and self._plan_next_target:
            rem = (self._plan_next_target - datetime.datetime.now()).total_seconds()
            rem = max(0, rem)
            h_left, m_left = int(rem // 3600), int((rem % 3600) // 60)
            left = (self.t('plan_left_fmt', h=h_left, m=m_left) if h_left
                   else self.t('plan_left_fmt_m', m=m_left))
            self.lbl_plan_status.config(
                text=self.t('plan_status_next',
                           time=self._plan_next_target.strftime('%d.%m %H:%M'), left=left),
                fg=ACC)
        elif not self._plan_running:
            self.lbl_plan_status.config(text=self.t('plan_status_idle'), fg=DIM)

    def _toggle_plan(self):
        if self._plan_running:
            self._plan_stop_evt.set()
            self._plan_running = False
            self.btn_plan_start.recolor(C2, TXT, hbg=BRD)
            self.btn_plan_start.config(text=self.t('plan_start_btn'))
            self._log(self.t('log_plan_stopped'), 'dim')
            self._update_plan_status()
            self._pc.set_outline(BRD)
        else:
            self._plan_start()

    def _plan_start(self):
        if not HAS_UIA:
            self._log(self.t('log_no_uia'), 'error')
            return
        if not self._plan:
            self._plan_add()
            if not self._plan:
                return
        if self._running:
            self._log(self.t('log_plan_already_running'), 'error')
            return
        self._plan_stop_evt.clear()
        self._plan_running = True
        self.btn_plan_start.recolor(ERR, '#fff', '#ff6b6b')
        self.btn_plan_start.config(text=self.t('plan_stop_btn'))
        self._log(self.t('log_plan_started', n=len(self._plan)), 'accent')
        self._pc.set_outline(ACC)
        threading.Thread(target=self._plan_worker, daemon=True).start()

    def _plan_worker(self):
        while not self._plan_stop_evt.is_set():
            targets = self._plan_next_targets()
            if not targets:
                break
            next_t = targets[0]
            self._plan_next_target = next_t
            self.root.after(0, self._update_plan_status)

            while not self._plan_stop_evt.is_set():
                rem = (next_t - datetime.datetime.now()).total_seconds()
                if rem <= 0: break
                self._plan_stop_evt.wait(min(0.5, rem))
            if self._plan_stop_evt.is_set():
                return

            self._slog(self.t('log_plan_trigger', time=next_t.strftime('%H:%M')), 'warn')
            indices = sorted(self._selected_chat_idx) or [0]
            try_again, auto_cont = self.v_btn_try.get(), self.v_btn_cont.get()
            conf = self.v_conf.get()
            ok = run_cycle(indices, try_again, auto_cont, conf, self._slog, self._badge)
            self._stat_click(ok)
            self._add_history(ok)
            self._notify(ok)

            if not self.v_plan_repeat.get():
                fired = (next_t.hour, next_t.minute)
                if fired in self._plan:
                    self._plan.remove(fired)
                    self.root.after(0, self._refresh_plan_list)
                if not self._plan:
                    break

        if not self._plan_stop_evt.is_set():
            self._plan_running = False
            self._plan_next_target = None
            self._slog(self.t('log_plan_done'), 'success')
            self.root.after(0, lambda: [
                self.btn_plan_start.recolor(C2, TXT, hbg=BRD),
                self.btn_plan_start.config(text=self.t('plan_start_btn')),
                self._update_plan_status(),
                self._pc.set_outline(BRD),
            ])


# ══════════════════════════════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if IS_WIN:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    root.tk.call('tk', 'scaling', 1.35)
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
