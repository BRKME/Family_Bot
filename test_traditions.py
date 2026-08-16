# -*- coding: utf-8 -*-
"""Живые традиции: отметка «было / не было» и авто-архив.

Раньше традиции архивировались руками — «Вечер воспоминаний» просто
закомментировали в коде. Теперь традиция, которую пропустили три раза
подряд, уходит в архив сама: список перестаёт быть кладбищем намерений.

Молчание считается пропуском — иначе традиция, которую никогда не
отмечают, не заархивируется никогда, и механика бессмысленна. Чтобы
случайный пропуск не убил живую традицию, на втором подряд приходит
предупреждение, а сообщение об архиве несёт кнопку «Вернуть».
"""
import json
import sys

import pytest

sys.path.insert(0, '.')

from traditions import (ARCHIVE_AFTER, TraditionLog, archive_message,
                        event_keyboard, warning_line)


@pytest.fixture
def log(tmp_path):
    return TraditionLog(str(tmp_path / 'traditions.json'))


# ── Отметки ──────────────────────────────────────────────────────────────

def test_done_resets_the_miss_counter(log):
    for _ in range(2):
        log.record('tarelka', '2026-06-27', 'skip')
    log.record('tarelka', '2026-07-25', 'done')
    assert log.misses_in_row('tarelka') == 0


def test_misses_accumulate(log):
    log.record('tarelka', '2026-05-30', 'skip')
    log.record('tarelka', '2026-06-27', 'skip')
    assert log.misses_in_row('tarelka') == 2


def test_answer_for_a_date_can_be_changed(log):
    log.record('tarelka', '2026-06-27', 'skip')
    log.record('tarelka', '2026-06-27', 'done')
    assert log.misses_in_row('tarelka') == 0


def test_state_survives_reload(log, tmp_path):
    log.record('new', '2026-06-13', 'skip')
    again = TraditionLog(log.path)
    assert again.misses_in_row('new') == 1


def test_broken_file_does_not_crash_the_bot(tmp_path):
    p = tmp_path / 'traditions.json'
    p.write_text('{ это не json', encoding='utf-8')
    assert TraditionLog(str(p)).misses_in_row('tarelka') == 0


# ── Архив ────────────────────────────────────────────────────────────────

def test_archived_after_three_misses_in_a_row(log):
    for d in ('2026-05-30', '2026-06-27', '2026-07-25'):
        log.record('tarelka', d, 'skip')
    assert log.is_archived('tarelka')


def test_two_misses_are_not_enough(log):
    for d in ('2026-05-30', '2026-06-27'):
        log.record('tarelka', d, 'skip')
    assert not log.is_archived('tarelka')


def test_archived_tradition_is_filtered_out(log):
    for d in ('2026-05-30', '2026-06-27', '2026-07-25'):
        log.record('tarelka', d, 'skip')
    active = log.filter_active({'tarelka': {}, 'new': {}})
    assert set(active) == {'new'}


def test_restore_brings_it_back_with_a_clean_counter(log):
    for d in ('2026-05-30', '2026-06-27', '2026-07-25'):
        log.record('tarelka', d, 'skip')
    log.restore('tarelka')
    assert not log.is_archived('tarelka')
    assert log.misses_in_row('tarelka') == 0


def test_archive_keeps_the_date_for_the_digest(log):
    for d in ('2026-05-30', '2026-06-27', '2026-07-25'):
        log.record('tarelka', d, 'skip')
    assert log.archived_on('tarelka') == '2026-07-25'


# ── Тексты и кнопки ──────────────────────────────────────────────────────

def test_event_day_message_has_both_answers():
    data = [b['callback_data'] for row in event_keyboard('tarelka')['inline_keyboard']
            for b in row]
    assert 'trad_done_tarelka' in data
    assert 'trad_skip_tarelka' in data


def test_warning_appears_on_the_second_miss_only(log):
    log.record('tarelka', '2026-05-30', 'skip')
    assert warning_line(log, 'tarelka') == ''
    log.record('tarelka', '2026-06-27', 'skip')
    assert 'архив' in warning_line(log, 'tarelka').lower()


def test_archive_message_offers_a_way_back():
    msg, kb = archive_message('tarelka', 'Путешествие на тарелке')
    assert 'Путешествие на тарелке' in msg
    data = [b['callback_data'] for row in kb['inline_keyboard'] for b in row]
    assert 'trad_restore_tarelka' in data


def test_skip_button_is_not_framed_as_failure():
    buttons = [b for row in event_keyboard('new')['inline_keyboard'] for b in row]
    skip = next(b for b in buttons if b['callback_data'].startswith('trad_skip'))
    for word in ('провал', 'сорвал', '❌'):
        assert word not in skip['text'].lower()


def test_archive_threshold_is_three():
    assert ARCHIVE_AFTER == 3


# ── Интеграция с ботом ───────────────────────────────────────────────────

def _notifier(tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(tmp_path)
    os.environ.setdefault('TELEGRAM_TOKEN', 'test-token')
    os.environ.setdefault('TELEGRAM_CHAT_ID', 'test-chat')
    from notifier import FamilyScheduleBot
    n = FamilyScheduleBot()
    n.trad_log = TraditionLog(str(tmp_path / 'traditions.json'))
    return n


def test_archived_tradition_gets_no_reminders(tmp_path, monkeypatch):
    """Главное, ради чего всё затевалось: заархивированная традиция
    перестаёт напоминать о себе."""
    n = _notifier(tmp_path, monkeypatch)
    for d in ('2026-05-30', '2026-06-27', '2026-07-25'):
        n.trad_log.record('tarelka', d, 'skip')
    assert 'tarelka' not in n.active_events()
    assert 'new' in n.active_events()


def test_restored_tradition_reminds_again(tmp_path, monkeypatch):
    n = _notifier(tmp_path, monkeypatch)
    for d in ('2026-05-30', '2026-06-27', '2026-07-25'):
        n.trad_log.record('tarelka', d, 'skip')
    n.trad_log.restore('tarelka')
    assert 'tarelka' in n.active_events()


def test_council_is_a_tradition_too(tmp_path, monkeypatch):
    """Семейный совет — такая же традиция: три пропуска подряд, и
    воскресное сообщение с ним больше не приходит."""
    n = _notifier(tmp_path, monkeypatch)
    for d in ('2026-08-02', '2026-08-09', '2026-08-16'):
        n.trad_log.record('council', d, 'skip')
    assert n.trad_log.is_archived('council')


def test_event_day_message_carries_buttons(tmp_path, monkeypatch):
    """Кнопки должны быть в самом сообщении, а не появляться потом:
    иначе в день события отметить традицию нечем."""
    n = _notifier(tmp_path, monkeypatch)
    kb = n.reminder_keyboard([{'key': 'tarelka', 'type': 'event_day'}])
    data = [b['callback_data'] for row in kb['inline_keyboard'] for b in row]
    assert 'trad_done_tarelka' in data


def test_no_buttons_for_advance_reminders(tmp_path, monkeypatch):
    """За неделю и за три дня отмечать нечего — событие ещё не наступило."""
    n = _notifier(tmp_path, monkeypatch)
    assert n.reminder_keyboard([{'key': 'tarelka', 'type': 'week_before'}]) is None
    assert n.reminder_keyboard([{'key': 'new', 'type': 'three_days_before'}]) is None


def test_council_message_has_buttons(tmp_path, monkeypatch):
    n = _notifier(tmp_path, monkeypatch)
    kb = n.council_keyboard()
    data = [b['callback_data'] for row in kb['inline_keyboard'] for b in row]
    assert 'trad_done_council' in data and 'trad_skip_council' in data


def test_callback_records_the_answer(tmp_path, monkeypatch):
    import asyncio
    import os
    monkeypatch.chdir(tmp_path)
    os.environ.setdefault('TELEGRAM_TOKEN', 'test-token')
    from tracker_bot import TaskTrackerBot

    b = TaskTrackerBot()
    b.trad_log = TraditionLog(str(tmp_path / 'traditions.json'))
    calls = {}

    async def fake_answer(self, qid, text=None):
        calls['text'] = text

    async def fake_edit(self, message_id, keyboard):
        calls['kb'] = keyboard

    monkeypatch.setattr(type(b), 'answer_callback_query', fake_answer)
    monkeypatch.setattr(type(b), 'edit_message_keyboard', fake_edit, raising=False)

    asyncio.run(b.process_callback('trad_skip_tarelka', 'q1', 5, 'текст'))
    assert b.trad_log.misses_in_row('tarelka') == 1
    assert calls['text']


def test_callback_restore_brings_it_back(tmp_path, monkeypatch):
    import asyncio
    import os
    monkeypatch.chdir(tmp_path)
    os.environ.setdefault('TELEGRAM_TOKEN', 'test-token')
    from tracker_bot import TaskTrackerBot

    b = TaskTrackerBot()
    b.trad_log = TraditionLog(str(tmp_path / 'traditions.json'))
    for d in ('2026-05-30', '2026-06-27', '2026-07-25'):
        b.trad_log.record('tarelka', d, 'skip')

    async def noop(self, *a, **kw):
        return True

    monkeypatch.setattr(type(b), 'answer_callback_query', noop)
    monkeypatch.setattr(type(b), 'edit_message_keyboard', noop, raising=False)

    asyncio.run(b.process_callback('trad_restore_tarelka', 'q1', 5, 'текст'))
    assert not b.trad_log.is_archived('tarelka')


def test_silence_counts_as_a_miss(tmp_path, monkeypatch):
    """Молчание — пропуск: иначе традиция, которую никогда не отмечают,
    не заархивируется никогда, и механика бессмысленна. Автозакрытие
    ставит «не было» за прошедшее событие, если ответа так и не пришло."""
    n = _notifier(tmp_path, monkeypatch)
    n.close_unanswered('tarelka', '2026-05-30')
    assert n.trad_log.misses_in_row('tarelka') == 1


def test_silence_does_not_overwrite_an_answer(tmp_path, monkeypatch):
    n = _notifier(tmp_path, monkeypatch)
    n.trad_log.record('tarelka', '2026-05-30', 'done')
    n.close_unanswered('tarelka', '2026-05-30')
    assert n.trad_log.misses_in_row('tarelka') == 0


def test_past_events_get_closed_on_next_run(tmp_path, monkeypatch):
    """Пропуск засчитывается не в день события, а при следующем запуске:
    у человека есть весь день, чтобы нажать кнопку."""
    n = _notifier(tmp_path, monkeypatch)
    n.trad_log.record('tarelka', '2026-05-30', 'skip')   # прошлое событие
    closed = n.close_past_events(today='2026-06-01')
    assert 'tarelka' not in closed          # уже отвечено, повторно не трогаем


def test_council_silence_is_closed_weekly(tmp_path, monkeypatch):
    """Совет проходит по воскресеньям: непрожатое прошлое воскресенье
    закрывается как пропуск при следующем."""
    n = _notifier(tmp_path, monkeypatch)
    n.close_unanswered('council', '2026-08-09')
    n.close_unanswered('council', '2026-08-16')
    assert n.trad_log.misses_in_row('council') == 2


def test_archive_notice_is_sent_when_it_happens(tmp_path, monkeypatch):
    """Архив не должен быть тихим: иначе через полгода не вспомнить, что
    вообще было в списке."""
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append((message, keyboard))
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    for d in ('2026-05-30', '2026-06-27'):
        n.trad_log.record('tarelka', d, 'skip')
    n.trad_log.record('tarelka', '2026-07-25', 'skip')

    asyncio.run(n.announce_archived(['tarelka']))
    assert sent, 'сообщение об архиве не ушло'
    msg, kb = sent[0]
    assert 'архив' in msg.lower()
    data = [b['callback_data'] for row in kb['inline_keyboard'] for b in row]
    assert 'trad_restore_tarelka' in data


def test_nothing_is_announced_without_archiving(tmp_path, monkeypatch):
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append(message)
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    asyncio.run(n.announce_archived([]))
    assert sent == []
