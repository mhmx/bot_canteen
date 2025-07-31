import telebot
import schedule
import time
import datetime
import pytz
import requests
from config import TOKEN, GROUP_CHAT_ID, TIMEZONE, SEND_TIME, GO_TIME


HOLIDAYS_URL = "https://isdayoff.ru/api/getdata?year={year}&month={month}&day={day}&cc=ru"

poll_id = None

LOG_FILE = "bot.log"

def log(message):
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    timestamp = now.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")
    print(f"{timestamp} {message}")  # чтобы и в консоли оставалось

bot = telebot.TeleBot(TOKEN)
log("Bot started")

def is_holiday():
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    try:
        response = requests.get(HOLIDAYS_URL.format(year=now.year, month=now.month, day=now.day), timeout=5)
        return response.text.strip() == "1"
    except Exception as e:
        log(f"Ошибка проверки праздника: {e}")
        return False

def create_poll():
    global poll_id
    while True:
        try:
            poll = bot.send_poll(
                GROUP_CHAT_ID,
                f"Идем в столовку в {GO_TIME}?",
                ["Да", "Нет", "Другое время"],
                is_anonymous=False
            )
            poll_id = poll.poll.id
            log("Опрос успешно отправлен.")
            break
        except Exception as e:
            log(f"Не удалось отправить опрос: {e}")
            time.sleep(10)

def send_poll():
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    if now.weekday() < 5 and not is_holiday():
        #log("Сегодня будний день, не праздник — пытаемся отправить опрос.")
        create_poll()
    else:
        log("Сегодня выходной или праздник — опрос не отправляется.")

# Планирование отправки по времени
schedule.every().day.at(SEND_TIME).do(send_poll)

# Основной цикл
while True:
    schedule.run_pending()
    time.sleep(30)
