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
        # Проверяем переменные окружения
        logger.info("=== Инициализация Tracker Bot ===")
        
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        if not self.telegram_token:
            logger.error("ОШИБКА: TELEGRAM_TOKEN не найден в переменных окружения!")
            # Выводим доступные переменные для отладки
            logger.info("Доступные переменные окружения:")
            for key in sorted(os.environ.keys()):
                if 'TELEGRAM' in key or 'TOKEN' in key or 'BOT' in key:
                    logger.info(f"  {key}: {'*' * len(os.environ[key])}")
            raise ValueError("TELEGRAM_TOKEN не найден в переменных окружения!")

        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not self.chat_id:
            logger.error("ОШИБКА: TELEGRAM_CHAT_ID не найден!")
            raise ValueError("TELEGRAM_CHAT_ID не найден! Укажи ID канала (например -100...)")

        logger.info(f"✅ Токен бота загружен")
        logger.info(f"✅ Chat ID: {self.chat_id}")
        
        # Порт из окружения Railway или 8080 по умолчанию
        self.port = int(os.getenv('PORT', 8080))
        logger.info(f"✅ Порт: {self.port}")
        
        self.stats_file = "stats.json"
        self.last_update_id = 0
        self.message_state = {}
        
        # Для хранения статистики
        self.stats = self.load_stats()

    def load_stats(self):
        """Загружает статистику из файла"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки статистики: {e}")
        return {}

    def save_stats(self):
        """Сохраняет статистику в файл"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения статистики: {e}")

    def parse_tasks(self, message_text):
        """Парсит задачи из сообщения"""
        tasks = {'day': [], 'cant_do': [], 'evening': []}
        lines = message_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            clean_line = line.replace('<b>', '').replace('</b>', '')
            
            # Определяем секцию
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
            
            # Добавляем задачу если находимся в секции и строка начинается с •
            if current_section and line.startswith('•'):
                task_text = line[1:].strip()
                if task_text:
                    tasks[current_section].append(task_text)
        
        logger.info(f"Распарсено задач: день={len(tasks['day'])}, нельзя={len(tasks['cant_do'])}, вечер={len(tasks['evening'])}")
        return tasks

    def create_checklist_keyboard(self, tasks, completed):
        """Создает клавиатуру с чеклистом"""
        keyboard = []
        
        if tasks['day']:
            keyboard.append([{'text': '☀️ ДНЕВНЫЕ ЗАДАЧИ', 'callback_data': 'header'}])
            for idx, task in enumerate(tasks['day']):
                emoji = '✅' if idx in completed.get('day', []) else '⬜'
                short_task = task[:35] + '...' if len(task) > 35 else task
                keyboard.append([{'text': f'{emoji} {idx+1}. {short_task}', 'callback_data': f'toggle_day_{idx}'}])
        
        if tasks['cant_do']:
            keyboard.append([{'text': '⛔ НЕЛЬЗЯ ДЕЛАТЬ', 'callback_data': 'header'}])
            for idx, task in enumerate(tasks['cant_do']):
                emoji = '✅' if idx in completed.get('cant_do', []) else '⬜'
                short_task = task[:32] + '...' if len(task) > 32 else task
                keyboard.append([{'text': f'{emoji} {idx+1}. НЕ {short_task}', 'callback_data': f'toggle_cant_do_{idx}'}])
        
        if tasks['evening']:
            keyboard.append([{'text': '🌙 ВЕЧЕРНИЕ ЗАДАЧИ', 'callback_data': 'header'}])
            for idx, task in enumerate(tasks['evening']):
                emoji = '✅' if idx in completed.get('evening', []) else '⬜'
                short_task = task[:35] + '...' if len(task) > 35 else task
                keyboard.append([{'text': f'{emoji} {idx+1}. {short_task}', 'callback_data': f'toggle_evening_{idx}'}])
        
        keyboard.append([
            {'text': '💾 Сохранить', 'callback_data': 'save_progress'},
            {'text': '❌ Отмена', 'callback_data': 'cancel_update'}
        ])
        
        return {'inline_keyboard': keyboard}

    def format_checklist_message(self, tasks, completed):
        """Форматирует сообщение с прогресс-баром"""
        msg = "<b>📋 Отметь выполненные задачи:</b>\n\n"
        total_tasks = total_done = 0
        
        if tasks['day']:
            msg += "<b>☀️ ДНЕВНЫЕ:</b>\n"
            for idx, task in enumerate(tasks['day']):
                emoji = '✅' if idx in completed.get('day', []) else '⬜'
                msg += f"{emoji} {task}\n"
                total_tasks += 1
                if idx in completed.get('day', []): total_done += 1
            msg += "\n"
        
        if tasks['cant_do']:
            msg += "<b>⛔ НЕЛЬЗЯ ДЕЛАТЬ:</b>\n"
            for idx, task in enumerate(tasks['cant_do']):
                emoji = '✅' if idx in completed.get('cant_do', []) else '⬜'
                msg += f"{emoji} НЕ {task}\n"
                total_tasks += 1
                if idx in completed.get('cant_do', []): total_done += 1
            msg += "\n"
        
        if tasks['evening']:
            msg += "<b>🌙 ВЕЧЕРНИЕ:</b>\n"
            for idx, task in enumerate(tasks['evening']):
                emoji = '✅' if idx in completed.get('evening', []) else '⬜'
                msg += f"{emoji} {task}\n"
                total_tasks += 1
                if idx in completed.get('evening', []): total_done += 1
        
        # Прогресс-бар
        percentage = int((total_done / total_tasks * 100)) if total_tasks > 0 else 0
        bar = self.get_progress_bar(percentage)
        msg += f"\n<b>📊 Прогресс:</b> {bar} {total_done}/{total_tasks} ({percentage}%)\n"
        
        return msg

    def get_progress_bar(self, percentage, length=10):
        """Создает текстовый прогресс-бар"""
        filled = int((percentage / 100) * length)
        return '▓' * filled + '░' * (length - filled)

    async def send_telegram_message(self, text, parse_mode='HTML', reply_markup=None):
        """Отправляет сообщение в Telegram"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('result', {})
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка отправки сообщения: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            return None

    async def edit_message(self, message_id, text, parse_mode='HTML', reply_markup=None):
        """Редактирует сообщение в Telegram"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/editMessageText"
        
        payload = {
            'chat_id': self.chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка редактирования сообщения: {response.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            return False

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        """Отвечает на callback query"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/answerCallbackQuery"
        
        payload = {
            'callback_query_id': callback_query_id
        }
        
        if text:
            payload['text'] = text
        if show_alert:
            payload['show_alert'] = show_alert
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Ошибка ответа на callback: {e}")
            return False

    async def get_updates(self):
        """Получает обновления от Telegram"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
        params = {
            'timeout': 30,
            'offset': self.last_update_id + 1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('ok'):
                            return data.get('result', [])
                    return []
        except Exception as e:
            logger.error(f"Ошибка получения updates: {e}")
            return []

    async def process_callback(self, data, callback_query_id, message_id, message_text):
        """Обрабатывает callback-запросы"""
        logger.info(f"Обработка callback: {data}")
        
        if data == 'save_progress':
            # Сохраняем прогресс
            await self.answer_callback_query(callback_query_id, "Прогресс сохранён! ✅")
            
            # Обновляем сообщение
            new_text = "<b>✅ Прогресс сохранён!</b>\n\n" + message_text.replace("<b>📋 Отметь выполненные задачи:</b>", "<b>📋 Результаты:</b>")
            await self.edit_message(message_id, new_text, reply_markup=None)
            
        elif data == 'cancel_update':
            # Отменяем обновление
            await self.answer_callback_query(callback_query_id, "Обновление отменено")
            await self.edit_message(message_id, "❌ Обновление отменено", reply_markup=None)
            
        elif data.startswith('toggle_'):
            # Обработка переключения задачи
            parts = data.split('_')
            if len(parts) >= 3:
                section = parts[1]
                task_idx = int(parts[2])
                
                # Получаем текущее состояние
                state_key = f"{message_id}_{section}"
                if state_key not in self.message_state:
                    self.message_state[state_key] = []
                
                # Переключаем состояние
                if task_idx in self.message_state[state_key]:
                    self.message_state[state_key].remove(task_idx)
                else:
                    self.message_state[state_key].append(task_idx)
                
                # Парсим задачи из оригинального сообщения
                tasks = self.parse_tasks(message_text)
                
                # Создаем обновленное сообщение
                completed = {}
                for sec in ['day', 'cant_do', 'evening']:
                    state_key_sec = f"{message_id}_{sec}"
                    completed[sec] = self.message_state.get(state_key_sec, [])
                
                new_text = self.format_checklist_message(tasks, completed)
                new_keyboard = self.create_checklist_keyboard(tasks, completed)
                
                await self.edit_message(message_id, new_text, reply_markup=new_keyboard)
                await self.answer_callback_query(callback_query_id)
        
        elif data == 'header':
            # Заголовок - ничего не делаем
            await self.answer_callback_query(callback_query_id)

    async def check_schedule(self):
        """Проверяет расписание для автоматических действий"""
        now = datetime.now()
        
        # Проверяем, если это время для сводки (например, 21:00)
        if now.hour == 21 and now.minute == 0:
            # Отправляем итоги дня
            await self.send_daily_summary()
    
    async def send_daily_summary(self):
        """Отправляет итоги дня"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        if today in self.stats:
            day_stats = self.stats[today]
            total_tasks = day_stats.get('total', 0)
            completed_tasks = day_stats.get('completed', 0)
            
            if total_tasks > 0:
                percentage = int((completed_tasks / total_tasks) * 100)
                bar = self.get_progress_bar(percentage)
                
                summary = f"<b>📊 Итоги дня ({today})</b>\n\n"
                summary += f"Задач выполнено: {completed_tasks}/{total_tasks}\n"
                summary += f"Прогресс: {bar} {percentage}%\n\n"
                
                if percentage >= 80:
                    summary += "🎉 Отличная работа! Продолжайте в том же духе!"
                elif percentage >= 50:
                    summary += "👍 Хороший результат! Завтра будет ещё лучше!"
                else:
                    summary += "💪 Завтра новый день! Постарайтесь сделать больше!"
                
                await self.send_telegram_message(summary)
    
    async def run(self):
        """Основной цикл бота"""
        logger.info("🚀 Tracker Bot запущен!")
        
        # Запускаем HTTP-сервер для Railway
        app = web.Application()
        app.router.add_get('/', lambda _: web.Response(text="Tracker Bot работает ✅"))
        app.router.add_get('/health', lambda _: web.Response(text="OK"))
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        # Используем порт из переменной окружения (Railway предоставляет)
        port = int(os.getenv('PORT', 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"✅ HTTP-сервер запущен на порту {port}")
        
        last_schedule_check = datetime.now()
        
        # Основной цикл
        while True:
            try:
                now = datetime.now()
                
                # Проверяем расписание каждую минуту
                if (now - last_schedule_check).total_seconds() >= 60:
                    await self.check_schedule()
                    last_schedule_check = now
                
                # Получаем обновления от Telegram
                updates = await self.get_updates()
                
                for update in updates:
                    self.last_update_id = update.get('update_id', 0)
                    
                    # Обработка callback-запросов
                    if 'callback_query' in update:
                        cq = update['callback_query']
                        data = cq.get('data', '')
                        cq_id = cq.get('id', '')
                        msg = cq.get('message', {})
                        msg_id = msg.get('message_id', 0)
                        msg_text = msg.get('text', '')
                        
                        await self.process_callback(data, cq_id, msg_id, msg_text)
                    
                    # Обработка текстовых сообщений
                    elif 'message' in update:
                        message = update['message']
                        text = message.get('text', '')
                        chat_id = message.get('chat', {}).get('id')
                        
                        # Если боту прислали сообщение с задачами
                        if chat_id == int(self.chat_id) and '•' in text:
                            logger.info("Получено сообщение с задачами")
                            
                            # Парсим задачи
                            tasks = self.parse_tasks(text)
                            
                            # Создаем чеклист
                            checklist_text = self.format_checklist_message(tasks, {})
                            keyboard = self.create_checklist_keyboard(tasks, {})
                            
                            # Отправляем чеклист
                            await self.send_telegram_message(checklist_text, reply_markup=keyboard)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        bot = TaskTrackerBot()
        asyncio.run(bot.run())
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
