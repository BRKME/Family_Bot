# Family_Bot

Семейный бот в Telegram: утреннее сообщение с погодой, занятиями детей,
дежурством по посуде и напоминаниями о семейных традициях.

## Живые традиции

Традиции больше не архивируются руками. В день события приходят две
кнопки — «Было» и «Не было». Три пропуска подряд, и традиция уходит в
архив: напоминания о ней прекращаются.

- **Молчание считается пропуском.** Иначе традиция, которую никогда не
  отмечают, не заархивируется никогда. Прошедшее событие без ответа
  закрывается при следующем запуске — есть целый день, чтобы нажать.
- **Предупреждение на втором пропуске**, чтобы архивация не стала
  неожиданностью.
- **Возврат одной кнопкой**: сообщение об архиве несёт «↩️ Вернуть»,
  счётчик при этом обнуляется.
- Семейный совет — такая же традиция с ключом `council`.

Состояние — `traditions.json`, логика — `traditions.py`, тесты —
`test_traditions.py`.

## Где что работает

| Компонент | Где | Что делает |
|---|---|---|
| `notifier.py` | GitHub Actions | шлёт сообщения, показывает кнопки |
| `dispatch.sh` | VPS-крон | держит время утреннего запуска |
| `family_tracker.py` | systemd на VPS | принимает нажатия, пишет `traditions.json`, коммитит его в репозиторий |

Разделение вынужденное: Actions поднимает контейнер с нуля и стирает
после запуска, поэтому принять нажатие и сохранить состояние он не может.

## Время утреннего сообщения

Расписание GitHub дрейфует на часы, и утреннее сообщение приходило не
вовремя. Время держит крон на VPS, GitHub только исполняет:

```bash
mkdir -p /opt/familybot
cp /opt/Family_Bot/dispatch.sh /opt/familybot/dispatch.sh
chmod +x /opt/familybot/dispatch.sh
(crontab -l; echo '30 8 * * *  /opt/familybot/dispatch.sh morning') | crontab -
```

Остальные запуски (благодарность, игры, уборка) остались на расписании
GitHub — там дрейф в час роли не играет. Если GitHub не примет задачу,
скрипт пришлёт предупреждение в чат: молча терять запуски нельзя.

## Установка трекера на VPS

```bash
cd /opt && git clone https://github.com/BRKME/Family_Bot.git
cat > /etc/family-bot.env <<'ENV'
TELEGRAM_TOKEN=токен_семейного_бота
TELEGRAM_CHAT_ID=id_семейного_чата
GITHUB_TOKEN=pat_с_правом_contents
ENV
chmod 600 /etc/family-bot.env
cp /opt/Family_Bot/family-tracker.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now family-tracker
journalctl -u family-tracker -n 20 --no-pager
```

Секреты в отдельном файле, а не в юните: `systemctl cat` их не покажет.

## Запуск

```bash
pip install -r requirements.txt
TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=... python notifier.py
python -m pytest -q
```
