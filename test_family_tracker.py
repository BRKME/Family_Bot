# -*- coding: utf-8 -*-
"""Трекер семейных традиций — процесс, который слушает нажатия.

Без него кнопки в сообщениях бесполезны: Telegram шлёт callback, а
принять его некому. notifier.py живёт в GitHub Actions и умирает сразу
после отправки, поэтому нужен отдельный долгоживущий процесс на VPS.

Он же решает вторую проблему: файловая система Actions одноразовая, и
traditions.json там не переживает запуск. Состояние хранится локально на
VPS и синхронизируется в репозиторий через GitHub API — та же схема, что
у личного бота с program.json.
"""
import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, '.')

os.environ.setdefault('TELEGRAM_TOKEN', 'test-token')
os.environ.setdefault('TELEGRAM_CHAT_ID', 'test-chat')

from family_tracker import FamilyTracker
from traditions import TraditionLog


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    t = FamilyTracker()
    t.trad_log = TraditionLog(str(tmp_path / 'traditions.json'))
    t.synced = []

    async def fake_sync(self):
        self.synced.append(True)
        return True

    async def fake_answer(self, qid, text=None):
        self.answered = text

    async def fake_kb(self, mid, kb):
        self.keyboard = kb

    monkeypatch.setattr(type(t), 'sync_to_github', fake_sync)
    monkeypatch.setattr(type(t), 'answer_callback', fake_answer)
    monkeypatch.setattr(type(t), 'edit_keyboard', fake_kb)
    return t


# ── Обработка нажатий ────────────────────────────────────────────────────

def test_done_is_recorded_and_synced(tracker):
    asyncio.run(tracker.handle_callback('trad_done_cleaning', 'q1', 10))
    assert tracker.trad_log.misses_in_row('cleaning') == 0
    assert tracker.trad_log.data['cleaning']['marks']
    assert tracker.synced, 'состояние не ушло в репозиторий'


def test_skip_increments_the_counter(tracker):
    asyncio.run(tracker.handle_callback('trad_skip_cleaning', 'q1', 10))
    assert tracker.trad_log.misses_in_row('cleaning') == 1


def test_restore_clears_the_archive(tracker):
    for d in ('2026-08-02', '2026-08-09', '2026-08-16'):
        tracker.trad_log.record('cleaning', d, 'skip')
    asyncio.run(tracker.handle_callback('trad_restore_cleaning', 'q1', 10))
    assert not tracker.trad_log.is_archived('cleaning')


def test_user_always_gets_a_reply(tracker):
    """Без ответа на callback Telegram крутит часики на кнопке."""
    asyncio.run(tracker.handle_callback('trad_done_games', 'q1', 10))
    assert tracker.answered


def test_pressed_state_is_visible_on_the_button(tracker):
    asyncio.run(tracker.handle_callback('trad_done_games', 'q1', 10))
    texts = [b['text'] for row in tracker.keyboard['inline_keyboard'] for b in row]
    assert any('✅' in t for t in texts)


def test_foreign_callbacks_are_ignored(tracker):
    """Трекер личного бота шлёт свои callback'и в другой чат, но чужой
    формат не должен ронять процесс."""
    asyncio.run(tracker.handle_callback('toggle_day_3', 'q1', 10))
    assert tracker.trad_log.data == {}


def test_broken_callback_does_not_crash(tracker):
    asyncio.run(tracker.handle_callback('trad_', 'q1', 10))
    asyncio.run(tracker.handle_callback('trad_weird', 'q1', 10))
    assert tracker.trad_log.data == {}


def test_repeat_press_changes_the_answer(tracker):
    asyncio.run(tracker.handle_callback('trad_skip_cleaning', 'q1', 10))
    asyncio.run(tracker.handle_callback('trad_done_cleaning', 'q2', 10))
    assert tracker.trad_log.misses_in_row('cleaning') == 0


# ── Опрос Telegram ───────────────────────────────────────────────────────

def test_offset_advances_past_processed_updates(tracker):
    """Без сдвига offset один и тот же update обрабатывается вечно."""
    updates = [{'update_id': 41, 'callback_query': {
        'id': 'q', 'data': 'trad_done_cleaning', 'message': {'message_id': 5}}}]
    asyncio.run(tracker.process_updates(updates))
    assert tracker.offset == 42


def test_non_callback_updates_are_skipped(tracker):
    updates = [{'update_id': 7, 'message': {'text': 'привет'}}]
    asyncio.run(tracker.process_updates(updates))
    assert tracker.offset == 8
    assert tracker.trad_log.data == {}
