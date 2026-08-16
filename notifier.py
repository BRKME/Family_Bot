#!/usr/bin/env python3
import asyncio
import aiohttp

from traditions import (TraditionLog, archive_message, digest_line,
                         event_keyboard, warning_line)
import json
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
        
        self.ss_url = "https://brkme.github.io/My_Day_Shedule/ss.html"
        self.new_url = "https://brkme.github.io/My_Day_Shedule/new.html"
        self.chronos_url = "https://brkme.github.io/My_Day_Shedule/chronos.html"
        
        # Цитаты убраны из утреннего сообщения 16.08.2026: корпус был
        # о воспитании и обращён к родителям, а сообщение в общем
        # чате читают все, включая детей — для них это текст о себе
        # в третьем лице. quotes.json оставлен на случай возврата.
        
        # Живые традиции: отметки и авто-архив (см. traditions.py).
        # Семейный совет — такая же традиция, у него ключ 'council'.
        self.trad_log = TraditionLog()

        self.recurring_events = {
            'tarelka': {
                'name': 'Семейная традиция - Путешествие на тарелке', 
                'file': 'tarelka.txt', 
                'rule': 'last_saturday'
            },
            # Возвращена 16.08.2026: архивация теперь автоматическая, и
            # если традиция снова не пойдёт, механика уберёт её сама.
            'chronos': {
                'name': 'Семейная традиция - Вечер воспоминаний',
                'url': self.chronos_url,
                'short_text': 'Хранители времени — смотрим фото и рассказываем историю семьи',
                'rule': 'third_saturday'
            },
            'new': {
                'name': 'Семейная традиция - День нового', 
                'url': self.new_url,
                'short_text': 'Выходим из зоны комфорта всей семьей!',
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
            'Илья Зеновский': (28, 4),
            'Зак': (1, 5),
            'Слава (брат папы)': (6, 5),
            'прабабушка Зоя (день памяти)': (7, 5),
            'дядя Миша': (9, 5),
            'Годовщина Иры и Жени': (10, 5),
            'Годовщина свадьбы (венчание)': (11, 5),
            'тетя Лариса': (16, 5),
            'Годовщина свадьбы (ЗАГС)': (21, 5),
            'бабушка Таня': (21, 5),
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
            'Ксюша Витина': (21, 9),
            'Даня': (2, 10),
            'Годовщина свадьбы Гали и Сережи': (4, 10),
            'Галя Добровенко (крестная Аркаши)': (6, 10),
            'Малюсик': (15, 10),
            'Аркаша': (16, 10),
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
                {'child': 'Марта', 'activity': 'Английский', 'time': '16:00-17:00'},
                {'child': 'Аркаша', 'activity': 'Математика', 'time': '19:00-20:00'}
            ],
            'вторник': [
                {'child': 'Марта', 'activity': 'Танцы', 'time': '17:30-19:00'},
                {'child': 'Аркаша', 'activity': 'Футбол', 'time': '17:00-18:00'}
            ],
            'среда': [
                {'child': 'Марта', 'activity': 'Фехтование', 'time': '15:00-16:30'},
                {'child': 'Аркаша', 'activity': 'Фехтование', 'time': '16:00-18:00'},
                {'child': 'Марта', 'activity': 'Английский', 'time': '17:00-18:00'}
            ],
            'четверг': [
                {'child': 'Марта', 'activity': 'Танцы', 'time': '17:30-19:00'},
                {'child': 'Аркаша', 'activity': 'Футбол', 'time': '17:00-18:00'}
            ],
            'пятница': [
                {'child': 'Марта', 'activity': 'Фехтование', 'time': '15:00-16:30'},
                {'child': 'Аркаша', 'activity': 'Фехтование', 'time': '16:00-18:00'},
                {'child': 'Аркаша', 'activity': 'Математика', 'time': '19:00-20:00'}
            ],
            'суббота': [
                {'child': 'Марта', 'activity': 'Фехтование', 'time': '15:00-17:00'}
            ],
            'воскресенье': [
                {'child': 'Марта', 'activity': 'Фехтование', 'time': '12:00-14:00'},
                {'child': 'Аркаша', 'activity': 'Фехтование', 'time': '14:00-16:00'}
            ]
        }
        
        self.dishes_schedule = {
            'понедельник': 'Марта',
            'вторник': 'Аркаша',
            'среда': 'Марта',
            'четверг': 'Аркаша',
            'пятница': 'Марта',
            'суббота': 'Аркаша',
            'воскресенье': 'Родители'
        }

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

    async def get_currency_rates(self):
        """Получаем курс USD/RUB и BTC/USD с направлением"""
        result = ""
        
        try:
            async with aiohttp.ClientSession() as session:
                # USD/RUB from CBR API
                try:
                    cbr_url = "https://www.cbr-xml-daily.ru/daily_json.js"
                    async with session.get(cbr_url, timeout=10) as response:
                        if response.status == 200:
                            text = await response.text()
                            data = json.loads(text)
                            usd = data.get('Valute', {}).get('USD', {})
                            usd_rate = usd.get('Value', 0)
                            usd_prev = usd.get('Previous', usd_rate)
                            if usd_rate:
                                usd_diff = usd_rate - usd_prev
                                usd_arrow = "↑" if usd_diff > 0 else "↓" if usd_diff < 0 else "→"
                                result += f"💵 USD: {usd_rate:.2f}₽ {usd_arrow}\n"
                                logger.info(f"✅ USD: {usd_rate:.2f} {usd_arrow}")
                        else:
                            logger.warning(f"CBR API status: {response.status}")
                except Exception as e:
                    logger.error(f"❌ USD error: {e}")
                
                # BTC/USD from CoinGecko with 24h change
                try:
                    btc_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
                    async with session.get(btc_url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            btc = data.get('bitcoin', {})
                            btc_price = btc.get('usd', 0)
                            btc_change = btc.get('usd_24h_change', 0)
                            if btc_price:
                                btc_arrow = "↑" if btc_change > 0 else "↓" if btc_change < 0 else "→"
                                btc_formatted = f"{btc_price:,.0f}".replace(",", " ")
                                result += f"₿ BTC: ${btc_formatted} {btc_arrow}{abs(btc_change):.1f}%\n"
                                logger.info(f"✅ BTC: ${btc_formatted} {btc_arrow}{abs(btc_change):.1f}%")
                        else:
                            logger.warning(f"CoinGecko API status: {response.status}")
                except Exception as e:
                    logger.error(f"❌ BTC error: {e}")
                            
        except Exception as e:
            logger.error(f"❌ Ошибка курсов: {e}")
        
        if result:
            result = "\n" + result  # Add newline before currency block
        
        return result

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

    def close_past_daily(self, key, days=14):
        """Закрыть прошедшие дни без ответа для ежедневного ритуала."""
        from datetime import timedelta as _td
        today = datetime.now().date()
        seen = self.trad_log.mark_seen(key, today.isoformat())
        closed = []
        for back in range(1, days + 1):
            day = today - _td(days=back)
            if day.isoformat() < seen:
                continue
            if self.close_unanswered(key, day.isoformat()):
                closed.append(key)
        return closed

    def close_past_weekly(self, key, weekday, weeks=2):
        """Закрыть прошедшие недельные события без ответа.

        Отдельно от close_past_events: уборка, игры и совет живут не в
        recurring_events, а собственными ветками запуска — у них нет
        правила вида «вторая суббота месяца», только день недели.
        """
        from datetime import timedelta as _td
        today = datetime.now().date()
        seen = self.trad_log.mark_seen(key, today.isoformat())
        closed = []
        for back in range(1, weeks * 7 + 1):
            day = today - _td(days=back)
            if day.isoformat() < seen:
                continue        # до первого показа механики пропусков нет
            if day.weekday() == weekday and self.close_unanswered(key, day.isoformat()):
                closed.append(key)
        return closed

    async def announce_archived(self, keys):
        """Сообщить о заархивированных традициях — с кнопкой возврата.

        Тихая архивация опаснее ошибочной: через полгода не вспомнить,
        что вообще было в списке.
        """
        names = self.tradition_names()
        for key in keys:
            if not self.trad_log.is_archived(key):
                continue
            msg, kb = archive_message(key, names.get(key, key))
            await self.send_telegram_message(msg, keyboard=kb)

    def close_past_events(self, today=None):
        """Закрыть все прошедшие события, на которые не ответили.

        Считается при запуске, а не в день события: у человека есть весь
        день, чтобы нажать кнопку. Смотрим на месяц назад — этого хватает
        и месячным традициям, и еженедельному совету.

        Возвращает ключи традиций, которым только что засчитали пропуск.
        """
        from datetime import date as _d, timedelta as _td
        today = _d.fromisoformat(today) if today else datetime.now().date()
        closed = []
        for key, event in self.recurring_events.items():
            if self.trad_log.is_archived(key):
                continue
            seen = self.trad_log.mark_seen(key, today.isoformat())
            for back in range(1, 32):
                day = today - _td(days=back)
                if day.isoformat() < seen:
                    continue
                ed = self.get_event_date_by_rule(event['rule'], day.year, day.month)
                if ed and _d(*ed) == day:
                    if self.close_unanswered(key, day.isoformat()):
                        closed.append(key)
        # Семейный совет — каждое воскресенье
        if not self.trad_log.is_archived('council'):
            seen_c = self.trad_log.mark_seen('council', today.isoformat())
            for back in range(1, 15):
                day = today - _td(days=back)
                if day.isoformat() < seen_c:
                    continue
                if day.weekday() == 6 and self.close_unanswered('council', day.isoformat()):
                    closed.append('council')
        return closed

    def close_unanswered(self, key, day):
        """Закрыть прошедшее событие как пропущенное, если ответа не было.

        Ровно то место, где реализовано «молчание считается пропуском».
        Уже проставленный ответ не трогаем: нажатие всегда важнее
        автоматики.
        """
        marks = self.trad_log.data.get(key, {}).get('marks', {})
        if str(day) in marks:
            return False
        self.trad_log.record(key, day, 'skip')
        return True

    def reminder_keyboard(self, reminders):
        """Кнопки «Было / Не было» — только в день события.

        За неделю и за три дня отмечать нечего: событие ещё не наступило,
        и кнопка там означала бы обещание, а не факт.
        """
        keys = [r['key'] for r in reminders if r.get('type') == 'event_day']
        if not keys:
            return None
        rows = []
        for k in keys:
            rows += event_keyboard(k)['inline_keyboard']
        return {'inline_keyboard': rows}

    def council_keyboard(self):
        return event_keyboard('council')

    def active_events(self):
        """Традиции без заархивированных.

        Раньше архивация была ручной — традицию комментировали в коде,
        и до этого момента она продолжала напоминать о себе."""
        return self.trad_log.filter_active(self.recurring_events)

    def tradition_names(self):
        names = {k: v['name'] for k, v in self.recurring_events.items()}
        names['council'] = 'Семейный совет'
        names['cleaning'] = 'Большая уборка'
        names['games'] = 'Семейные игры'
        names['gratitude'] = 'Семейная благодарность'
        return names

    def check_recurring_events(self):
        from datetime import date as dt
        today = datetime.now()
        year, month, day = today.year, today.month, today.day
        reminders = []
        
        for event_key, event in self.active_events().items():
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
        
        schedule_text = ""
        successful_items = 0
        
        # По времени, а не по порядку в данных: иначе занятие в 17:30
        # оказывается выше того, что в 17:00, и «время слева» перестаёт
        # работать.
        activities = sorted(activities, key=lambda a: a.get('time', ''))

        for idx, item in enumerate(activities):
            try:
                child = item['child']
                activity = item['activity']
                time = item['time']
                
                # Время слева: единственное, что выхватывается глазом
                # утром. Эмодзи убраны — метка на сообщение одна.
                start = time.split('-')[0].strip()
                schedule_text += f"{start} {child} — {activity}\n"
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
        
        # Компактная шапка (16.08.2026). Раньше до первой полезной строки
        # шло семь: погода в три строки, курсы, цитата. Утром нужно одно —
        # во сколько везти детей, поэтому расписание идёт сразу за датой,
        # а погода ужата в строку. Курсы убраны: они личные, и в личном
        # боте уже есть.
        content = f"🌅 <b>{day_ru}, {date_str}</b>\n"

        weather = await self.get_weather_forecast()
        if weather:
            content += f"{weather}\n"

        kids_schedule_text = self.get_kids_schedule(day_of_week)
        if kids_schedule_text:
            content += f"\n<b>Сегодня:</b>\n{kids_schedule_text}"

        dishes_reminder = self.get_dishes_reminder(day_of_week)
        if dishes_reminder:
            content += f"\nПосуда: {dishes_reminder}\n"

        content += "Телефон Аркаши в 20:00\n"
        
        reminders = self.check_recurring_events()
        if reminders:
            for reminder in reminders:
                event = reminder['event']
                
                # Если есть URL - используем короткий текст со ссылкой
                if 'url' in event:
                    if reminder['type'] == 'week_before':
                        content += f"\n🔔 <b>НАПОМИНАНИЕ (За 7 дней):</b>\n<b>{event['name']}</b>\n"
                        content += f"{event.get('short_text', '')}\n"
                        content += f"🔗 <a href='{event['url']}'>Подробнее</a>\n"
                    elif reminder['type'] == 'three_days_before':
                        content += f"\n🔔 <b>НАПОМИНАНИЕ (За 3 дня):</b>\n<b>{event['name']}</b>\n"
                        content += f"{event.get('short_text', '')}\n"
                        content += f"🔗 <a href='{event['url']}'>Подробнее</a>\n"
                    elif reminder['type'] == 'event_day':
                        content += f"\n🎉 <b>СЕГОДНЯ:</b>\n<b>{event['name']}</b>\n"
                        content += f"{event.get('short_text', '')}\n"
                        content += f"🔗 <a href='{event['url']}'>Подробнее</a>\n"
                        _w = warning_line(self.trad_log, reminder['key'])
                        if _w:
                            content += f"{_w}\n"
                else:
                    # Старая логика для событий с файлом
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

    async def send_telegram_message(self, message, send_ss=False, keyboard=None):
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id, 
                'text': message, 
                'parse_mode': 'HTML',
                'disable_web_page_preview': False
            }
            if keyboard:
                payload['reply_markup'] = json.dumps(keyboard)
            
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
                    'disable_web_page_preview': False,
                    'reply_markup': json.dumps(self.council_keyboard())
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
        
        send_ss = (day_of_week == 'sunday' and
                   not self.trad_log.is_archived('council'))

        # Прошедшие события без ответа закрываем как пропущенные — это и
        # есть «молчание считается пропуском».
        _closed = self.close_past_events()

        keyboard = self.reminder_keyboard(self.check_recurring_events())
        result = await self.send_telegram_message(message, send_ss=send_ss,
                                                  keyboard=keyboard)
        await self.announce_archived(_closed)
        return result

    async def send_gratitude_reminder(self):
        """Ежедневно 20:00 МСК — семейная благодарность.

        Порог архива у неё десять пропусков, а не три: ритуал ежедневный,
        и три подряд набираются на первой же занятой неделе.
        """
        if self.trad_log.is_archived('gratitude'):
            return True
        self.close_past_daily('gratitude')
        text = "🌷Самое время получить семейную благодарность"
        warn = warning_line(self.trad_log, 'gratitude')
        if warn:
            text += f"\n\n{warn}"
        return await self.send_telegram_message(
            text, keyboard=event_keyboard('gratitude'))

    async def send_games_reminder(self):
        """Пятница 19:00 МСК — семейные игры. Такая же традиция: с
        кнопками и с архивом по трём пропускам."""
        if self.trad_log.is_archived('games'):
            return True
        self.close_past_weekly('games', 4)      # игры по пятницам
        return await self.send_telegram_message(
            "🏠Самое время поиграть в семейные игры и повеселиться",
            keyboard=event_keyboard('games'))

    async def send_cleaning_reminder(self):
        """Воскресенье 10:00 МСК - Большая уборка"""
        if self.trad_log.is_archived('cleaning'):
            return True
        self.close_past_weekly('cleaning', 6)   # уборка по воскресеньям
        text = "Всем привет сегодня 🧹Большая Уборка!"
        warn = warning_line(self.trad_log, 'cleaning')
        if warn:
            text += f"\n\n{warn}"
        return await self.send_telegram_message(
            text, keyboard=event_keyboard('cleaning'))

    async def send_cleaning_tomorrow(self):
        """Суббота 18:00 МСК - напоминание про уборку завтра.

        Часть той же традиции: если уборка в архиве, предупреждать не о
        чем."""
        if self.trad_log.is_archived('cleaning'):
            return True
        return await self.send_telegram_message("Ребята завтра утром 🧹Большая Уборка!")

    async def send_this_day_in_history(self):
        """Ежедневно - интересный/забавный факт 'Этот день в истории' через AI"""
        try:
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key:
                logger.error("❌ OPENAI_API_KEY не найден")
                return False
            
            today = datetime.now()
            day = today.day
            month_names = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                          'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
            month = month_names[today.month - 1]
            
            prompt = f"""Расскажи один интересный, забавный или удивительный исторический факт о том, что произошло {day} {month} в любой год в истории.

Требования:
- Факт должен быть реальным и проверяемым
- Предпочтительны забавные, необычные или удивительные события
- Можно про изобретения, открытия, рекорды, курьёзы
- Формат: короткий факт (2-3 предложения)
- В конце укажи год события

Напиши только сам факт, без вступлений."""

            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.9
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        fact = data['choices'][0]['message']['content'].strip()
                        
                        message = f"📅 <b>Этот день в истории</b>\n"
                        message += f"<i>{day} {month}</i>\n\n"
                        message += fact
                        
                        logger.info(f"✅ AI факт получен: {fact[:50]}...")
                        return await self.send_telegram_message(message)
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ OpenAI ошибка: {response.status} - {error_text[:100]}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Ошибка получения факта: {e}")
            return False

async def main():
    logger.info(f"🚀 Запуск семейного бота")
    bot = FamilyScheduleBot()
    
    mode = sys.argv[1] if len(sys.argv) > 1 else 'morning'
    
    if mode == 'gratitude':
        success = await bot.send_gratitude_reminder()
    elif mode == 'games':
        success = await bot.send_games_reminder()
    elif mode == 'cleaning':
        success = await bot.send_cleaning_reminder()
    elif mode == 'cleaning_tomorrow':
        success = await bot.send_cleaning_tomorrow()
    elif mode == 'this_day':
        success = await bot.send_this_day_in_history()
    else:
        success = await bot.send_morning_message()
    
    if success:
        logger.info("🎉 Успешно завершено!")
    else:
        logger.error("💥 Ошибка при отправке")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
