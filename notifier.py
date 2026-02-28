#!/usr/bin/env python3
import asyncio
import aiohttp
from datetime import datetime
from calendar import monthcalendar
import logging
import random
import sys
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FamilyScheduleBot:
    DAY_NAMES_MAP = {
        'monday': 'понедельник',
        'tuesday': 'вторник', 
        'wednesday': 'среда',
        'thursday': 'четверг',
        'friday': 'пятница',
        'saturday': 'суббота',
        'sunday': 'воскресенье'
    }
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_TOKEN', '')
        if not self.telegram_token:
            raise ValueError("❌ TELEGRAM_TOKEN не найден в переменных окружения!")
        
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        if not self.chat_id:
            raise ValueError("❌ TELEGRAM_CHAT_ID не найден в переменных окружения!")
        
        self.ss_url = "https://brkme.github.io/OK_My_Day_Shedule/ss.html"
        
        self.wisdoms = [
            # Про семью и детей
            "Семья — это не важная вещь. Это всё. — Майкл Джей Фокс",
            "В семейной жизни главное — терпение. Любовь продолжаться долго не может. — Антон Чехов",
            "Счастлив тот, кто счастлив у себя дома. — Лев Толстой",
            "Семья — это компас, который ведёт нас. Она вдохновляет достигать высот и утешает, когда мы падаем. — Брэд Генри",
            "Дети — это живые послания, которые мы отправляем в будущее. — Джон Кеннеди",
            "Лучшее наследство, которое можно дать детям — это несколько минут вашего времени каждый день. — Баттиста",
            "Семья — это место, где жизнь начинается, а любовь никогда не заканчивается. — Неизвестный автор",
            "Дом там, где тебя любят. — Тибетская мудрость",
            "Нет ничего важнее семьи и любви. — Джон Вуден",
            "Любовь к семье — самое важное богатство в жизни. — Эррол Флинн",
            "Семья — не просто важная вещь, это всё. — Майкл Джей Фокс",
            "Воспитание детей — это не наполнение ведра, а зажигание огня. — Уильям Батлер Йейтс",
            "Дети больше всего нуждаются в вашем присутствии, а не в ваших подарках. — Джесси Джексон",
            "Самое ценное, что мы можем дать нашим детям — это корни и крылья. — Гёте",
            "Семья — это не те люди, которые с тобой по крови. Это те, кто с тобой по жизни. — Неизвестный автор",
            "Счастье — это когда тебя понимают, большое счастье — когда тебя любят, настоящее счастье — когда любишь ты. — Конфуций",
            "Лучший способ сделать детей хорошими — сделать их счастливыми. — Оскар Уайльд",
            "Дети — наше зеркало. В них отражается всё, что мы делаем. — Неизвестный автор",
            "Любовь матери — это мир. Её не нужно завоёвывать, её не нужно заслуживать. — Эрих Фромм",
            "Семья — это тихая гавань в бурном море жизни. — Неизвестный автор",
            "Один отец значит больше, чем сто учителей. — Джордж Герберт",
            "Нет места лучше дома. — Лаймен Фрэнк Баум",
            "Дом — это не место, а чувство. — Сесилия Ахерн",
            "Семья начинается с детей. — Александр Герцен",
            "Самый большой подарок, который вы можете сделать своим детям — быть счастливыми. — Неизвестный автор",
            "Любовь и уважение — два столпа семьи. — Конфуций",
            "Когда вы смотрите на свою жизнь, самые счастливые моменты — это семейные. — Джойс Бразерс",
            "Семья — это место, где вас любят больше всего и ведут себя хуже всего. — Марджори Пэй Хинкли",
            "Дети — это якоря, которые удерживают мать в жизни. — Софокл",
            "Благословение семьи — это когда её члены уважают друг друга. — Эзоп"
        ]
        
        self.recurring_events = {
            'tarelka': {
                'name': 'Семейная традиция - Путешествие на тарелке', 
                'file': 'tarelka.txt', 
                'rule': 'last_saturday'
            },
            'chronos': {
                'name': 'Семейная традиция - Вечер воспоминаний. Хранители времени', 
                'file': 'chronos.txt', 
                'rule': 'third_saturday'
            },
            'new': {
                'name': 'Семейная традиция - День нового', 
                'file': 'new.txt', 
                'rule': 'second_saturday'
            }
        }
        
        self.birthdays = {
            'дедушка Коля (день памяти)': (1, 1),
            'Илюша Бензионович': (3, 1),
            'Света Пяткова': (8, 1),
            'бабушка Таня (день памяти)': (13, 1),
            'Ира Разведченко (крестная Марты)': (14, 1),
            'прабабушка Зоя': (14, 1),
            'Витя': (23, 1),
            'Сережа Добровенко (крестный Марты)': (25, 1),
            'Годовщина Ксюши и Вити': (4, 2),
            'Мама': (14, 2),
            'Милана Зборовская': (26, 2),
            'Макар Ельцов': (4, 3),
            'Марина Зборовская': (7, 3),
            'Катя (сестра папы)': (18, 3),
            'Юра Добровенко': (28, 3),
            'тетя Галя': (31, 3),
            'Годовщина Кати и Олега': (31, 3),
            'дедушка Эдик (день памяти)': (1, 4),
            'бабушка Галя': (2, 4),
            'Варя': (6, 4),
            'Годовщина Ени и Ромы': (8, 4),
            'Саша': (9, 4),
            'Ярик Артеменко': (22, 4),
            'Зак': (1, 5),
            'Слава (брат папы)': (6, 5),
            'прабабушка Зоя (день памяти)': (7, 5),
            'дядя Миша': (9, 5),
            'Годовщина Иры и Жени': (10, 5),
            'Годовщина свадьбы (венчание)': (11, 5),
            'тетя Лариса': (16, 5),
            'Годовщина свадьбы (ЗАГС)': (21, 5),
            'бабушка Таня': (22, 5),
            'Женя (сестра папы)': (27, 5),
            'Разманыч': (3, 6),
            'дядя Рома': (7, 6),
            'Яна': (10, 6),
            'Антон': (11, 6),
            'Лилуся': (16, 6),
            'Снег': (16, 6),
            'Леша Зборовский': (21, 6),
            'Оля Пяткова': (22, 6),
            'Годовщина свадьбы Иры и Жени': (24, 6),
            'Кирюша': (29, 6),
            'Таня Пяткова': (2, 7),
            'Вова Разведченко': (27, 7),
            'Кирилл Бензионович': (28, 7),
            'Женя Артеменко': (30, 7),
            'дедушка Эдик': (1, 8),
            'Мироша Бензионович': (3, 8),
            'Мартюся': (10, 8),
            'Оля Зеновская': (10, 8),
            'Надя': (11, 8),
            'Юля': (20, 8),
            'Годовщина свадьбы Оли Пятковой': (7, 9),
            'бабушка Света': (14, 9),
            'Даня': (2, 10),
            'Годовщина свадьбы Гали и Сережи': (4, 10),
            'Галя Добровенко (крестная Аркаши)': (6, 10),
            'Малюсик': (15, 10),
            'Савва Зеновский': (30, 10),
            'Лева': (15, 11),
            'Ваня': (18, 11),
            'Рома Зборовский': (19, 11),
            'Олег': (21, 11),
            'Сережа Зайцев': (25, 11),
            'Костя (брат папы)': (26, 11),
            'Джонни': (2, 12),
            'Папа': (4, 12),
            'Галя (сестра папы)': (6, 12),
            'тетя Еня': (10, 12),
            'Пипс': (15, 12),
            'дедушка Коля': (24, 12),
            'тетя Галя (24 декабря)': (24, 12),
            'Дима Ельцов': (25, 12),
        }
        
        self.kids_schedule = {
            'понедельник': [
                {'child': '👧 Марта', 'activity': '🇬🇧 Английский', 'time': '16:00-17:00'},
                {'child': '👦 Аркаша', 'activity': '📐 Математика', 'time': '19:00-20:00'}
            ],
            'вторник': [
                {'child': '👧 Марта', 'activity': '💃 Танцы', 'time': '17:30-19:00'},
                {'child': '👦 Аркаша', 'activity': '⚽ Футбол', 'time': '17:00-18:00'}
            ],
            'среда': [
                {'child': '👧 Марта', 'activity': '🤺 Фехтование', 'time': '15:00-16:30'},
                {'child': '👦 Аркаша', 'activity': '🤺 Фехтование', 'time': '16:00-18:00'},
                {'child': '👧 Марта', 'activity': '🇬🇧 Английский', 'time': '17:00-18:00'}
            ],
            'четверг': [
                {'child': '👧 Марта', 'activity': '💃 Танцы', 'time': '17:30-19:00'},
                {'child': '👦 Аркаша', 'activity': '⚽ Футбол', 'time': '17:00-18:00'}
            ],
            'пятница': [
                {'child': '👧 Марта', 'activity': '🤺 Фехтование', 'time': '15:00-16:30'},
                {'child': '👦 Аркаша', 'activity': '🤺 Фехтование', 'time': '16:00-18:00'},
                {'child': '👦 Аркаша', 'activity': '📐 Математика', 'time': '19:00-20:00'}
            ],
            'суббота': [
                {'child': '👧 Марта', 'activity': '🤺 Фехтование', 'time': '15:00-17:00'}
            ],
            'воскресенье': [
                {'child': '👧 Марта', 'activity': '🤺 Фехтование', 'time': '12:00-14:00'},
                {'child': '👦 Аркаша', 'activity': '🤺 Фехтование', 'time': '14:00-16:00'}
            ]
        }
        
        self.dishes_schedule = {
            'понедельник': '👧 Марта моет посуду',
            'вторник': '👦 Аркаша моет посуду',
            'среда': '👧 Марта моет посуду',
            'четверг': '👦 Аркаша моет посуду',
            'пятница': '👧 Марта моет посуду',
            'суббота': '👨‍👩‍👧‍👦 Родители моют посуду',
            'воскресенье': '👨‍👩‍👧‍👦 Родители моют посуду'
        }

    def get_random_wisdom(self):
        return random.choice(self.wisdoms)

    def get_today_schedule(self):
        now = datetime.now()
        months = {
            1: 'Января', 2: 'Февраля', 3: 'Марта', 4: 'Апреля',
            5: 'Мая', 6: 'Июня', 7: 'Июля', 8: 'Августа',
            9: 'Сентября', 10: 'Октября', 11: 'Ноября', 12: 'Декабря'
        }
        day = now.day
        month_name = months[now.month]
        date_str = f"{day} {month_name}"
        day_of_week = now.strftime("%A").lower()
        return date_str, day_of_week

    async def get_weather_forecast(self):
        try:
            url = "https://api.open-meteo.com/v1/forecast?latitude=59.9311&longitude=30.3609&current_weather=true&temperature_unit=celsius&timezone=Europe/Moscow"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        current = data.get('current_weather', {})
                        
                        temp = current.get('temperature', 'N/A')
                        windspeed = current.get('windspeed', 'N/A')
                        
                        weather_codes = {
                            0: 'Ясно', 1: 'Малооблачно', 2: 'Переменная облачность', 3: 'Облачно',
                            45: 'Туман', 48: 'Изморозь',
                            51: 'Морось', 53: 'Морось', 55: 'Сильная морось',
                            61: 'Слабый дождь', 63: 'Дождь', 65: 'Сильный дождь',
                            71: 'Слабый снег', 73: 'Снег', 75: 'Сильный снег',
                            95: 'Гроза'
                        }
                        
                        weather_code = current.get('weathercode', 0)
                        condition = weather_codes.get(weather_code, 'Неизвестно')
                        
                        logger.info(f"✅ Погода получена: {temp}°C, {condition}")
                        
                        return (
                            f"🌤️ <b>Погода в Санкт-Петербурге:</b>\n"
                            f"🌡️ {temp}°C • {condition}\n"
                            f"💨 Ветер: {windspeed} км/ч\n"
                        )
                    else:
                        logger.warning(f"⚠️ Open-Meteo вернул статус {response.status}")
                        return ""
            
        except Exception as e:
            logger.error(f"❌ Ошибка погоды: {e}")
            return ""

    def get_last_day_of_month(self, year, month, target_weekday):
        calendar = monthcalendar(year, month)
        for week in reversed(calendar):
            day = week[target_weekday]
            if day != 0:
                return day
        return None

    def get_event_date_by_rule(self, rule, year, month):
        if rule == 'last_saturday':
            day = self.get_last_day_of_month(year, month, 5)
            return (year, month, day) if day else None
        elif rule == 'third_saturday':
            calendar = monthcalendar(year, month)
            saturdays = [week[5] for week in calendar if week[5] != 0]
            if len(saturdays) >= 3:
                return (year, month, saturdays[2])
        elif rule == 'second_saturday':
            calendar = monthcalendar(year, month)
            saturdays = [week[5] for week in calendar if week[5] != 0]
            if len(saturdays) >= 2:
                return (year, month, saturdays[1])
        return None

    def check_recurring_events(self):
        from datetime import date as dt
        today = datetime.now()
        year, month, day = today.year, today.month, today.day
        reminders = []
        
        for event_key, event in self.recurring_events.items():
            event_date = self.get_event_date_by_rule(event['rule'], year, month)
            if not event_date:
                continue
                
            event_year, event_month, event_day = event_date
            event_dt = dt(event_year, event_month, event_day)
            today_dt = dt(year, month, day)
            days_until = (event_dt - today_dt).days
            
            if days_until == 7:
                reminders.append({'key': event_key, 'event': event, 'type': 'week_before'})
            elif days_until == 3:
                reminders.append({'key': event_key, 'event': event, 'type': 'three_days_before'})
            elif days_until == 0:
                reminders.append({'key': event_key, 'event': event, 'type': 'event_day'})
        
        return reminders

    def check_upcoming_birthdays(self):
        from datetime import timedelta
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        upcoming_birthdays = []
        
        for name, (day, month) in self.birthdays.items():
            if tomorrow.day == day and tomorrow.month == month:
                upcoming_birthdays.append(name)
        
        return upcoming_birthdays

    async def fetch_event_file(self, filename):
        try:
            url = f"https://raw.githubusercontent.com/BRKME/Day/main/{filename}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Файл {filename} загружен")
                        return content
                    else:
                        logger.error(f"❌ Ошибка загрузки {filename}")
                        return None
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки {filename}: {e}")
            return None

    def get_kids_schedule(self, day_of_week):
        logger.info(f"📅 Запрос расписания детей для дня: {day_of_week}")
        
        if not day_of_week:
            logger.warning("⚠️ day_of_week is None or empty")
            return None
        
        day_ru = self.DAY_NAMES_MAP.get(day_of_week)
        if not day_ru:
            logger.warning(f"⚠️ День '{day_of_week}' не найден в маппинге")
            return None
        
        if day_ru not in self.kids_schedule:
            logger.warning(f"⚠️ Расписание для дня '{day_ru}' отсутствует")
            return None
        
        activities = self.kids_schedule[day_ru]
        
        if not activities:
            logger.info(f"ℹ️ Нет занятий на {day_ru}")
            return None
        
        logger.info(f"✅ Найдено {len(activities)} занятий для {day_ru}")
        
        schedule_text = "<b>👨‍👩‍👧‍👦 Занятия детей сегодня:</b>\n"
        successful_items = 0
        
        for idx, item in enumerate(activities):
            try:
                child = item['child']
                activity = item['activity']
                time = item['time']
                
                schedule_text += f"• {child} — {activity} <i>({time})</i>\n"
                successful_items += 1
                logger.debug(f"  ✓ Занятие {idx+1}: {child} - {activity} ({time})")
                
            except KeyError as e:
                logger.error(f"❌ Ошибка в данных расписания (элемент {idx+1}): отсутствует ключ {e}")
                continue
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка при обработке элемента {idx+1}: {e}")
                continue
        
        if successful_items == 0:
            logger.warning(f"⚠️ Не удалось обработать ни одного занятия для {day_ru}")
            return None
        
        logger.info(f"✅ Расписание сформировано: {successful_items}/{len(activities)} занятий")
        return schedule_text

    def get_dishes_reminder(self, day_of_week):
        day_ru = self.DAY_NAMES_MAP.get(day_of_week)
        if not day_ru:
            return None
        
        return self.dishes_schedule.get(day_ru)

    async def format_morning_message(self, date_str, day_of_week):
        day_names = {
            'monday': 'Понедельник', 
            'tuesday': 'Вторник', 
            'wednesday': 'Среда', 
            'thursday': 'Четверг', 
            'friday': 'Пятница', 
            'saturday': 'Суббота', 
            'sunday': 'Воскресенье'
        }
        day_ru = day_names.get(day_of_week, day_of_week)
        wisdom = self.get_random_wisdom()
        
        content = f"🌅 <b>Доброе Утро ! Сегодня «{day_ru}» {date_str}</b>\n\n"
        
        weather = await self.get_weather_forecast()
        if weather:
            content += weather + "\n"
        
        content += f"💭 {wisdom}\n\n"
        
        kids_schedule_text = self.get_kids_schedule(day_of_week)
        if kids_schedule_text:
            content += f"{kids_schedule_text}\n"
        
        dishes_reminder = self.get_dishes_reminder(day_of_week)
        if dishes_reminder:
            content += f"<b>🍽️ Посуда:</b>\n• {dishes_reminder}\n\n"
        
        if day_of_week == 'friday':
            content += "<b>🧹 Сегодня пятница:</b>\n• Зачёт по чистоте комнаты <i>(20 min)</i>\n\n"
        
        reminders = self.check_recurring_events()
        if reminders:
            for reminder in reminders:
                event = reminder['event']
                event_content = await self.fetch_event_file(event['file'])
                
                if reminder['type'] == 'week_before':
                    content += f"\n🔔 <b>НАПОМИНАНИЕ (За 7 дней):</b>\n<b>{event['name']}</b>\n"
                    if event_content:
                        content += f"{event_content}\n"
                elif reminder['type'] == 'three_days_before':
                    content += f"\n🔔 <b>НАПОМИНАНИЕ (За 3 дня):</b>\n<b>{event['name']}</b>\n"
                    if event_content:
                        content += f"{event_content}\n"
                elif reminder['type'] == 'event_day':
                    content += f"\n🎉 <b>СЕГОДНЯ:</b>\n<b>{event['name']}</b>\n"
                    if event_content:
                        content += f"{event_content}\n"
        
        upcoming_birthdays = self.check_upcoming_birthdays()
        if upcoming_birthdays:
            content += "\n🎂 <b>ЗАВТРА ДЕНЬ РОЖДЕНИЯ:</b>\n"
            for name in upcoming_birthdays:
                content += f"🎈 {name}\n"
        
        return content

    async def send_telegram_message(self, message, send_ss=False):
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id, 
                'text': message, 
                'parse_mode': 'HTML',
                'disable_web_page_preview': False
            }
            
            logger.info("📤 Отправка сообщения в Telegram...")
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    response_data = await response.json()
                    logger.info(f"📊 Telegram API response: {response_data}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка API {response.status}: {error_text}")
                        return False
                    
                    if not response_data.get('ok', False):
                        logger.error(f"❌ Telegram API вернул ok=false: {response_data}")
                        return False
            
            if send_ss:
                family_msg = f"<b>📋 Семейный совет:</b>\n\n🔗 <a href='{self.ss_url}'>Открыть структуру Семейного Совета</a>"
                payload_council = {
                    'chat_id': self.chat_id, 
                    'text': family_msg, 
                    'parse_mode': 'HTML', 
                    'disable_web_page_preview': False
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload_council, timeout=10) as response:
                        response_data = await response.json()
                        logger.info(f"📊 Telegram API response (семейный совет): {response_data}")
                        
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"❌ Ошибка отправки семейного совета {response.status}: {error_text}")
                            return False
                        
                        if not response_data.get('ok', False):
                            logger.error(f"❌ Telegram API вернул ok=false для семейного совета: {response_data}")
                            return False
                        
                        logger.info("✅ Сообщения отправлены!")
                        return True
            else:
                logger.info("✅ Сообщение отправлено!")
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False

    async def send_morning_message(self):
        date_str, day_of_week = self.get_today_schedule()
        message = await self.format_morning_message(date_str, day_of_week)
        
        send_ss = (day_of_week == 'sunday')
        
        return await self.send_telegram_message(message, send_ss=send_ss)

    async def send_gratitude_reminder(self):
        return await self.send_telegram_message("🌷Самое время получить семейную благодарность")

    async def send_games_reminder(self):
        return await self.send_telegram_message("🏠Самое время поиграть в семейные игры и повеселиться")

async def main():
    logger.info(f"🚀 Запуск семейного бота")
    bot = FamilyScheduleBot()
    
    mode = sys.argv[1] if len(sys.argv) > 1 else 'morning'
    
    if mode == 'gratitude':
        success = await bot.send_gratitude_reminder()
    elif mode == 'games':
        success = await bot.send_games_reminder()
    else:
        success = await bot.send_morning_message()
    
    if success:
        logger.info("🎉 Успешно завершено!")
    else:
        logger.error("💥 Ошибка при отправке")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
