"""Юнит-тесты чистой логики (без UIA/Tk). Запуск: pytest -q"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import claude_continue_gui as app  # noqa: E402

NOW = datetime.datetime(2026, 8, 23, 12, 0, 0)


def test_i18n_tables_have_same_keys():
    assert set(app.I18N['ru']) == set(app.I18N['en'])


def test_themes_have_same_keys():
    assert set(app.THEMES['dark']) == set(app.THEMES['light'])


# ── parse_limit_text: абсолютное время ────────────────────────────────────────

def test_absolute_time_plain():
    assert app.parse_limit_text('Your limit resets at 15:30', NOW) == (15, 30)


def test_absolute_time_pm():
    assert app.parse_limit_text('limit resets at 3:45 PM', NOW) == (15, 45)


def test_absolute_time_am_midnight():
    assert app.parse_limit_text('resets at 12:30 AM', NOW) == (0, 30)


def test_available_again_at():
    assert app.parse_limit_text('You can try again at 09:05', NOW) == (9, 5)


def test_russian_absolute():
    assert app.parse_limit_text('Лимит сбросится в 07:15', NOW) == (7, 15)


# ── parse_limit_text: длительность ────────────────────────────────────────────

def test_duration_hours_and_minutes():
    assert app.parse_limit_text('try again in 2 hours and 5 minutes', NOW) == (14, 5)


def test_duration_hours_only():
    assert app.parse_limit_text('come back in 3 hours', NOW) == (15, 0)


def test_duration_minutes_only():
    assert app.parse_limit_text('in 45 minutes the limit resets', NOW) == (12, 45)


def test_duration_rolls_past_midnight():
    assert app.parse_limit_text('in 13 hours and 30 minutes', NOW) == (1, 30)


def test_russian_duration():
    assert app.parse_limit_text('Попробуйте через 1 час и 20 минут', NOW) == (13, 20)


# ── parse_limit_text: негативные ──────────────────────────────────────────────

def test_no_false_positive_on_chat_history():
    text = 'User: how do cron jobs work? Assistant: you can schedule a task at any time'
    assert app.parse_limit_text(text, NOW) is None


def test_empty_text_is_none():
    assert app.parse_limit_text('', NOW) is None


# ── фильтр сайдбара ───────────────────────────────────────────────────────────

def test_chrome_names_filtered():
    for n in ('Pinned', 'Recents', 'More options for Claude chat',
              'Show more', 'Relaunch to update'):
        assert not app._is_real_chat_name(n), n


def test_real_chats_survive_filter():
    for n in ('Show me how to write tests', 'Новый чат про деплой', 'chat with mom'):
        assert app._is_real_chat_name(n), n


# ── утилиты времени плана ─────────────────────────────────────────────────────

def test_plan_next_targets_tomorrow_for_passed_time(monkeypatch):
    monkeypatch.setattr(app.datetime, 'datetime', _FakeDateTime)
    a = AppStub()
    a._plan = [(9, 0), (23, 30)]
    targets = a._plan_next_targets()
    assert targets[0] == datetime.datetime(2026, 8, 23, 23, 30)
    assert targets[1] == datetime.datetime(2026, 8, 24, 9, 0)


class _FakeDateTime(datetime.datetime):
    @classmethod
    def now(cls):
        return NOW


class AppStub:
    """Минимальная заглушка: только то, что нужно _plan_next_targets."""
    _plan = []


AppStub._plan_next_targets = app.App._plan_next_targets


# --- parse_limit_text: контекст limit/usage (#16) ---

def test_context_required_rejects_bare_history_mention():
    text = 'we discussed that the job resets at 15:30 back then'
    assert app.parse_limit_text(text, NOW, require_context=True) is None
    # без требования контекста - старое поведение
    assert app.parse_limit_text(text, NOW) == (15, 30)


def test_context_required_accepts_real_limit_message():
    text = ('You have reached your usage limit. '
            'Your plan resets at 15:30.')
    assert app.parse_limit_text(text, NOW, require_context=True) == (15, 30)


def test_context_russian_keyword():
    text = 'Лимит исчерпан. Обновится в 09:05.'
    assert app.parse_limit_text(text, NOW, require_context=True) == (9, 5)


def test_context_window_is_local_not_global():
    # слово limit далеко (за пределами окна 120 знаков) от времени
    filler = 'x' * 200
    text = 'limit reached. ' + filler + ' task scheduled at 15:30'
    assert app.parse_limit_text(text, NOW, require_context=True) is None


def test_duration_with_context():
    text = 'Usage limit reached. Try again in 2 hours and 45 minutes.'
    assert app.parse_limit_text(text, NOW, require_context=True) == (14, 45)


def test_has_limit_context_spans():
    t = 'your usage limit resets at 15:30'
    i = t.find('15:30')
    assert app.has_limit_context(t, i, i + 5)
    assert not app.has_limit_context('nothing here', 0, 12)


def test_recent_items_tail():
    parts = ['msg%d' % k for k in range(100)]
    parts.append('limit resets at 15:30')
    joined = ' '.join(parts[-60:])
    assert 'msg99' in joined and 'msg0' not in joined
# --- CLI/headless (#17) ---

def _cli_args(argv):
    import sys as _s
    old = _s.argv
    try:
        _s.argv = ['prog'] + argv
        ns = app._build_cli_parser().parse_args(argv)
    finally:
        _s.argv = old
    return ns


def test_cli_defaults():
    ns = _cli_args(['--headless'])
    assert ns.at is None and ns.now is False and ns.chats == '3'
    assert ns.try_again if False else True
    assert ns.no_try_again is False and ns.no_continue is False
    assert abs(ns.confidence - 0.82) < 1e-9 and ns.interval == 0


def test_cli_target_parses_future():
    t = app._cli_target('05:00')
    assert t is not None and (t.hour, t.minute) == (5, 0) and t > datetime.datetime.now()


def test_cli_target_rejects_garbage():
    assert app._cli_target('25:00') is None
    assert app._cli_target('abc') is None
    assert app._cli_target('') is None


def test_run_headless_validates_before_uia(monkeypatch):
    # Валидация аргументов должна работать и без uiautomation (CI/ubuntu)
    ns = _cli_args(['--headless', '--at', '25:00'])
    assert app.run_headless(ns) == 2


# --- Профили приложений (пивот) ---

def test_resolve_profile_fallback():
    assert app._resolve_profile(None)['label'] == 'Claude Desktop'
    assert app._resolve_profile('no-such-app')['process'] == ['claude.exe']
    assert app._resolve_profile('cursor')['label'] == 'Cursor'


def test_every_profile_is_well_formed():
    for name, prof in app.APP_PROFILES.items():
        assert prof['process'], name
        assert all(x == x.lower() for x in prof['process']), name
        assert prof['button_labels'] and prof['input_names'], name
        assert isinstance(prof['experimental'], bool), name


def test_claude_profile_keeps_reference_behavior():
    p = app.APP_PROFILES['claude']
    assert 'Попробовать снова' in p['button_labels']
    assert 'prompt' in [n.lower() for n in p['input_names']]
    assert p['experimental'] is False


def test_experimental_profiles_marked():
    assert app.APP_PROFILES['cursor']['experimental'] is True
    assert app.APP_PROFILES['windsurf']['experimental'] is True


def test_cli_profile_choices_and_list():
    ns = _cli_args(['--headless', '--profile', 'cursor'])
    assert ns.profile == 'cursor'
    import pytest as _pt
    with _pt.raises(SystemExit):
        _cli_args(['--headless', '--profile', 'nope'])


# --- Quick wins: версия, ротация файлового лога ---

def test_version_constant():
    import re as _re
    assert _re.match(r'3\.', app.__version__)
    assert app.__version__ == '3.17.0'


def test_headless_log_file_rotation(tmp_path):
    lf = tmp_path / 'run.log'
    log = app._headless_logger(str(lf), max_file_lines=100)
    for i in range(120):
        log('line %d' % i)
    count = len(lf.read_text(encoding='utf-8').splitlines())
    assert 0 < count <= 100, count


def test_headless_logger_counts_existing_file(tmp_path):
    lf = tmp_path / 'pre.log'
    lf.write_text('\n'.join('x%d' % k for k in range(95)) + '\n',
                   encoding='utf-8')
    log = app._headless_logger(str(lf), max_file_lines=100)
    for i in range(20):
        log('new %d' % i)
    count = len(lf.read_text(encoding='utf-8').splitlines())
    assert count <= 100


# --- Профильные overrides из settings.json ---

def test_resolve_profile_overrides_whitelist():
    ov = {'cursor': {'button_labels': ['Ещё раз'], 'bogus_key': 1}}
    p = app._resolve_profile('cursor', ov)
    assert p['button_labels'] == ['Ещё раз']
    assert 'process' in p and 'bogus_key' not in p
    # базовый реестр не мутирует и другие профили не задеты
    assert app.APP_PROFILES['cursor']['button_labels'] != ['Ещё раз']
    assert app._resolve_profile('windsurf', ov)['label'] == 'Windsurf'


def test_resolve_profile_bad_overrides_ignored():
    p = app._resolve_profile('cursor', {'cursor': 'not-a-dict', 42: {}})
    assert p['label'] == 'Cursor'


def test_profile_persists_via_settings(tmp_path, monkeypatch):
    import claude_continue_gui as m
    m.SETTINGS_FILE = str(tmp_path / 'settings.json')
    root = tk_root = None
    # сохранение: главный поток пишет текущий профиль в файл
    class Store: pass
    fake = object.__new__(m.App)
    fake.lang = 'ru'; fake._theme = 'dark'
    fake._cfg = {}; fake._history = []
    fake._running = False; fake._target = None
    fake._plan = []
    fake._tray_minimize = type('V', (), {'get': lambda s: True})()
    fake._selected_chat_idx = set()
    m._CURRENT_PROFILE['name'] = 'cursor'
    called = {}
    for attr, val in [('sp_h', 5), ('sp_m', 0)]:
        setattr(fake, attr, type('S', (), {'get': lambda s, v=val: v})())
    fake._sg = lambda a, d: d
    fake._sgv = lambda a, d: d
    fake._watch_interval = lambda: 30
    m.App._save_settings(fake)
    data = __import__('json').load(open(m.SETTINGS_FILE, encoding='utf-8'))
    assert data['profile'] == 'cursor'


# --- macOS AX: выбор чатов ---

FLAT = [
    ('AXButton', 'New chat'),
    ('AXButton', 'Pinned'),
    ('AXButton', 'Как сделать cron'),
    ('AXStaticText', 'Some article text'),
    ('AXButton', 'Try again'),
    ('AXButton', 'Retry'),
    ('AXButton', 'more options for Как сделать'),
    ('AXButton', 'Как сделать cron'),          # дубликат
    ('AXButton', ''),                            # пустое
    ('AXGroup', 'Chat group'),
]


def test_mac_pick_chat_titles_basic():
    prof = app.APP_PROFILES['claude']
    out = app.mac_pick_chat_titles(FLAT, prof['button_labels'],
                                   prof['sidebar_chrome'],
                                   prof['sidebar_prefixes'])
    assert out == ['Как сделать cron']


def test_mac_pick_chat_titles_max_and_order():
    seq = [(('AXButton'), 'chat %d' % k) for k in range(50)]
    out = app.mac_pick_chat_titles(seq, max_items=5)
    assert len(out) == 5 and out[0] == 'chat 0'


def test_mac_empty_tree():
    assert app.mac_pick_chat_titles([]) == []
