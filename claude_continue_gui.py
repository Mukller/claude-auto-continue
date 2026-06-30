#!/usr/bin/env python3
"""Claude Code Auto-Continue — v5 (screenshot template matching + mouse control)"""

import sys, os

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
    from tkinter import filedialog
except ImportError:
    _fatal("tkinter не найден. Переустановите Python с поддержкой Tkinter.")

import threading, time, datetime, math, json

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

# ── Палитра ─────────────────────────────────────────────────────────────────
BG, C1, C2 = "#0d1117", "#161b22", "#21262d"
ACC, TXT, DIM = "#58a6ff", "#e6edf3", "#8b949e"
SUC, ERR, WARN, BRD = "#3fb950", "#f85149", "#e3b341", "#30363d"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TPL_DIR = os.path.join(APP_DIR, 'templates')
os.makedirs(TPL_DIR, exist_ok=True)

TEMPLATES = {
    'try_again': {'label': 'Try again',  'file': os.path.join(TPL_DIR, 'try_again.png')},
    'continue':  {'label': 'Continue',   'file': os.path.join(TPL_DIR, 'continue.png')},
}


# ══════════════════════════════════════════════════════════════════════════════
#  ПОИСК КНОПКИ ПО СКРИНШОТУ
# ══════════════════════════════════════════════════════════════════════════════

def find_matches(template_path: str, confidence: float, log_fn) -> list:
    """Вернуть [(left, top, width, height), ...] всех совпадений на экране."""
    if pyautogui is None:
        log_fn('  pyautogui не установлен', 'error')
        return []
    if not os.path.isfile(template_path):
        return []

    try:
        if HAS_CV2:
            boxes = list(pyautogui.locateAllOnScreen(
                template_path, confidence=confidence, grayscale=True))
        else:
            # Без opencv доступно только точное совпадение пикселей
            boxes = list(pyautogui.locateAllOnScreen(template_path))
    except Exception as e:
        log_fn(f'  Поиск шаблона: {e}', 'dim')
        return []

    # Убираем дубликаты (близкие по центру боксы)
    out = []
    for b in boxes:
        cx, cy = b.left + b.width / 2, b.top + b.height / 2
        dup = False
        for ex in out:
            ecx, ecy = ex.left + ex.width / 2, ex.top + ex.height / 2
            if abs(cx - ecx) < 12 and abs(cy - ecy) < 12:
                dup = True
                break
        if not dup:
            out.append(b)
    return out


def click_box(box, log_fn, press_enter_after=False) -> bool:
    if pyautogui is None:
        return False
    try:
        cx = box.left + box.width // 2
        cy = box.top + box.height // 2
        pyautogui.moveTo(cx, cy, duration=0.15)
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


def search_and_click(labels: list, n: int, confidence: float,
                     press_enter_after: bool, log_fn, badge_fn=None) -> int:
    all_boxes = []
    for i, key in enumerate(labels):
        tpl = TEMPLATES.get(key)
        if not tpl:
            continue
        if badge_fn: badge_fn(i, 'trying')
        boxes = find_matches(tpl['file'], confidence, log_fn)
        if boxes:
            log_fn(f'  Найдено "{tpl["label"]}": {len(boxes)}', 'dim')
            if badge_fn: badge_fn(i, 'ok')
        else:
            if badge_fn: badge_fn(i, 'idle')
        all_boxes.extend(boxes)

    if not all_boxes:
        log_fn('  Кнопки на экране не найдены', 'error')
        return 0

    # Сортируем по порядку чтения: сверху-вниз, слева-направо
    all_boxes.sort(key=lambda b: (b.top, b.left))
    targets = all_boxes[:max(1, n)]

    ok = 0
    for box in targets:
        if click_box(box, log_fn, press_enter_after):
            ok += 1
        if box is not targets[-1]:
            time.sleep(0.6)
    return ok


# ══════════════════════════════════════════════════════════════════════════════
#  ЗАХВАТ ШАБЛОНА КНОПКИ (выделение области мышью)
# ══════════════════════════════════════════════════════════════════════════════

class RegionCapture:
    """Полноэкранный полупрозрачный оверлей для выделения области экрана."""

    def __init__(self, root: tk.Tk, on_done):
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
            text='Выдели рамкой кнопку  •  Esc — отмена',
            fill='white', font=('Segoe UI', 14, 'bold'))

        self.canvas.bind('<ButtonPress-1>', self._down)
        self.canvas.bind('<B1-Motion>', self._move)
        self.canvas.bind('<ButtonRelease-1>', self._up)
        self.top.bind('<Escape>', lambda e: self._cancel())

    def _down(self, e):
        self.start = (e.x_root, e.y_root)
        self.rect_id = self.canvas.create_rectangle(
            e.x, e.y, e.x, e.y, outline=ACC, width=2)

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
        left, top = min(x1, x2), min(y1, y2)
        right, bottom = max(x1, x2), max(y1, y2)
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
                self.create_oval(ex-w//2, ey-w//2, ex+w//2, ey+w//2,
                                 fill=color, outline='')
        self.create_text(cx, cy-12, text=main, fill=color,
                         font=('Segoe UI Mono', 22, 'bold'))
        self.create_text(cx, cy+16, text=sub, fill=DIM, font=('Segoe UI', 8))


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
        self._hbg, self._hfg = hbg or bg, hfg or fg
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


class TemplateRow(tk.Frame):
    """Строка управления одним шаблоном: превью + захват + чекбокс."""

    def __init__(self, parent, key: str, app, **kw):
        super().__init__(parent, bg=C1, **kw)
        self.key = key
        self.app = app
        self.tpl = TEMPLATES[key]

        self.var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, variable=self.var,
                       bg=C1, fg=DIM, selectcolor=C2,
                       activebackground=C1, font=('Segoe UI', 9),
                       cursor='hand2').pack(side='left')

        self.thumb = tk.Label(self, bg=C2, width=6, height=2,
                              relief='flat', bd=0)
        self.thumb.pack(side='left', padx=(2, 8))

        info = tk.Frame(self, bg=C1)
        info.pack(side='left', fill='x', expand=True)
        tk.Label(info, text=self.tpl['label'], bg=C1, fg=TXT,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        self.lbl_status = tk.Label(info, text='шаблон не задан', bg=C1, fg=WARN,
                                    font=('Segoe UI', 7))
        self.lbl_status.pack(anchor='w')

        FlatBtn(self, '📷 Захватить', self._capture,
                bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                font=('Segoe UI', 8), padx=10, pady=5
                ).pack(side='right', padx=(6, 0))

        self.refresh()

    def refresh(self):
        path = self.tpl['file']
        if os.path.isfile(path) and Image:
            try:
                img = Image.open(path)
                img.thumbnail((48, 28))
                self._photo = ImageTk.PhotoImage(img)
                self.thumb.config(image=self._photo, width=48, height=28)
                self.lbl_status.config(text=f'{img.width}×{img.height} px  ✓',
                                       fg=SUC)
            except Exception:
                self.lbl_status.config(text='ошибка чтения файла', fg=ERR)
        else:
            self.thumb.config(image='', width=6, height=2)
            self.lbl_status.config(text='шаблон не задан — нажми «Захватить»',
                                   fg=WARN)

    def _capture(self):
        self.app.capture_template(self.key, self.refresh)


# ══════════════════════════════════════════════════════════════════════════════
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════════════════════════════════════════

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title('Claude Code Auto-Continue')
        root.configure(bg=BG)
        root.geometry('480x880')
        root.minsize(440, 800)

        self._running  = False
        self._stop_evt = threading.Event()
        self._target   = None
        self._total_s  = 1.0

        self._check_deps()
        self._build()
        self._tick()

    # ── Проверка зависимостей ──────────────────────────────────────────────

    def _check_deps(self):
        missing = []
        if pyautogui is None: missing.append('pyautogui')
        if Image is None: missing.append('pillow')
        if not HAS_CV2: missing.append('opencv-python (рекомендуется)')
        self._missing = missing

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

        if self._missing:
            warn = tk.Frame(body, bg='#3d2f0a', padx=14, pady=10)
            warn.pack(fill='x', pady=(14, 0))
            tk.Label(warn, text=f'⚠ Не хватает: {", ".join(self._missing)}\n'
                                 f'pip install {" ".join(m.split()[0] for m in self._missing)}',
                     bg='#3d2f0a', fg=WARN, font=('Segoe UI', 8),
                     justify='left').pack(anchor='w')

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

        # Опции наблюдения
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

        # ── Карточка: шаблоны кнопок ──
        tk.Frame(body, bg=BG, height=10).pack()
        wc = tk.Frame(body, bg=C1, padx=18, pady=14,
                      highlightthickness=1, highlightbackground=BRD)
        wc.pack(fill='x')
        tk.Label(wc, text='Кнопки для поиска по скриншоту', bg=C1, fg=DIM,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(0, 10))

        self.tpl_rows = {}
        for key in TEMPLATES:
            row = TemplateRow(wc, key, self)
            row.pack(fill='x', pady=4)
            self.tpl_rows[key] = row

        tk.Frame(wc, bg=BRD, height=1).pack(fill='x', pady=(10, 8))

        nr = tk.Frame(wc, bg=C1)
        nr.pack(fill='x')
        tk.Label(nr, text='Кликнуть по первым', bg=C1, fg=DIM,
                 font=('Segoe UI', 9)).pack(side='left')
        self.sp_n = Spinner(nr, lo=1, hi=20, val=3, big=False)
        self.sp_n.pack(side='left', padx=(8, 8))
        tk.Label(nr, text='найденным кнопкам', bg=C1, fg=DIM,
                 font=('Segoe UI', 9)).pack(side='left')

        cr = tk.Frame(wc, bg=C1)
        cr.pack(fill='x', pady=(8, 0))
        tk.Label(cr, text='Точность', bg=C1, fg=DIM,
                 font=('Segoe UI', 9)).pack(side='left')
        self.v_conf = tk.DoubleVar(value=0.82)
        tk.Scale(cr, from_=0.5, to=0.99, resolution=0.01, orient='horizontal',
                 variable=self.v_conf, bg=C1, fg=DIM, troughcolor=C2,
                 highlightthickness=0, bd=0, length=140,
                 font=('Segoe UI', 7)).pack(side='left', padx=8)

        erow = tk.Frame(wc, bg=C1)
        erow.pack(fill='x', pady=(6, 0))
        self.v_enter = tk.BooleanVar(value=True)
        tk.Checkbutton(erow, text='Нажимать Enter после клика (отправить)',
                       variable=self.v_enter,
                       bg=C1, fg=DIM, selectcolor=C2,
                       activebackground=C1, activeforeground=TXT,
                       font=('Segoe UI', 9), cursor='hand2').pack(side='left')

        FlatBtn(wc, '🔍  Проверить сейчас (без клика по факту)', self._test_find,
                bg=C2, fg=DIM, hbg=BRD, hfg=TXT,
                font=('Segoe UI', 8), padx=10, pady=6
                ).pack(fill='x', pady=(10, 0))

        # Бейджи методов / состояния шаблонов
        tk.Frame(body, bg=BG, height=10).pack()
        br = tk.Frame(body, bg=BG)
        br.pack(anchor='w')
        self.badges = [Badge(br, t['label']) for t in TEMPLATES.values()]
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

    # ── Захват шаблона ──────────────────────────────────────────────────────

    def capture_template(self, key: str, on_refreshed):
        if ImageGrab is None:
            self._log('Pillow не установлен — захват недоступен.', 'error')
            return
        self.root.iconify()
        self.root.after(350, lambda: self._start_capture(key, on_refreshed))

    def _start_capture(self, key, on_refreshed):
        def done(bbox):
            self.root.deiconify()
            if not bbox:
                self._log('Захват отменён.', 'dim')
                return
            try:
                img = ImageGrab.grab(bbox=bbox)
                img.save(TEMPLATES[key]['file'])
                self._log(f'✓ Шаблон "{TEMPLATES[key]["label"]}" сохранён '
                          f'({img.width}×{img.height})', 'success')
                on_refreshed()
            except Exception as e:
                self._log(f'Ошибка сохранения шаблона: {e}', 'error')

        RegionCapture(self.root, done)

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

    # ── Получение активных шаблонов ────────────────────────────────────────

    def _active_labels(self) -> list:
        return [k for k, row in self.tpl_rows.items() if row.var.get()]

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
        labels = self._active_labels()
        if not any(os.path.isfile(TEMPLATES[k]['file']) for k in labels):
            self._log('⚠ Сначала захвати хотя бы один шаблон кнопки!', 'error')
            return
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

        self._slog('Время! Ищу кнопки на экране…', 'warn')
        n      = self.sp_n.get()
        labels = self._active_labels()
        conf   = self.v_conf.get()
        enter  = self.v_enter.get()

        ok = 0
        for attempt in range(1, 4):
            if self._stop_evt.is_set(): return
            self._slog(f'Попытка {attempt}/3:', 'dim')
            ok = search_and_click(labels, n, conf, enter, self._slog, self._badge)
            if ok: break
            if attempt < 3: self._stop_evt.wait(5)

        if ok:
            self.root.after(0, lambda c=ok: self.ring.draw(100, '✓', f'Клик×{c}', SUC))
            self._slog(f'✓  Успех — нажато {ok} раз!', 'success')
        else:
            self.root.after(0, lambda: self.ring.draw(100, '✗', 'Не найдено', ERR))
            self._slog('✗  Кнопка не найдена. Проверь шаблон или открой чат.', 'error')

        if self.v_watch.get() and not self._stop_evt.is_set():
            iv = int(self.v_interval.get() or 30)
            self._slog(f'Наблюдение каждые {iv}с.', 'dim')
            while not self._stop_evt.is_set():
                self._stop_evt.wait(iv)
                if self._stop_evt.is_set(): break
                search_and_click(self._active_labels(), self.sp_n.get(),
                                 self.v_conf.get(), self.v_enter.get(),
                                 self._slog, self._badge)

        if not self._stop_evt.is_set():
            self._running = False
            self.root.after(0, lambda: [
                self.main_btn.recolor(ACC, BG, '#79b8ff'),
                self.main_btn.config(text='▶   СТАРТ'),
                self.lbl_hint.config(text=''),
            ])

    def _click_now(self):
        self._log('Ищу и нажимаю прямо сейчас…', 'accent')
        n, labels = self.sp_n.get(), self._active_labels()
        conf, enter = self.v_conf.get(), self.v_enter.get()
        threading.Thread(
            target=lambda: search_and_click(labels, n, conf, enter,
                                            self._slog, self._badge),
            daemon=True
        ).start()

    def _test_find(self):
        self._log('Тестовый поиск…', 'accent')
        def run():
            labels = self._active_labels()
            conf = self.v_conf.get()
            total = 0
            for i, key in enumerate(labels):
                tpl = TEMPLATES[key]
                self._badge(i, 'trying')
                boxes = find_matches(tpl['file'], conf, self._slog)
                total += len(boxes)
                self._slog(f'  "{tpl["label"]}": найдено {len(boxes)}',
                           'success' if boxes else 'dim')
                self._badge(i, 'ok' if boxes else 'idle')
            self._slog(f'Итого совпадений: {total}', 'accent')
        threading.Thread(target=run, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════════════════════════════

def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    root.tk.call('tk', 'scaling', 1.35)
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
