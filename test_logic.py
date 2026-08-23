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
