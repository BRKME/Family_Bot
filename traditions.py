# -*- coding: utf-8 -*-
"""Живые традиции: отметка «было / не было» и авто-архив.

До этого архивация была ручной — «Вечер воспоминаний» просто
закомментировали в `recurring_events`. Традиция, которую перестали
делать, продолжала напоминать о себе каждый месяц, пока кто-то не
доходил до кода.

Теперь в день события приходят две кнопки, а традиция, пропущенная три
раза подряд, уходит в архив сама.

Молчание считается пропуском. Иначе традиция, которую никогда не
отмечают, не заархивируется никогда — и вся механика теряет смысл. Цена
такого решения: случайная забывчивость может убить живую традицию,
поэтому на втором пропуске приходит предупреждение, а сообщение об
архиве несёт кнопку «Вернуть» — ошибка стоит одного тапа.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

ARCHIVE_AFTER = 3          # пропусков подряд до архива
WARN_AT = 2                # на каком пропуске предупреждать

DONE, SKIP = 'done', 'skip'


class TraditionLog:
    """Состояние традиций: отметки по датам и архив.

    Файл лежит рядом с ботом и коммитится в репозиторий, как stats.json:
    отдельная база ради двух десятков записей в год не нужна.
    """

    def __init__(self, path='traditions.json'):
        self.path = path
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError) as e:
            # Битый файл не должен ронять утреннее сообщение: молча
            # начинаем с чистого состояния, счётчики восстановятся сами.
            logger.error("traditions.json нечитаем (%s), стартуем с нуля", e)
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error("не сохранил traditions.json: %s", e)

    def _entry(self, key):
        return self.data.setdefault(key, {'marks': {}, 'archived': None})

    # ── Отметки ──────────────────────────────────────────────────────

    def record(self, key, day, status):
        """Отметить традицию за конкретную дату.

        Дата — ключ, а не время нажатия: одно и то же событие можно
        переотметить, если сначала нажал не ту кнопку.
        """
        entry = self._entry(key)
        entry['marks'][str(day)] = status
        if status == DONE:
            entry['archived'] = None
        elif self.misses_in_row(key) >= ARCHIVE_AFTER and not entry['archived']:
            entry['archived'] = str(day)
            logger.info("традиция %s ушла в архив", key)
        self._save()
        return entry

    def misses_in_row(self, key):
        """Сколько пропусков подряд считая с конца."""
        marks = self.data.get(key, {}).get('marks', {})
        n = 0
        for day in sorted(marks, reverse=True):
            if marks[day] == SKIP:
                n += 1
            else:
                break
        return n

    # ── Архив ────────────────────────────────────────────────────────

    def is_archived(self, key):
        return bool(self.data.get(key, {}).get('archived'))

    def archived_on(self, key):
        return self.data.get(key, {}).get('archived')

    def restore(self, key):
        """Вернуть традицию из архива с чистым счётчиком.

        Счётчик обнуляется, иначе следующий же пропуск отправил бы её
        обратно — возвращение не имело бы смысла.
        """
        entry = self._entry(key)
        entry['archived'] = None
        entry['marks'] = {}
        self._save()

    def filter_active(self, events):
        """Оставить только неархивированные традиции."""
        return {k: v for k, v in events.items() if not self.is_archived(k)}

    def archived_list(self):
        return {k: v['archived'] for k, v in self.data.items() if v.get('archived')}


# ── Тексты и кнопки ──────────────────────────────────────────────────────

def event_keyboard(key):
    """Кнопки в день события. «Не было» — обычный ответ, а не провал:
    пропуск даёт те же данные и нужен, чтобы понять, жива ли традиция."""
    return {'inline_keyboard': [[
        {'text': 'Было', 'callback_data': f'trad_done_{key}'},
        {'text': 'Не было', 'callback_data': f'trad_skip_{key}'},
    ]]}


def warning_line(log, key):
    """Предупреждение на предпоследнем пропуске — чтобы архивация не
    стала неожиданностью."""
    if log.misses_in_row(key) == WARN_AT and not log.is_archived(key):
        return ("⚠️ Традицию пропустили дважды подряд. "
                "Ещё раз — и она уйдёт в архив.")
    return ''


def archive_message(key, name):
    """Сообщение об архивации с кнопкой возврата."""
    msg = (f"📦 <b>Традиция ушла в архив</b>\n\n"
           f"{name} — три пропуска подряд.\n"
           f"Напоминания о ней приходить не будут. Если это ошибка, "
           f"верните её одной кнопкой.")
    kb = {'inline_keyboard': [[
        {'text': '↩️ Вернуть', 'callback_data': f'trad_restore_{key}'},
    ]]}
    return msg, kb


def digest_line(log, names):
    """Строка для месячного дайджеста: что в архиве и когда ушло.

    Без неё архив становится тихой ямой — через полгода не вспомнить,
    что вообще было в списке.
    """
    archived = log.archived_list()
    if not archived:
        return ''
    parts = [f"{names.get(k, k)} (с {d})" for k, d in sorted(archived.items())]
    return "📦 В архиве: " + ", ".join(parts)
