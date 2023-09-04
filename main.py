import telebot
import re
import threading
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from docx import Document
from io import BytesIO
from datetime import datetime
from telebot import types

TOKEN = '6389584311:AAEOqZhGrLhHuKz03D4z3gW_ZQAObS6sOsA'
bot = telebot.TeleBot(TOKEN)

def fetch_latest_docx_url(base_url="https://www.uksivt.ru/zameny"):
    response = requests.get(base_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')

    # Ищем все ссылки на DOCX-файлы
    docx_links = [link['href'] for link in soup.select('td > a[href$=".docx"]')]

    # Если это относительные ссылки, преобразуем их в абсолютные
    docx_links = [urljoin(base_url, link) for link in docx_links]

    # Извлекаем даты из имен файлов
    file_dates = [link.split('/')[-1].replace('.docx', '') for link in docx_links]

    # Преобразуем строки дат в объекты datetime
    date_objects = []
    for date_str in file_dates:
        try:
            date_obj = datetime.strptime(date_str, "%d.%m")
            date_objects.append(date_obj)
        except ValueError:
            pass

    # Определяем последнюю дату
    latest_date = max(date_objects, default=None)
    if not latest_date:
        raise ValueError("Не удалось определить последнюю дату.")

    # Находим ссылку, соответствующую последней дате
    latest_date_str = latest_date.strftime("%d.%m")
    latest_link = next((link for link in docx_links if latest_date_str in link), None)
    if not latest_link:
        raise ValueError("Не найдено ссылки на DOCX-файл для последней даты.")

    return latest_link

#print(fetch_latest_docx_url())
def extract_schedule_from_docx(docx_url):
    # Скачиваем docx-файл
    response = requests.get(docx_url)
    response.raise_for_status()

    # Открываем docx-файл с помощью python-docx
    doc = Document(BytesIO(response.content))

    # Ищем строку для группы 21уКСК
    for table in doc.tables:
        for row in table.rows:
            if "21уКСК" in row.cells[0].text:  # Проверяем первую ячейку каждой строки на наличие "21уКСК"
                return ' '.join(cell.text for cell in row.cells)
    return None

# Обновленное расписание для группы 21уКСК-1
schedule = {
    'ПОНЕДЕЛЬНИК': {
        3: ('МПШ', '001в', 'Лихарев'),
        4: ('МПШ', '001в', 'Лихарев'),
        5: ('МПШ', '001в', 'Лихарев'),
    },
    'ВТОРНИК': {
        2: ('Английский язык', '322', 'Ахметова'),
        3: ('МДК', '001в', 'Шарипов'),
        4: ('МДК', '001в', 'Шарипов'),
        5: ('Физра', None, 'Баранов АВ'),
    },
    'СРЕДА': {
        0: ('Программирование', '3', 'Хасипов Р. Эх'),
        1: ('Программирование', '3', 'Хасипов Р. Эх'),
    },
    'ЧЕТВЕРГ': {
        1: ('МПШ', '001в', 'Лихарев'),
        2: ('МПШ', '001в', 'Лихарев'),
        3: ('МПШ', '001в', 'Лихарев'),
    },
    'ПЯТНИЦА': {
        0: ('МДК', '001в', 'Шарипов НТ'),
        1: ('МДК', '001в', 'Шарипов НТ'),
        2: ('МДК', '001в', 'Шарипов НТ'),
    },
    'СУББОТА': {
        4: ('Программирование', '3', 'Хасипов Р. Эх'),
        5: ('Программирование', '3', 'Хасипов Р. Эх'),
        6: ('Программирование', '3', 'Хасипов Р. Эх'),
    }
}


bell_schedule = {
    'default': [
        ("07:50", "09:20"),
        ("09:30", "10:45"),
        ("11:15", "12:00"),
        ("12:00", "12:45"),  # 1-я половина 2-ой пары для 3-4 курсов
        ("12:45", "13:30"),  # 2-я половина 2-ой пары для 1-х, 3-х, 4-х курсов
        ("12:05", "12:50"),  # 2-я половина 2-ой пары для 2-х курсов
        ("13:35", "14:20"),
        ("14:25", "15:40"),
        ("15:20", "16:50"),
        ("17:00", "18:20"),
        ("18:30", "19:50")
    ],
    'wednesday': [
        ("07:50", "09:20"),
        ("09:30", "10:45"),
        ("11:15", "12:00"),
        ("12:00", "12:45"),  # 1-я половина 2-ой пары для 3-4 курсов
        ("12:45", "13:30"),  # 2-я половина 2-ой пары для 1-х, 3-х, 4-х курсов
        ("12:05", "12:50"),  # 2-я половина 2-ой пары для 2-х курсов
        ("13:35", "14:20"),
        ("14:25", "15:40"),
        ("16:10", "17:30"),
        ("17:40", "18:50"),
        ("19:00", "20:40")
    ],
    'saturday': [
        ("08:00", "09:20"),
        ("09:30", "10:50"),
        ("11:00", "12:20"),
        ("12:30", "13:50"),
        ("14:00", "15:20"),
        ("15:30", "16:50"),
        ("17:40", "18:20")
    ]
}
days_mapping = {
    'MONDAY': 'ПОНЕДЕЛЬНИК',
    'TUESDAY': 'ВТОРНИК',
    'WEDNESDAY': 'СРЕДА',
    'THURSDAY': 'ЧЕТВЕРГ',
    'FRIDAY': 'ПЯТНИЦА',
    'SATURDAY': 'СУББОТА',
    'SUNDAY': 'ВОСКРЕСЕНЬЕ'
}
reminders = {}
all_users = set()

def remind_user(chat_id, text):
    bot.send_message(chat_id, text)

@bot.message_handler(commands=['замены'])
def fetch_replacements(message):
    try:
        docx_url = fetch_latest_docx_url()
        schedule_info = extract_schedule_from_docx(docx_url)
        if schedule_info:
            bot.reply_to(message, schedule_info)
        else:
            bot.reply_to(message, "Не удалось найти информацию для группы 21уКСК в последнем docx-файле.")
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {e}")


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = """
Я бот-расписание для группы 21уКСК-1. Вот список команд, которые я поддерживаю:

1. "/расписание": Показать расписание на сегодня.
   Пример: /расписание

2. `"/расписаниенанеделю": Показать расписание на всю неделю.
   Пример: /расписаниенанеделю

3. "/пара": Узнать текущую пару.
   Пример: /пара

4. `/напомнить`: Установить напоминание на определенное время.
   Пример: /напомнить 8:30 Иди нахуй

5. `/напомнитьвсем`: Установить напоминание для всех пользователей на определенное время.
   Пример: /напомнитьвсем 9:00 Всем просыпаться!
   
6. /замены - выводит замены на сегодня
могу не работать 
    """
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['расписание', 'schedule'])
def today_schedule(message):
    today = days_mapping[datetime.today().strftime('%A').upper()]
    lessons = schedule.get(today, {})
    if not lessons:
        bot.reply_to(message, "Сегодня занятий нет. Ты че долбаеб это в воскресенье спрашивать?")
        return

    response = "\n".join([f"{i}. {lesson[0]} - {lesson[1]} ({lesson[2]})" for i, lesson in lessons.items()])
    bot.reply_to(message, response)

@bot.message_handler(commands=['расписаниенанеделю', 'weekschedule'])
def week_schedule(message):
    response = ""
    for day, lessons in schedule.items():
        response += day + ":\n"
        response += "\n".join([f"{i}. {lesson[0]} - {lesson[1]} ({lesson[2]})" for i, lesson in lessons.items()]) + "\n\n"
    bot.reply_to(message, response)

@bot.message_handler(commands=['пара', 'lesson'])
def current_lesson(message):
    today = datetime.today().strftime('%A').upper()
    current_time = datetime.now().time()
    current_lesson = None
    for i, (start, end) in enumerate(bell_schedule.get(today, bell_schedule['default'])):
        start_time = datetime.strptime(start, "%H:%M").time()
        end_time = datetime.strptime(end, "%H:%M").time()
        if start_time <= current_time <= end_time:
            current_lesson = i
            break

    if current_lesson is not None and current_lesson in schedule.get(today, {}):
        lesson = schedule[today][current_lesson]
        bot.reply_to(message, f"Текущая пара: {lesson[0]} - {lesson[1]} ({lesson[2]})")
    else:
        bot.reply_to(message, "Сейчас нет пары.")

@bot.message_handler(commands=['напомнить'])
def set_reminder(message):
    # Разделяем сообщение на время и текст напоминания
    match = re.match(r'/напомнить (\d{1,2}:\d{2})\s+(.+)', message.text)
    if not match:
        bot.reply_to(message, "Ошибка при установке напоминания. Пожалуйста, убедитесь, что вы указали время и текст корректно.")
        return

    reminder_time = match.group(1)
    reminder_text = match.group(2)
    try:
        remind_time = datetime.strptime(reminder_time, "%H:%M")
        current_time = datetime.now()
        delay = (remind_time - current_time).seconds
        if delay < 0:
            bot.reply_to(message, "Указанное время уже прошло. Пожалуйста, укажите другое время.")
            return
        threading.Timer(delay, remind_user, args=[message.chat.id, reminder_text]).start()
        reminders[message.chat.id] = (remind_time, reminder_text)
        bot.reply_to(message, f"Напоминание установлено на {reminder_time}: {reminder_text}")
    except Exception as e:
        bot.reply_to(message, "Ошибка при установке напоминания. Пожалуйста, убедитесь, что вы указали время и текст корректно.")


@bot.message_handler(commands=['напомнитьвсем', 'remindall'])
def remind_all(message):
    # Разделяем сообщение на время и текст напоминания
    match = re.match(r'/напомнитьвсем (\d{1,2}:\d{2})\s+(.+)', message.text)
    if not match:
        bot.reply_to(message, "Ошибка при установке напоминания. Пожалуйста, убедитесь, что вы указали время и текст корректно.")
        return

    reminder_time = match.group(1)
    reminder_text = match.group(2)
    try:
        remind_time = datetime.strptime(reminder_time, "%H:%M")
        current_time = datetime.now()
        delay = (remind_time - current_time).seconds
        if delay < 0:
            bot.reply_to(message, "Указанное время уже прошло. Пожалуйста, укажите другое время.")
            return
        for user_id in all_users:
            threading.Timer(delay, remind_user, args=[user_id, reminder_text]).start()
        bot.reply_to(message, f"Напоминание всем установлено на {reminder_time}.")
    except Exception as e:
        bot.reply_to(message, "Ошибка при установке напоминания. Пожалуйста, убедитесь, что вы указали время и текст корректно.")


bot.polling()