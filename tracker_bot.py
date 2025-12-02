#!/usr/bin/env python3
"""
Telegram бот для отслеживания выполнения задач - ФИНАЛЬНАЯ ВЕРСИЯ
Этапы 3 и 4: Прогресс-бары + Итоги дня/недели
"""

import asyncio
import aiohttp
from aiohttp import web
import json
import logging
from datetime import datetime, timedelta
import os
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TaskTrackerBot:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        if not self.telegram_token:
            raise ValueError("TELEGRAM_TOKEN не найден в переменных окружения!")

        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID не найден! Укажи ID канала (например -100...)")

        logger.info(f"Tracker Bot запущен | Чат ID: {self.chat_id}")

        self.stats_file = "stats.json"
        self.last_update_id = 0
        self.message_state = {}

    def parse_tasks(self, message_text):
        tasks = {'morning': [], 'day': [], 'cant_do': [], 'evening': []}
        lines = message_text.split('\n')
        current_section = None
        for line in lines:
            line = line.strip()
            clean_line = line.replace('<b>', '').replace('</b>', '')
            if 'Дневн' in clean_line and '☀️' in clean_line:
                current_section = 'day'
                continue
            elif any(x in clean_line for x in ['⛔', '⛔️', 'Нельзя делать']):
                current_section = 'cant_do'
                continue
            elif 'Вечерн' in clean_line and 'Вечерние задачи' in clean_line:
                current_section = 'evening'
                continue
            elif any(x in clean_line for x in ['Твоя миссия', 'Мудрость', 'Утренняя молитва', 'СЕГОДНЯ', 'События']):
                current_section = None
                continue
            if current_section and line.startswith('•'):
                task_text = line[1:].strip()
                if task_text:
                    tasks[current_section].append(task_text)
        logger.info(f"Распарсено задач: день={len(tasks['day'])}, нельзя={len(tasks['cant_do'])}, вечер={len(tasks['evening'])}")
        return tasks

    def create_checklist_keyboard(self, tasks, completed):
        keyboard = []
        if tasks['day']:
            keyboard.append([{'text': '☀️ ДНЕВНЫЕ ЗАДАЧИ', 'callback_data': 'header'}])
            for idx, task in enumerate(tasks['day']):
                emoji = '⭐' if idx in completed.get('day', []) else '☆'
                short_task = task[:35] + '...' if len(task) > 35 else task
                keyboard.append([{'text': f'{emoji} {idx+1}. {short_task}', 'callback_data': f'toggle_day_{idx}'}])
        if tasks['cant_do']:
            keyboard.append([{'text': '⛔ НЕЛЬЗЯ ДЕЛАТЬ', 'callback_data': 'header'}])
            for idx, task in enumerate(tasks['cant_do']):
                emoji = '⭐' if idx in completed.get('cant_do', []) else '☆'
                short_task = task[:32] + '...' if len(task) > 32 else task
                keyboard.append([{'text': f'{emoji} {idx+1}. НЕ {short_task}', 'callback_data': f'toggle_cant_do_{idx}'}])
        if tasks['evening']:
            keyboard.append([{'text': 'ВЕЧЕРНИЕ ЗАДАЧИ', 'callback_data': 'header'}])
            for idx, task in enumerate(tasks['evening']):
                emoji = '⭐' if idx in completed.get('evening', []) else '☆'
                short_task = task[:35] + '...' if len(task) > 35 else task
                keyboard.append([{'text': f'{emoji} {idx+1}. {short_task}', 'callback_data': f'toggle_evening_{idx}'}])
        keyboard.append([
            {'text': 'Сохранить', 'callback_data': 'save_progress'},
            {'text': 'Отмена', 'callback_data': 'cancel_update'}
        ])
        return {'inline_keyboard': keyboard}

    def format_checklist_message(self, tasks, completed):
        msg = "<b>Отметь выполненные задачи:</b>\n\n"
        total_tasks = total_done = 0
        if tasks['day']:
            msg += "<b>ДНЕВНЫЕ:</b>\n"
            for idx, task in enumerate(tasks['day']):
                emoji = '⭐' if idx in completed.get('day', []) else '☆'
                msg += f"{emoji} {task}\n"
                total_tasks += 1
                if idx in completed.get('day', []): total_done += 1
            msg += "\n"
        if tasks['cant_do']:
            msg += "<b>НЕЛЬЗЯ ДЕЛАТЬ:</b>\n"
            for idx, task in enumerate(tasks['cant_do']):
                emoji = '⭐' if idx in completed.get('cant_do', []) else '☆'
                msg += f"{emoji} НЕ {task}\n"
                total_tasks += 1
                if idx in completed.get('cant_do', []): total_done += 1
            msg += "\n"
        if tasks['evening']:
            msg += "<b>ВЕЧЕРНИЕ:</b>\n"
            for idx, task in enumerate(tasks['evening']):
                emoji = '⭐' if idx in completed.get('evening', []) else '☆'
                msg += f"{emoji} {task}\n"
                total_tasks += 1
                if idx in completed.get('evening', []): total_done += 1
        percentage = int((total_done / total_tasks * 100)) if total_tasks > 0 else 0
        bar = self.get_progress_bar(percentage)
        msg += f"<b>Прогресс:</b> {bar} {total_done}/{total_tasks} ({percentage}%)\n"
        return msg

    def get_progress_bar(self, percentage, length=8):
        filled = int((percentage / 100) * length)
        return '▓' * filled + '░' * (length - filled)

    async def run(self):
        logger.info("Tracker Bot запущен!")

        app = web.Application()
        app.router.add_get('/', lambda _: web.Response(text="OK"))
        app.router.add_get('/health', lambda _: web.Response(text="OK"))

        # ЖЁСТКО 443 — Railway не имеет права это перебить
        port = 443
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"HTTP-сервер запущен на порту {port} (принудительно 443)")

        last_schedule_check = datetime.now()

        while True:
            try:
                now = datetime.now()
                if (now - last_schedule_check).total_seconds() >= 60:
                    await self.check_schedule()
                    last_schedule_check = now

                updates = await self.get_updates()
                for update in updates:
                    self.last_update_id = update.get('update_id', 0)
                    if 'callback_query' in update:
                        cq = update['callback_query']
                        data = cq.get('data', '')
                        cq_id = cq.get('id', '')
                        msg = cq.get('message', {})
                        msg_id = msg.get('message_id', 0)
                        msg_text = msg.get('text', '')
                        await self.process_callback(data, cq_id, msg_id, msg_text)

                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Ошибка в цикле: {e}")
                await asyncio.sleep(5)

    # ← ОСТАЛЬНЫЕ МЕТОДЫ (send_telegram_message, edit_message, process_callback и т.д.)
    # копируй их из твоего старого файла — они все уже правильные

if __name__ == "__main__":
    bot = TaskTrackerBot()
    asyncio.run(bot.run())
