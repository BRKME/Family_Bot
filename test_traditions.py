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


# ── Уборка и игры — такие же традиции ────────────────────────────────────

def test_cleaning_is_a_tradition(tmp_path, monkeypatch):
    """Большая уборка приходила отдельной веткой и в механику не входила:
    её нельзя было ни отметить, ни заархивировать."""
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append((message, keyboard))
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    asyncio.run(n.send_cleaning_reminder())

    msg, kb = sent[0]
    assert 'Уборка' in msg
    data = [b['callback_data'] for row in kb['inline_keyboard'] for b in row]
    assert 'trad_done_cleaning' in data and 'trad_skip_cleaning' in data


def test_games_are_a_tradition(tmp_path, monkeypatch):
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append(keyboard)
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    asyncio.run(n.send_games_reminder())
    data = [b['callback_data'] for row in sent[0]['inline_keyboard'] for b in row]
    assert 'trad_done_games' in data


def test_archived_cleaning_stops_reminding(tmp_path, monkeypatch):
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append(message)
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    for d in ('2026-08-02', '2026-08-09', '2026-08-16'):
        n.trad_log.record('cleaning', d, 'skip')

    asyncio.run(n.send_cleaning_reminder())
    assert sent == [], 'заархивированная уборка всё ещё напоминает'


def test_tomorrow_reminder_also_stops(tmp_path, monkeypatch):
    """Субботнее «завтра уборка» — часть той же традиции."""
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append(message)
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    for d in ('2026-08-02', '2026-08-09', '2026-08-16'):
        n.trad_log.record('cleaning', d, 'skip')

    asyncio.run(n.send_cleaning_tomorrow())
    assert sent == []


def test_daily_gratitude_is_not_archivable(tmp_path, monkeypatch):
    """Ежедневная благодарность — привычка, а не традиция: архивировать
    её по трём пропускам значило бы убрать её на первой же занятой
    неделе."""
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append(message)
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    for d in ('2026-08-14', '2026-08-15', '2026-08-16'):
        n.trad_log.record('gratitude', d, 'skip')

    asyncio.run(n.send_gratitude_reminder())
    assert sent, 'благодарность не должна архивироваться'


def test_no_backdated_misses_on_first_run(tmp_path, monkeypatch):
    """Автозакрытие не должно записывать пропуски за дни, когда механики
    ещё не существовало: иначе на первой же неделе уборка уходит в архив
    за события, которые бот не показывал."""
    n = _notifier(tmp_path, monkeypatch)
    assert n.close_past_weekly('cleaning', 6) == []
    assert n.trad_log.misses_in_row('cleaning') == 0


def test_misses_counted_after_the_tradition_is_seen(tmp_path, monkeypatch):
    """После первого показа события пропуски считаются как обычно."""
    n = _notifier(tmp_path, monkeypatch)
    n.trad_log.mark_seen('cleaning', '2026-08-01')
    n.trad_log.record('cleaning', '2026-08-02', 'skip')
    assert n.trad_log.misses_in_row('cleaning') == 1


# ── Благодарность: ежедневный ритм, свой порог ───────────────────────────

def test_gratitude_has_buttons(tmp_path, monkeypatch):
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append(keyboard)
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    asyncio.run(n.send_gratitude_reminder())
    data = [b['callback_data'] for row in sent[0]['inline_keyboard'] for b in row]
    assert 'trad_done_gratitude' in data and 'trad_skip_gratitude' in data


def test_three_misses_do_not_kill_a_daily_ritual(log):
    """Три пропуска у месячной традиции — квартал, у ежедневной — три дня.
    Одна командировка не должна убивать благодарность."""
    for d in ('2026-08-01', '2026-08-02', '2026-08-03'):
        log.record('gratitude', d, 'skip')
    assert not log.is_archived('gratitude')


def test_gratitude_archives_after_ten_misses(log):
    for i in range(1, 11):
        log.record('gratitude', f'2026-08-{i:02d}', 'skip')
    assert log.is_archived('gratitude')


def test_threshold_is_per_tradition():
    from traditions import threshold_for
    assert threshold_for('gratitude') == 10
    assert threshold_for('cleaning') == 3
    assert threshold_for('tarelka') == 3


def test_gratitude_warns_before_the_end(log):
    for i in range(1, 10):
        log.record('gratitude', f'2026-08-{i:02d}', 'skip')
    assert 'архив' in warning_line(log, 'gratitude').lower()


def test_archived_gratitude_stops_reminding(tmp_path, monkeypatch):
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append(message)
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    for i in range(1, 11):
        n.trad_log.record('gratitude', f'2026-08-{i:02d}', 'skip')
    asyncio.run(n.send_gratitude_reminder())
    assert sent == []


def test_state_is_read_from_the_repo_copy(tmp_path, monkeypatch):
    """Actions поднимает контейнер с нуля: traditions.json приезжает
    вместе с чекаутом репозитория. Если файл есть — счётчики должны
    подхватиться, иначе архив не наступит никогда."""
    (tmp_path / 'traditions.json').write_text(json.dumps({
        'cleaning': {'marks': {'2026-08-02': 'skip', '2026-08-09': 'skip'},
                     'archived': None, 'seen': '2026-08-01'}
    }), encoding='utf-8')
    n = _notifier(tmp_path, monkeypatch)
    n.trad_log = TraditionLog('traditions.json')
    assert n.trad_log.misses_in_row('cleaning') == 2


def test_chronos_is_back_in_the_active_list(tmp_path, monkeypatch):
    """«Вечер воспоминаний» был заархивирован по-старому — закомментирован
    в коде. Теперь он вернулся и живёт по общим правилам: с кнопками и с
    авто-архивом, без правки кода."""
    n = _notifier(tmp_path, monkeypatch)
    assert 'chronos' in n.recurring_events
    assert 'chronos' in n.active_events()
    assert n.recurring_events['chronos']['rule'] == 'third_saturday'


def test_chronos_can_be_archived_by_the_mechanic(tmp_path, monkeypatch):
    n = _notifier(tmp_path, monkeypatch)
    for d in ('2026-06-20', '2026-07-18', '2026-08-15'):
        n.trad_log.record('chronos', d, 'skip')
    assert 'chronos' not in n.active_events()


def test_chronos_has_a_human_name(tmp_path, monkeypatch):
    n = _notifier(tmp_path, monkeypatch)
    assert 'воспоминаний' in n.tradition_names()['chronos'].lower()


def test_morning_message_has_no_parenting_quotes(tmp_path, monkeypatch):
    """Цитаты были о воспитании и обращены к родителям — в общем чате их
    читают и дети, для которых это текст о себе в третьем лице."""
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append(message)
        return True

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    asyncio.run(n.send_morning_message())
    assert '💭' not in sent[0]
    assert 'пословица' not in sent[0].lower()


# ── Компактное утреннее сообщение ────────────────────────────────────────

def _morning(tmp_path, monkeypatch):
    import asyncio
    n = _notifier(tmp_path, monkeypatch)
    sent = []

    async def fake_send(self, message, send_ss=False, keyboard=None):
        sent.append(message)
        return True

    async def fake_weather(self):
        return "20°C, облачно"

    monkeypatch.setattr(type(n), 'send_telegram_message', fake_send)
    monkeypatch.setattr(type(n), 'get_weather_forecast', fake_weather)
    asyncio.run(n.send_morning_message())
    return sent[0]


def test_weather_is_one_line_right_after_the_date(tmp_path, monkeypatch):
    """Раньше шапка занимала семь строк — погода, ветер, курс, цитата, —
    и главное начиналось в середине сообщения."""
    lines = [l for l in _morning(tmp_path, monkeypatch).splitlines() if l.strip()]
    assert 'облачно' in lines[1]
    assert 'Ветер' not in lines[1]


def test_no_currency_rates(tmp_path, monkeypatch):
    """Курс BTC в семейном чате не нужен: он личный, и в личном боте есть."""
    msg = _morning(tmp_path, monkeypatch)
    assert 'BTC' not in msg and 'USD' not in msg


def test_kids_schedule_leads_with_time(tmp_path, monkeypatch):
    """Время слева выхватывается глазом мгновенно — это единственное, что
    реально нужно утром."""
    msg = _morning(tmp_path, monkeypatch)
    assert 'Сегодня:' in msg
    lines = [l for l in msg.splitlines() if 'Марта' in l]
    assert lines and lines[0].strip().startswith('12:00')


def test_dishes_are_a_single_short_line(tmp_path, monkeypatch):
    msg = _morning(tmp_path, monkeypatch)
    assert 'Посуда: ' in msg
    assert '🍽️' not in msg


def test_emoji_only_in_the_header(tmp_path, monkeypatch):
    """Одна метка на сообщение: когда помечено всё, не помечено ничего."""
    msg = _morning(tmp_path, monkeypatch)
    body = msg.split('\n', 1)[1]
    for e in ('👨‍👩‍👧‍👦', '🍽️', '📱', '👧', '👦', '💭'):
        assert e not in body, e


def test_message_is_short(tmp_path, monkeypatch):
    msg = _morning(tmp_path, monkeypatch)
    assert len([l for l in msg.splitlines() if l.strip()]) <= 10


def test_schedule_is_sorted_by_time(tmp_path, monkeypatch):
    """Порядок брался из данных: во вторник Марта в 17:30 оказывалась выше
    Аркаши в 17:00, и смысл «времени слева» терялся."""
    n = _notifier(tmp_path, monkeypatch)
    text = n.get_kids_schedule('tuesday')
    times = [l.split()[0] for l in text.splitlines() if l.strip()]
    assert times == sorted(times)
