import telebot
import schedule
import time
import datetime
import pytz
import requests
from threading import Thread
from config import TOKEN, GROUP_CHAT_ID, TIMEZONE, SEND_TIME, GO_TIME

# ===============================
# 🔧 Настройки
# ===============================
HOLIDAYS_URL = "https://isdayoff.ru/api/getdata?year={year}&month={month}&day={day}&cc=ru"
LOG_FILE = "bot.log"

TEST_MODE = False  # <<< если True — бот сразу создаёт “сегодняшний” опрос, но не завершает работу
ENABLE_LOGGING = False  # <<< если True - ведётся логирование в файл
RICH_POLL_CHECK_INTERVAL = 20     # каждые 60 секунд проверяем опрос
RICH_POLL_CHECK_DURATION = 3600   # проверяем в течение 1 часа (3600 сек)

poll_id = None
rich_poll_id = None


# ===============================
# 🧾 Логирование
# ===============================
def log(message):
    if not ENABLE_LOGGING:
        return
        
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    timestamp = now.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")
    print(f"{timestamp} {message}")


bot = telebot.TeleBot(TOKEN)
log("Bot started")


# ===============================
# 👋 Команда /hello
# ===============================
@bot.message_handler(commands=['hello'])
def hello_command(message):
    """Приветствие пользователя"""
    user_name = message.from_user.first_name or message.from_user.username or "пользователь"
    current_time = datetime.datetime.now(pytz.timezone(TIMEZONE)).strftime("%H:%M")

    greeting = (
        f"Привет, {user_name}! \n"
        f"Сейчас {current_time} по времени {TIMEZONE.split('/')[-1]}.\n"
        f"Я бот для организации походов в столовую! 🍽️"
    )

    try:
        bot.reply_to(message, greeting)
        log(f"Отправлено приветствие пользователю {message.from_user.id} ({user_name})")
    except Exception as e:
        log(f"Ошибка отправки приветствия: {e}")


# ===============================
# 📅 Проверка праздников
# ===============================
def is_holiday():
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    try:
        response = requests.get(HOLIDAYS_URL.format(year=now.year, month=now.month, day=now.day), timeout=5)
        return response.text.strip() == "1"
    except Exception as e:
        log(f"Ошибка проверки праздника: {e}")
        return False


# ===============================
# 📊 Создание опросов
# ===============================
def create_poll(question, options):
    """Создаёт опрос в чате"""
    global poll_id
    while True:
        try:
            poll = bot.send_poll(
                GROUP_CHAT_ID,
                question,
                options,
                is_anonymous=False
            )
            poll_id = poll.poll.id
            log(f"Опрос отправлен: {question}")
            return poll
        except Exception as e:
            log(f"Не удалось отправить опрос ({question}): {e}")
            time.sleep(10)


def send_main_poll():
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    if now.weekday() < 5 and not is_holiday():
        create_poll(f"Идем в столовку в {GO_TIME}?", ["Да", "Нет", "Другое время"])
    else:
        log("Сегодня выходной или праздник — основной опрос не отправляется.")


def send_rich_poll():
    """Опрос 'Едем в богатую столовую?' с последующим мониторингом ответов"""
    global rich_poll_id
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    if now.weekday() == 2 and not is_holiday():  # среда
        poll = create_poll("Едем в богатую столовую?", ["Да", "Нет"])
        rich_poll_id = poll.poll.id
        Thread(target=monitor_rich_poll, args=(rich_poll_id,), daemon=True).start()
    else:
        log("Сегодня не среда или праздник — опрос про богатую столовую не отправляется.")


# ===============================
# 🔍 Мониторинг опроса про богатую столовку
# ===============================
def monitor_rich_poll(poll_id_to_check):
    """Следит за опросом: если ≥2 'Нет' за час — создаёт обычный опрос"""
    log("Начинаем мониторинг опроса 'богатая столовка'...")
    start_time = time.time()

    while time.time() - start_time < RICH_POLL_CHECK_DURATION:
        try:
            updates = bot.get_updates(timeout=5)
            for update in updates:
                if update.poll and update.poll.id == poll_id_to_check:
                    votes_no = update.poll.options[1].voter_count  # второй вариант — "Нет"
                    log(f"Текущее количество ответов 'Нет': {votes_no}")
                    if votes_no >= 2:
                        log("Обнаружено ≥2 ответов 'Нет' — создаём обычный опрос.")
                        send_main_poll()
                        return
        except Exception as e:
            log(f"Ошибка при проверке опроса: {e}")

        time.sleep(RICH_POLL_CHECK_INTERVAL)

    log("Мониторинг опроса завершён — условия для запуска обычного опроса не выполнены.")


# ===============================
# ⏰ Планирование задач
# ===============================
schedule.every().day.at(SEND_TIME).do(send_main_poll)
schedule.every().wednesday.at("10:40").do(send_rich_poll)


# ===============================
# 🚀 Основной запуск
# ===============================
def main_loop():
    while True:
        schedule.run_pending()
        time.sleep(30)


now = datetime.datetime.now(pytz.timezone(TIMEZONE))

if TEST_MODE:
    log("Тестовый режим активирован — создаём опрос, который должен быть сегодня.")
    if now.weekday() == 2:
        send_rich_poll()
    elif now.weekday() < 5:
        send_main_poll()
    else:
        log("Сегодня выходной — тестовый опрос не создаётся.")
    # после теста просто продолжаем работать дальше
    Thread(target=main_loop, daemon=False).start()
else:
    main_loop()