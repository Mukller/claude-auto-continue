#!/usr/bin/env python3
"""Claude Code Auto-Continue — v4"""

import sys, os

# ── Перехват ошибок при запуске (показывает диалог вместо тихого падения) ───
def _fatal(msg):
    try:
        import tkinter.messagebox as mb
        import tkinter as tk
        tk.Tk().withdraw()
        mb.showerror("Ошибка запуска", msg)
    except Exception:
        pass
    sys.exit(1)

try:
    import tkinter as tk
except ImportError:
    _fatal("tkinter не найден. Переустановите Python с поддержкой Tkinter.")

import threading, time, datetime, subprocess, ctypes, math
from collections import deque

# ── Палитра ─────────────────────────────────────────────────────────────────
BG   = "#0d1117"
C1   = "#161b22"
C2   = "#21262d"
ACC  = "#58a6ff"
TXT  = "#e6edf3"
DIM  = "#8b949e"
SUC  = "#3fb950"
ERR  = "#f85149"
WARN = "#e3b341"
BRD  = "#30363d"

# ── Кнопки для поиска ───────────────────────────────────────────────────────
BUTTON_LABELS = [
    'Try again', 'try again',
    'Continue',  'continue',
    'Retry',     'retry',
    'Попробовать снова', 'Продолжить',
]

# UIA ControlType для кнопок (Button=50000, Hyperlink=50003, Custom=50025)
BUTTON_CTYPES = {50000, 50003, 50025, 50013, 50014}


# ══════════════════════════════════════════════════════════════════════════════
#  ПОИСК ОКОН CLAUDE CODE
# ══════════════════════════════════════════════════════════════════════════════

def scan_windows() -> list:
    wins = []

    try:
        import uiautomation as auto
        auto.SetGlobalSearchTimeout(1)
        ctrl = auto.GetRootControl().GetFirstChildControl()
        while ctrl:
            name = ctrl.Name or ''
            if 'claude' in name.lower():
                hwnd = ctrl.NativeWindowHandle
                if hwnd:
                    wins.append({'title': name, 'hwnd': hwnd,
                                 'idx': len(wins)+1, 'ctrl': ctrl})
            ctrl = ctrl.GetNextSiblingControl()
        if wins:
            return wins
    except Exception:
        pass

    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            if 'claude' in (w.title or '').lower():
                hwnd = getattr(w, '_hWnd', 0)
                if hwnd:
                    wins.append({'title': w.title, 'hwnd': hwnd,
                                 'idx': len(wins)+1, 'ctrl': None})
        if wins:
            return wins
    except Exception:
        pass

    try:
        ps = ('Get-Process claude* -EA SilentlyContinue | '
              'Where-Object {$_.MainWindowHandle -ne 0} | '
              'ForEach-Object {"$($_.MainWindowHandle)|$($_.MainWindowTitle)"}')
        r = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.strip().splitlines():
            if '|' in line:
                h, t = line.strip().split('|', 1)
                if h.strip().isdigit():
                    wins.append({'title': t.strip() or 'Claude Code',
                                 'hwnd': int(h.strip()),
                                 'idx': len(wins)+1, 'ctrl': None})
    except Exception:
        pass

    return wins


# ══════════════════════════════════════════════════════════════════════════════
#  BFS-ПОИСК КНОПКИ В ДЕРЕВЕ ДОСТУПНОСТИ (Electron/Chrome)
# ══════════════════════════════════════════════════════════════════════════════

def _bfs_find_button(root_ctrl, labels: list, log_fn, max_depth=80):
    """
    Обход дерева UIA в ширину (BFS).
    Ищет кнопку с текстом из labels на любой глубине до max_depth.
    Electron/Chrome вкладывает кнопки на 30-60 уровней — фиксированный
    searchDepth=15 их не достаёт.
    """
    try:
        queue = deque([(root_ctrl, 0)])
        visited = set()

        while queue:
            ctrl, depth = queue.popleft()
            if depth > max_depth:
                continue

            try:
                uid = id(ctrl)
                if uid in visited:
                    continue
                visited.add(uid)

                name  = (ctrl.Name or '').strip()
                ctype = ctrl.ControlType

                # Нашли подходящую кнопку
                if ctype in BUTTON_CTYPES and name:
                    for label in labels:
                        if label.lower() == name.lower() or label.lower() in name.lower():
                            log_fn(f'  ✓ BFS нашёл: "{name}" (глубина {depth})', 'success')
                            ctrl.SetFocus()
                            time.sleep(0.1)
                            ctrl.Click(simulateMove=False)
                            return True

                child = ctrl.GetFirstChildControl()
                while child:
                    queue.append((child, depth + 1))
                    child = child.GetNextSiblingControl()

            except Exception:
                pass

    except Exception as e:
        log_fn(f'  BFS ошибка: {e}', 'dim')

    return False


# ══════════════════════════════════════════════════════════════════════════════
#  НАЖАТИЕ КНОПКИ В КОНКРЕТНОМ ОКНЕ
# ══════════════════════════════════════════════════════════════════════════════

def click_in_window(win: dict, labels: list, log_fn,
                    badge_fn=None, press_enter_after: bool = True) -> bool:
    hwnd = win.get('hwnd', 0)
    ctrl = win.get('ctrl')

    # ── Метод 0: BFS по дереву UIA (основной для Electron) ──────────────────
    if badge_fn: badge_fn(0, 'trying')
    try:
        import uiautomation as auto
        auto.SetGlobalSearchTimeout(1)

        # Пробуем в конкретном окне, если есть ctrl
        search_root = ctrl if ctrl else auto.GetRootControl()
        if _bfs_find_button(search_root, labels, log_fn):
            if badge_fn: badge_fn(0, 'ok')
            if press_enter_after:
                time.sleep(0.4)
                _send_enter(hwnd, log_fn)
            return True
        if badge_fn: badge_fn(0, 'idle')
    except Exception as e:
        log_fn(f'  UIA: {e}', 'dim')
        if badge_fn: badge_fn(0, 'fail')

    # ── Метод 1: фокус окна + Tab×N + Enter (клавиатура) ───────────────────
    if badge_fn: badge_fn(1, 'trying')
    if hwnd and _focus_hwnd(hwnd):
        try:
            import pyautogui
            time.sleep(0.3)
            # Tab до "Try again" (обычно 2-й элемент после "View details")
            for _ in range(2):
                pyautogui.press('tab')
                time.sleep(0.08)
            pyautogui.press('enter')
            log_fn('  ✓ Tab+Enter', 'success')
            if badge_fn: badge_fn(1, 'ok')
            if press_enter_after:
                time.sleep(0.5)
                _send_enter(hwnd, log_fn)
            return True
        except ImportError:
            pass
        except Exception as e:
            log_fn(f'  Tab+Enter: {e}', 'dim')
    if badge_fn: badge_fn(1, 'idle' if not hwnd else 'fail')

    # ── Метод 2: PowerShell SendKeys ────────────────────────────────────────
    if badge_fn: badge_fn(2, 'trying')
    if hwnd:
        result = _ps_sendkeys(hwnd, log_fn)
        if result:
            if badge_fn: badge_fn(2, 'ok')
            if press_enter_after:
                time.sleep(0.5)
                _send_enter(hwnd, log_fn)
            return True
    if badge_fn: badge_fn(2, 'fail' if hwnd else 'idle')

    return False


def _focus_hwnd(hwnd: int) -> bool:
    try:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.25)
        return True
    except Exception:
        return False


def _send_enter(hwnd: int, log_fn):
    """Нажать Enter в активном окне (для отправки сообщения после Try again)."""
    try:
        if hwnd:
            _focus_hwnd(hwnd)
        import pyautogui
        pyautogui.press('enter')
        log_fn('  → Enter отправлен', 'dim')
    except ImportError:
        try:
            script = f"""
Add-Type -AssemblyName System.Windows.Forms
$sig = '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);'
$t = Add-Type -MemberDefinition $sig -Name U -PassThru -Namespace _n -EA SilentlyContinue
if ($t -and {hwnd}) {{ $t::SetForegroundWindow({hwnd}) | Out-Null }}
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait("{{ENTER}}")
"""
            subprocess.run(['powershell', '-NoProfile', '-Command', script],
                           capture_output=True, timeout=5)
        except Exception:
            pass


def _ps_sendkeys(hwnd: int, log_fn) -> bool:
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
$sig = '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);'
$t = Add-Type -MemberDefinition $sig -Name U -PassThru -Namespace _n -EA SilentlyContinue
$t::SetForegroundWindow({hwnd}) | Out-Null
Start-Sleep -Milliseconds 300
# Tab дважды чтобы добраться до "Try again", потом Enter
[System.Windows.Forms.SendKeys]::SendWait("{{TAB}}{{TAB}}{{ENTER}}")
Write-Output "ok"
"""
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', script],
                           capture_output=True, text=True, timeout=8)
        if 'ok' in r.stdout:
            log_fn('  ✓ PowerShell Tab+Enter', 'success')
            return True
    except Exception:
        pass
    return False


def do_click_multi(wins: list, n: int, labels: list, log_fn,
                   badge_fn=None, press_enter_after=True) -> int:
    targets = wins[:max(1, n)]
    if not targets:
        log_fn('  Окна Claude Code не найдены', 'error')
        return 0
    ok = 0
    for w in targets:
        title = (w.get('title') or 'Claude Code')[:42]
        log_fn(f'  [{w["idx"]}] {title}', 'dim')
        if click_in_window(w, labels, log_fn, badge_fn, press_enter_after):
            ok += 1
        if w is not targets[-1]:
            time.sleep(0.7)
    return ok


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
        self.create_arc(cx-r, cy-r, cx+r, cy+r,
                        start=90, extent=360, style='arc',
                        outline=C2, width=w)
        if pct > 0.5:
            self.create_arc(cx-r, cy-r, cx+r, cy+r,
                            start=90, extent=-pct*3.6, style='arc',
                            outline=color, width=w)
            if 2 < pct < 98:
                ang = math.radians(90 - pct*3.6)
                ex, ey = cx + r*math.cos(ang), cy - r*math.sin(ang)
                self.create_oval(ex-w//2, ey-w//2, ex+w//2, ey+w//2,
                                 fill=color, outline='')
        self.create_text(cx, cy-12, text=main,
                         fill=color, font=('Segoe UI Mono', 22, 'bold'))
        self.create_text(cx, cy+16, text=sub,
                         fill=DIM, font=('Segoe UI', 8))


class Spinner(tk.Frame):
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
        tk.Label(self, textvariable=self._sv, bg=C2, fg=TXT,
                 font=('Segoe UI Mono', fs, 'bold'),
                 width=2, padx=px, pady=3).pack(side='left', padx=2)
        btn('+', self._inc).pack(side='left')

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


class FlatBtn(tk.Label):
    def __init__(self, parent, text, cmd, bg, fg, hbg=None, hfg=None, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, cursor='hand2', **kw)
        self._bg, self._fg = bg, fg
        self._hbg = hbg or bg
        self._hfg = hfg or fg
        self.bind('<Button-1>', lambda _: cmd())
        self.bind('<Enter>', lambda _: self.config(bg=self._hbg, fg=self._hfg))
        self.bind('<Leave>', lambda _: self.config(bg=self._bg, fg=self._fg))

    def recolor(self, bg, fg, hbg=None):
        self._bg, self._fg, self._hbg = bg, fg, hbg or bg
        self.config(bg=bg, fg=fg)


class Badge(tk.Frame):
    COLORS = {'idle': DIM, 'ok': SUC, 'fail': ERR, 'trying': WARN}

    def __init__(self, parent, name, **kw):
        super().__init__(parent, bg=C1, padx=10, pady=5,
                         highlightthickness=1, highlightbackground=BRD, **kw)
        self._dot = tk.Label(self, text='●', bg=C1, fg=DIM, font=('Segoe UI', 9))
        self._dot.pack(side='left')
        tk.Label(self, text=name, bg=C1, fg=DIM,
                 font=('Segoe UI', 8)).pack(side='left', padx=(4, 0))

    def set(self, state):
        self._dot.config(fg=self.COLORS.get(state, DIM))


# ══════════════════════════════════════════════════════════════════════════════
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════════════════════════════════════════

METHOD_NAMES = ['UIA / BFS', 'Tab + Enter', 'PowerShell']


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title('Claude Code Auto-Continue')
        root.configure(bg=BG)
        root.geometry('480x860')
        root.minsize(440, 780)

        self._running  = False
        self._stop_evt = threading.Event()
        self._target   = None
        self._total_s  = 1.0
        self._windows  = []

        self._build()
        self._tick()
        self._scan_windows()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build(self):
        hdr = tk.Frame(self.root, bg=C1, pady=14)
        hdr.pack(fill='x')
        tk.Label(hdr, text='⚡', bg=C1, fg=ACC,
                 font=('Segoe UI', 16)).pack(side='left', padx=(22, 0))
        tk.Label(hdr, text='Claude Code  Auto-Continue', bg=C1, fg=TXT,
                 font=('Segoe UI', 12, 'bold')).pack(side='left', padx=10)
        tk.Frame(self.root, bg=BRD, height=1).pack(fill='x')

        body = tk.Frame(self.root, bg=BG, padx=24)
        body.pack(fill='both', expand=True)

        # Кольцо
        tk.Frame(body, bg=BG, height=16).pack()
        self.ring = RingTimer(body)
        self.ring.pack()
        self.lbl_hint = tk.Label(body, text='', bg=BG, fg=DIM, font=('Segoe UI', 8))
        self.lbl_hint.pack(pady=(3, 12))

        # Карточка времени
        tc = tk.Frame(body, bg=C1, padx=18, pady=14,
                      highlightthickness=1, highlightbackground=BRD)
        tc.pack(fill='x')
        tk.Label(tc, text='Нажать в:', bg=C1, fg=DIM,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(0, 8))
        trow = tk.Frame(tc, bg=C1)
        trow.pack()
        self.sp_h = Spinner(trow, lo=0, hi=23, val=5)
        self.sp_h.pack(side='left')
        tk.Label(trow, text=':', bg=C1, fg=TXT,
                 font=('Segoe UI Mono', 22, 'bold')).pack(side='left', padx=10)
        self.sp_m = Spinner(trow, lo=0, hi=59, val=0)
        self.sp_m.pack(side='left')
        FlatBtn(trow, '↻ Сейчас', self._click_now,
                bg=BG, fg=DIM, hbg=C2, hfg=TXT,
                font=('Segoe UI', 9), padx=12, pady=8
                ).pack(side='left', padx=(18, 0))

        # Кнопка старт/стоп
        tk.Frame(body, bg=BG, height=12).pack()
        self.main_btn = FlatBtn(body, '▶   СТАРТ', self._toggle,
                                bg=ACC, fg=BG, hbg='#79b8ff', hfg=BG,
                                font=('Segoe UI', 11, 'bold'), padx=20, pady=12)
        self.main_btn.pack(fill='x')

        # Опции
        tk.Frame(body, bg=BG, height=10).pack()
        opts = tk.Frame(body, bg=BG)
        opts.pack(fill='x')
        self.v_watch = tk.BooleanVar(value=False)
        tk.Checkbutton(opts, text='Наблюдение — каждые', variable=self.v_watch,
                       bg=BG, fg=DIM, selectcolor=C2,
                       activebackground=BG, activeforeground=TXT,
                       font=('Segoe UI', 9), cursor='hand2').pack(side='left')
        self.v_interval = tk.StringVar(value='30')
        tk.Spinbox(opts, from_=5, to=600, textvariable=self.v_interval,
                   width=3, bg=C2, fg=TXT, relief='flat', bd=0,
                   font=('Segoe UI', 9), buttonbackground=C2,
                   insertbackground=TXT).pack(side='left', padx=6)
        tk.Label(opts, text='сек', bg=BG, fg=DIM,
                 font=('Segoe UI', 9)).pack(side='left')

        # Карточка окон
        tk.Frame(body, bg=BG, height=10).pack()
        wc = tk.Frame(body, bg=C1, padx=18, pady=14,
                      highlightthickness=1, highlightbackground=BRD)
        wc.pack(fill='x')

        wh = tk.Frame(wc, bg=C1)
        wh.pack(fill='x')
        tk.Label(wh, text='Целевые окна', bg=C1, fg=DIM,
                 font=('Segoe UI', 8, 'bold')).pack(side='left')
        FlatBtn(wh, '↻  Найти', self._scan_windows,
                bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                font=('Segoe UI', 8), padx=10, pady=4).pack(side='right')

        nr = tk.Frame(wc, bg=C1)
        nr.pack(fill='x', pady=(10, 0))
        tk.Label(nr, text='Нажать в первых', bg=C1, fg=DIM,
                 font=('Segoe UI', 9)).pack(side='left')
        self.sp_n = Spinner(nr, lo=1, hi=20, val=3, big=False,
                            on_change=lambda _: self._refresh_win_list())
        self.sp_n.pack(side='left', padx=(8, 8))
        self.lbl_wcount = tk.Label(nr, text='из – окон', bg=C1, fg=DIM,
                                    font=('Segoe UI', 9))
        self.lbl_wcount.pack(side='left')

        self.wlist = tk.Frame(wc, bg=C1)
        self.wlist.pack(fill='x', pady=(8, 0))

        # Разделитель и настройки кнопок
        tk.Frame(wc, bg=BRD, height=1).pack(fill='x', pady=(10, 8))
        brow = tk.Frame(wc, bg=C1)
        brow.pack(fill='x')
        tk.Label(brow, text='Кнопки:', bg=C1, fg=DIM,
                 font=('Segoe UI', 8, 'bold')).pack(side='left')
        self.v_btn_try  = tk.BooleanVar(value=True)
        self.v_btn_cont = tk.BooleanVar(value=True)
        self.v_enter    = tk.BooleanVar(value=True)
        for lbl, var in [('Try again', self.v_btn_try),
                         ('Continue',  self.v_btn_cont)]:
            tk.Checkbutton(brow, text=lbl, variable=var,
                           bg=C1, fg=DIM, selectcolor=C2,
                           activebackground=C1, activeforeground=TXT,
                           font=('Segoe UI', 9), cursor='hand2'
                           ).pack(side='left', padx=(14, 0))

        # Enter после нажатия
        erow = tk.Frame(wc, bg=C1)
        erow.pack(fill='x', pady=(6, 0))
        tk.Checkbutton(erow,
                       text='Нажимать Enter после (отправить сообщение)',
                       variable=self.v_enter,
                       bg=C1, fg=DIM, selectcolor=C2,
                       activebackground=C1, activeforeground=TXT,
                       font=('Segoe UI', 9), cursor='hand2').pack(side='left')

        # Бейджи методов
        tk.Frame(body, bg=BG, height=10).pack()
        br = tk.Frame(body, bg=BG)
        br.pack(anchor='w')
        self.badges = [Badge(br, n) for n in METHOD_NAMES]
        for b in self.badges: b.pack(side='left', padx=(0, 8))

        # Лог
        tk.Frame(body, bg=BRD, height=1).pack(fill='x', pady=(12, 0))
        lh = tk.Frame(body, bg=BG)
        lh.pack(fill='x', pady=(5, 4))
        tk.Label(lh, text='Лог', bg=BG, fg=DIM,
                 font=('Segoe UI', 8, 'bold')).pack(side='left')
        FlatBtn(lh, '✕ очистить', self._clear_log,
                bg=BG, fg=DIM, hfg=TXT,
                font=('Segoe UI', 8)).pack(side='right')
        self.log = tk.Text(body, bg=C1, fg=TXT, font=('Consolas', 8),
                            relief='flat', bd=0, state='disabled',
                            wrap='word', insertbackground=TXT)
        self.log.pack(fill='both', expand=True, pady=(0, 20))
        for tag, fg in [('success', SUC), ('error', ERR),
                        ('warn', WARN), ('dim', DIM), ('accent', ACC)]:
            self.log.tag_config(tag, foreground=fg)

    # ── Окна ────────────────────────────────────────────────────────────────

    def _scan_windows(self):
        def run():
            wins = scan_windows()
            self.root.after(0, lambda w=wins: self._update_windows(w))
        threading.Thread(target=run, daemon=True).start()

    def _update_windows(self, wins):
        self._windows = wins
        self._refresh_win_list()

    def _refresh_win_list(self):
        for w in self.wlist.winfo_children():
            w.destroy()
        wins  = self._windows
        n     = self.sp_n.get()
        total = len(wins)

        if not wins:
            self.lbl_wcount.config(text='из – окон')
            tk.Label(self.wlist, text='⚠  Окна Claude Code не найдены',
                     bg=C1, fg=WARN, font=('Segoe UI', 8)).pack(anchor='w')
            return

        noun = 'окна' if 2 <= total <= 4 else 'окон'
        self.lbl_wcount.config(text=f'из {total} {noun}')

        for i, w in enumerate(wins[:8]):
            active = i < n
            row = tk.Frame(self.wlist, bg=C1)
            row.pack(fill='x', pady=1)
            tk.Label(row, text='●', bg=C1,
                     fg=ACC if active else DIM,
                     font=('Segoe UI', 9)).pack(side='left')
            title = (w.get('title') or f'Claude Code ({i+1})')
            if len(title) > 44: title = title[:42] + '…'
            tk.Label(row, text=f'  {title}', bg=C1,
                     fg=TXT if active else DIM,
                     font=('Segoe UI', 8)).pack(side='left')
            if active:
                tk.Label(row, text='  ← нажать', bg=C1, fg=ACC,
                         font=('Segoe UI', 7)).pack(side='left')

        if total > 8:
            tk.Label(self.wlist, text=f'  … ещё {total-8}',
                     bg=C1, fg=DIM, font=('Segoe UI', 7)).pack(anchor='w')

    def _get_labels(self) -> list:
        labels = []
        if self.v_btn_try.get():
            labels += ['Try again', 'try again', 'Попробовать снова', 'Retry']
        if self.v_btn_cont.get():
            labels += ['Continue', 'continue', 'Продолжить']
        return labels or BUTTON_LABELS

    # ── Лог ─────────────────────────────────────────────────────────────────

    def _log(self, msg, tag=''):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.log.config(state='normal')
        self.log.insert('end', f'[{ts}]  {msg}\n', tag)
        self.log.see('end')
        self.log.config(state='disabled')

    def _slog(self, msg, tag=''):
        self.root.after(0, lambda m=msg, t=tag: self._log(m, t))

    def _clear_log(self):
        self.log.config(state='normal')
        self.log.delete('1.0', 'end')
        self.log.config(state='disabled')

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
                               f'Ждём {self._target.strftime("%H:%M")}', ACC)
            else:
                self.ring.draw(100, '⏰', 'Нажимаем…', WARN)
        elif not self._running:
            self.ring.draw(0, '--:--:--', 'Не запущено', DIM)
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
            self.main_btn.config(text='▶   СТАРТ')
            self.lbl_hint.config(text='')
            self._log('Остановлено.', 'dim')
            for b in self.badges: b.set('idle')
        else:
            self._start()

    def _start(self):
        self._stop_evt.clear()
        self._running = True
        self._target  = self._get_target()
        self._total_s = max(1.0, (self._target - datetime.datetime.now()).total_seconds())
        self.main_btn.recolor(ERR, '#fff', '#ff6b6b')
        self.main_btn.config(text='⏹   СТОП')
        self.lbl_hint.config(text=f'→ {self._target.strftime("%d.%m.%Y  %H:%M")}')
        self._log(f'Запущено → {self._target.strftime("%d.%m %H:%M")}', 'accent')
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while not self._stop_evt.is_set():
            rem = (self._target - datetime.datetime.now()).total_seconds()
            if rem <= 0: break
            self._stop_evt.wait(min(0.3, rem))
        if self._stop_evt.is_set(): return

        self._slog('Время! Сканируем окна…', 'warn')
        fresh = scan_windows()
        if fresh:
            self.root.after(0, lambda w=fresh: self._update_windows(w))
        else:
            fresh = self._windows

        n      = self.sp_n.get()
        labels = self._get_labels()
        enter  = self.v_enter.get()
        self._slog(
            f'Окон: {len(fresh)}, целевых: {min(n, len(fresh))}, '
            f'кнопки: {labels[0]}{"…" if len(labels)>1 else ""}, '
            f'Enter после: {"да" if enter else "нет"}', 'dim')

        ok = 0
        for attempt in range(1, 4):
            if self._stop_evt.is_set(): return
            self._slog(f'Попытка {attempt}/3:', 'dim')
            ok = do_click_multi(fresh, n, labels, self._slog,
                                self._badge, press_enter_after=enter)
            if ok: break
            if attempt < 3: self._stop_evt.wait(5)

        if ok:
            self.root.after(0, lambda c=ok: self.ring.draw(
                100, '✓', f'Нажато в {c} окн.', SUC))
            self._slog(f'✓  Успех в {ok} окн(е/ах)!', 'success')
        else:
            self.root.after(0, lambda: self.ring.draw(100, '✗', 'Ошибка', ERR))
            self._slog('✗  Не удалось. Проверьте, что Claude Code открыт.', 'error')

        if self.v_watch.get() and not self._stop_evt.is_set():
            iv = int(self.v_interval.get() or 30)
            self._slog(f'Наблюдение каждые {iv}с.', 'dim')
            while not self._stop_evt.is_set():
                self._stop_evt.wait(iv)
                if self._stop_evt.is_set(): break
                wins = scan_windows()
                do_click_multi(wins, self.sp_n.get(),
                               self._get_labels(), self._slog,
                               self._badge, self.v_enter.get())

        if not self._stop_evt.is_set():
            self._running = False
            self.root.after(0, lambda: [
                self.main_btn.recolor(ACC, BG, '#79b8ff'),
                self.main_btn.config(text='▶   СТАРТ'),
                self.lbl_hint.config(text=''),
            ])

    def _click_now(self):
        self._log('Нажимаем прямо сейчас…', 'accent')
        wins  = self._windows or scan_windows()
        n     = self.sp_n.get()
        labels = self._get_labels()
        enter  = self.v_enter.get()
        threading.Thread(
            target=lambda: do_click_multi(wins, n, labels,
                                          self._slog, self._badge, enter),
            daemon=True
        ).start()


# ══════════════════════════════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════════════════════════════

def main():
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
