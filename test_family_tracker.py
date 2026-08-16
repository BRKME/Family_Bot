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


# ── Логи: без них отладка идёт вслепую ───────────────────────────────────

def test_failed_sync_is_logged_with_the_status(tmp_path, monkeypatch, caplog):
    """Инцидент 16.08: токен не имел прав на запись, GitHub отвечал 403, а
    в логе не было ни строки — причину искали вручную через curl."""
    import logging
    t = FamilyTracker()
    t.trad_log = TraditionLog(str(tmp_path / 'traditions.json'))
    t.github_token = 'x'

    class FakeResp:
        status = 403

        async def json(self):
            return {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeSession:
        def get(self, *a, **kw):
            return FakeResp()

        def put(self, *a, **kw):
            return FakeResp()

    t.session = FakeSession()
    with caplog.at_level(logging.INFO):
        ok = asyncio.run(t.sync_to_github())
    assert ok is False
    assert '403' in caplog.text


def test_successful_sync_is_logged(tmp_path, monkeypatch, caplog):
    """Успех тоже должен быть виден: иначе непонятно, дошло состояние или
    просто ничего не произошло."""
    import logging
    t = FamilyTracker()
    t.trad_log = TraditionLog(str(tmp_path / 'traditions.json'))
    t.github_token = 'x'

    class Resp:
        def __init__(self, status):
            self.status = status

        async def json(self):
            return {'sha': 'abc'}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeSession:
        def get(self, *a, **kw):
            return Resp(200)

        def put(self, *a, **kw):
            return Resp(200)

    t.session = FakeSession()
    with caplog.at_level(logging.INFO):
        ok = asyncio.run(t.sync_to_github())
    assert ok is True
    assert 'traditions.json' in caplog.text


def test_every_press_is_logged(tracker, caplog):
    """По логу должно быть видно, что именно нажали и что записалось."""
    import logging
    with caplog.at_level(logging.INFO):
        asyncio.run(tracker.handle_callback('trad_skip_cleaning', 'q1', 10))
    assert 'cleaning' in caplog.text


# ── Что человек видит во всплывашке ──────────────────────────────────────

def test_first_miss_is_answered_calmly(tracker):
    """Первый пропуск — обычное дело. Если давить с самого начала,
    человек перестанет отвечать, и вместо честной картины будет молчание,
    которое тоже засчитается пропуском."""
    asyncio.run(tracker.handle_callback('trad_skip_cleaning', 'q1', 10))
    text = tracker.answered.lower()
    assert 'жаль' not in text and 'архив' not in text


def test_last_chance_says_what_is_being_lost(tracker):
    """На предпоследнем пропуске говорим не о вине, а о цене."""
    tracker.trad_log.record('cleaning', '2026-08-02', 'skip')
    asyncio.run(tracker.handle_callback('trad_skip_cleaning', 'q1', 10))
    text = tracker.answered.lower()
    assert 'осталась одна' in text or 'последн' in text
    assert 'жаль' in text


def test_archive_moment_is_announced_in_the_popup(tracker):
    for d in ('2026-08-02', '2026-08-09'):
        tracker.trad_log.record('cleaning', d, 'skip')
    asyncio.run(tracker.handle_callback('trad_skip_cleaning', 'q1', 10))
    assert 'архив' in tracker.answered.lower()


def test_popup_fits_telegram_limit(tracker):
    """Telegram обрезает всплывашку примерно на 200 символах."""
    for i in range(3):
        asyncio.run(tracker.handle_callback('trad_skip_cleaning', f'q{i}', 10))
        assert len(tracker.answered) <= 200


def test_done_never_scolds(tracker):
    asyncio.run(tracker.handle_callback('trad_done_cleaning', 'q1', 10))
    assert 'жаль' not in tracker.answered.lower()


def test_daily_ritual_warns_late_not_early(tracker):
    """У благодарности порог десять: на третьем пропуске пугать нечем."""
    for i in range(1, 3):
        tracker.trad_log.record('gratitude', f'2026-08-{i:02d}', 'skip')
    asyncio.run(tracker.handle_callback('trad_skip_gratitude', 'q1', 10))
    assert 'жаль' not in tracker.answered.lower()


# ── Сообщения в чат: их видит вся семья ──────────────────────────────────

def test_chat_message_on_every_miss(tracker, monkeypatch):
    """Всплывашку видит только нажавший, а традиция — общее дело: семья
    должна знать, что она под угрозой, чтобы кто-то успел сказать
    «давайте всё-таки сделаем»."""
    sent = []

    async def fake_chat(self, text, keyboard=None):
        sent.append(text)

    monkeypatch.setattr(type(tracker), 'send_chat', fake_chat)
    asyncio.run(tracker.handle_callback('trad_skip_cleaning', 'q1', 10))
    assert sent, 'семья не увидела пропуск'


def test_tone_grows_but_stays_hopeful(tracker):
    """С усилением, но без уныния: сообщение должно звать вернуться, а не
    сообщать, что всё пропало."""
    texts = []
    for i, d in enumerate(('2026-08-02', '2026-08-09'), 1):
        tracker.trad_log.record('cleaning', d, 'skip')
        texts.append(tracker.miss_announcement('cleaning'))
    assert texts[0] != texts[1], 'сообщения одинаковые'
    for t in texts:
        low = t.lower()
        assert 'провал' not in low and 'плохо' not in low


def test_last_miss_names_what_is_at_stake(tracker):
    """У порога 3 «последняя попытка» наступает на втором пропуске, а не
    на первом: после первого их остаётся ещё две."""
    for d in ('2026-08-02', '2026-08-09'):
        tracker.trad_log.record('cleaning', d, 'skip')
    text = tracker.miss_announcement('cleaning')
    assert 'последн' in text.lower()


def test_archive_is_announced_to_everyone(tracker, monkeypatch):
    sent = []

    async def fake_chat(self, text, keyboard=None):
        sent.append((text, keyboard))

    monkeypatch.setattr(type(tracker), 'send_chat', fake_chat)
    for d in ('2026-08-02', '2026-08-09'):
        tracker.trad_log.record('cleaning', d, 'skip')
    asyncio.run(tracker.handle_callback('trad_skip_cleaning', 'q1', 10))

    text, kb = sent[-1]
    assert 'архив' in text.lower()
    data = [b['callback_data'] for row in kb['inline_keyboard'] for b in row]
    assert 'trad_restore_cleaning' in data


def test_done_sends_nothing_to_the_chat(tracker, monkeypatch):
    """Выполненная традиция и так видна по отметке на кнопке —
    поздравлять сообщением значит засорять чат."""
    sent = []

    async def fake_chat(self, text, keyboard=None):
        sent.append(text)

    monkeypatch.setattr(type(tracker), 'send_chat', fake_chat)
    asyncio.run(tracker.handle_callback('trad_done_cleaning', 'q1', 10))
    assert sent == []


def test_tradition_is_named_not_keyed(tracker):
    """В чат идёт человеческое название, а не ключ из кода."""
    tracker.trad_log.record('cleaning', '2026-08-02', 'skip')
    assert 'cleaning' not in tracker.miss_announcement('cleaning')
    assert 'борка' in tracker.miss_announcement('cleaning')
