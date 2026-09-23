#!/usr/bin/env bash
# Запуск Family_Bot через workflow_dispatch с VPS-крона.
#
# Расписание GitHub дрейфует на часы: утреннее сообщение приходило не
# вовремя. Время держит крон на VPS, GitHub только исполняет.
#
# Установка:
#   cp /opt/Family_Bot/dispatch.sh /opt/familybot/dispatch.sh
#   chmod +x /opt/familybot/dispatch.sh
#   (crontab -l; echo '30 8 * * *  /opt/familybot/dispatch.sh morning') | crontab -
set -u

MODE="${1:-morning}"
ENV_FILE="/etc/family-bot.env"
LOG="/opt/familybot/dispatch.log"

[ -f "$ENV_FILE" ] && . "$ENV_FILE"

CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/BRKME/Family_Bot/actions/workflows/personal-schedule.yml/dispatches" \
  -d "{\"ref\":\"main\",\"inputs\":{\"mode\":\"${MODE}\"}}")

mkdir -p "$(dirname "$LOG")"
echo "$(date '+%F %T') ${MODE} HTTP=${CODE}" >> "$LOG"

# 204 — GitHub принял задачу. Всё остальное молча терять нельзя:
# именно так пропадали запуски.
[ "$CODE" = "204" ] || {
  [ -n "${TELEGRAM_TOKEN:-}" ] && curl -s -o /dev/null -X POST \
    "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_CHAT_ID}" \
    -d text="⚠️ Family_Bot: запуск ${MODE} не принят GitHub (HTTP ${CODE})"
  exit 1
}
