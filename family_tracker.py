#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Трекер семейных традиций.

Долгоживущий процесс на VPS. Слушает нажатия кнопок «Было / Не было» под
сообщениями семейного бота и пишет ответы в traditions.json.

Зачем отдельный процесс. notifier.py запускается в GitHub Actions по
крону: отправил сообщение и умер. Принять нажатие ему некому, а файловая
система Actions одноразовая — traditions.json там не переживает запуск.
Поэтому состояние живёт на VPS и синхронизируется в репозиторий через
GitHub API, ровно как program.json у личного бота.

Запуск:
    TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=... GITHUB_TOKEN=... \
        python3 family_tracker.py
"""
import asyncio
import base64
import json
import logging
import os
from datetime import datetime

import aiohttp

from traditions import TraditionLog, event_keyboard, threshold_for

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GITHUB_REPO = "BRKME/Family_Bot"
POLL_TIMEOUT = 30


class FamilyTracker:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_TOKEN', '')
        if not self.telegram_token:
            raise ValueError("❌ TELEGRAM_TOKEN не найден")
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.github_token = os.getenv('GITHUB_TOKEN', '')
        self.github_repo = GITHUB_REPO

        self.trad_log = TraditionLog()
        self.offset = 0
        self.session = None

    # ── Нажатия ──────────────────────────────────────────────────────

    async def handle_callback(self, data, query_id, message_id):
        """Обработать нажатие. Чужие и битые callback'и игнорируем молча:
        в чате могут жить кнопки других ботов, и падать из-за них нельзя."""
        if not data.startswith('trad_'):
            return False
        parts = data[5:].split('_', 1)
        if len(parts) != 2 or not parts[1]:
            logger.warning("непонятный callback: %s", data)
            return False

        action, key = parts
        today = datetime.now().strftime("%Y-%m-%d")

        if action == 'restore':
            self.trad_log.restore(key)
            note = "Вернул ↩️"
        elif action in ('done', 'skip'):
            self.trad_log.record(key, today,
                                 'done' if action == 'done' else 'skip')
            if action == 'done':
                note = "Отметил ✅"
            else:
                left = threshold_for(key) - self.trad_log.misses_in_row(key)
                note = ("Ок, записал" if left > 1
                        else "Записал. Ещё раз — и уйдёт в архив")
        else:
            return False

        await self.sync_to_github()
        await self.answer_callback(query_id, note)
        if action != 'restore':
            await self.edit_keyboard(message_id, self.marked_keyboard(key))
        return True

    def marked_keyboard(self, key):
        """Клавиатура с видимой отметкой: без неё непонятно, засчиталось
        нажатие или нет."""
        status = self.trad_log.data.get(key, {}).get('marks', {}).get(
            datetime.now().strftime("%Y-%m-%d"))
        kb = event_keyboard(key)
        for button in kb['inline_keyboard'][0]:
            if button['callback_data'].endswith(f'done_{key}') and status == 'done':
                button['text'] = '✅ Было'
            elif button['callback_data'].endswith(f'skip_{key}') and status == 'skip':
                button['text'] = '👉 Не было'
        return kb

    # ── Telegram ─────────────────────────────────────────────────────

    async def process_updates(self, updates):
        for update in updates:
            self.offset = max(self.offset, update.get('update_id', 0) + 1)
            query = update.get('callback_query')
            if not query:
                continue
            try:
                await self.handle_callback(
                    query.get('data', ''), query.get('id'),
                    (query.get('message') or {}).get('message_id'))
            except Exception as e:
                logger.error("ошибка обработки нажатия: %s", e)

    async def answer_callback(self, query_id, text=None):
        """Ответ обязателен: иначе Telegram крутит часики на кнопке."""
        url = f"https://api.telegram.org/bot{self.telegram_token}/answerCallbackQuery"
        payload = {'callback_query_id': query_id}
        if text:
            payload['text'] = text
        try:
            async with self.session.post(url, json=payload, timeout=10):
                pass
        except Exception as e:
            logger.error("не ответил на callback: %s", e)

    async def edit_keyboard(self, message_id, keyboard):
        """Меняем только клавиатуру: editMessageText переписал бы текст
        сообщения, а он у семейного бота содержит расписание детей."""
        if not message_id:
            return
        url = f"https://api.telegram.org/bot{self.telegram_token}/editMessageReplyMarkup"
        payload = {'chat_id': self.chat_id, 'message_id': message_id,
                   'reply_markup': json.dumps(keyboard)}
        try:
            async with self.session.post(url, json=payload, timeout=10):
                pass
        except Exception as e:
            logger.error("не обновил клавиатуру: %s", e)

    # ── Синхронизация ────────────────────────────────────────────────

    async def sync_to_github(self):
        """Состояние в репозиторий: VPS может пересоздаться, а Actions
        читает traditions.json именно оттуда."""
        if not self.github_token:
            logger.warning("⚠️ GITHUB_TOKEN не задан — состояние только локально")
            return False
        url = (f"https://api.github.com/repos/{self.github_repo}"
               f"/contents/traditions.json")
        headers = {"Authorization": f"token {self.github_token}",
                   "Accept": "application/vnd.github.v3+json"}
        try:
            sha = None
            async with self.session.get(url, headers=headers, timeout=10) as r:
                if r.status == 200:
                    sha = (await r.json()).get('sha')
                elif r.status in (401, 403):
                    logger.error("GitHub отказал: %s — проверь токен", r.status)
                    return False
            content = json.dumps(self.trad_log.data, ensure_ascii=False, indent=2)
            payload = {
                "message": f"traditions: {datetime.now():%Y-%m-%d %H:%M}",
                "content": base64.b64encode(content.encode()).decode(),
                "branch": "main",
            }
            if sha:
                payload['sha'] = sha
            async with self.session.put(url, headers=headers, json=payload,
                                        timeout=10) as r:
                return r.status in (200, 201)
        except Exception as e:
            logger.error("синк не удался: %s", e)
            return False

    # ── Цикл ─────────────────────────────────────────────────────────

    async def run(self):
        self.session = aiohttp.ClientSession()
        logger.info("🏠 Трекер семейных традиций запущен")
        url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
        try:
            while True:
                try:
                    params = {'timeout': POLL_TIMEOUT, 'offset': self.offset,
                              'allowed_updates': json.dumps(['callback_query'])}
                    async with self.session.get(
                            url, params=params,
                            timeout=POLL_TIMEOUT + 10) as response:
                        data = await response.json()
                    await self.process_updates(data.get('result', []))
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error("ошибка опроса: %s", e)
                    await asyncio.sleep(5)
        finally:
            await self.session.close()


if __name__ == '__main__':
    asyncio.run(FamilyTracker().run())
