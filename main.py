import telebot
import re
import threading
import requests
import random
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

    # Ищем первый блок с классом "ui-datepicker-calendar"
    calendar_block = soup.find(class_="ui-datepicker-calendar")
    if not calendar_block:
        raise ValueError("Не найден блок с классом 'ui-datepicker-calendar'.")

    # Ищем все ссылки на DOCX-файлы в этом блоке
    docx_links = [link['href'] for link in calendar_block.select('a[href$=".docx"]')]

    # Если это относительные ссылки, преобразуем их в абсолютные
    docx_links = [urljoin(base_url, link) for link in docx_links]

    # Берем последнюю ссылку
    latest_link = docx_links[-1] if docx_links else None
    if not latest_link:
        raise ValueError("Не найдено ссылки на DOCX-файл в блоке 'ui-datepicker-calendar'.")

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
        ("09:30", "11:05"),
        ("11:15", "12:50"),
        ("13:35", "15:10"),
        ("15:20", "16:50"),
        ("17:00", "18:20"),
        ("18:30", "19:50")
    ],
    'wednesday': [
        ("07:50", "09:20"),
        ("09:30", "11:05"),
        ("11:15", "12:50"),
        ("13:35", "15:10"),
        ("16:10", "17:30"),
        ("17:40", "18:50"),
        ("19:00", "20:10")
    ],
    'saturday': [
        ("08:00", "09:20"),
        ("09:30", "10:50"),
        ("11:00", "12:20"),
        ("12:30", "13:50"),
        ("14:00", "15:20"),
        ("15:30", "16:50"),
        ("17:00", "18:20")
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
commands = [
    ("/расписание", "Расписание на сегодня"),
    ("/неделя", "Расписание на неделю"),
    ("/пара", "Текущая пара"),
    ("/замены", "Замены на сегодня"),
    ("/надолинапару", "Надо ли на пару?"),
    ("/завтра", "Пары на завтра")
]
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



def get_next_day(today):
    days = ['ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'СРЕДА', 'ЧЕТВЕРГ', 'ПЯТНИЦА', 'СУББОТА', 'ВОСКРЕСЕНЬЕ']
    today_index = days.index(today)
    next_day_index = (today_index + 1) % 7
    return days[next_day_index]

@bot.message_handler(commands=['завтра', 'tomorrow'])
def tomorrow_schedule(message):
    today = days_mapping[datetime.today().strftime('%A').upper()]
    tomorrow = get_next_day(today)
    lessons = schedule.get(tomorrow, {})
    if not lessons:
        bot.reply_to(message, "Завтра занятий нет.")
        return

    response = "\n".join([format_lesson(i, lesson, tomorrow) for i, lesson in lessons.items()])
    bot.reply_to(message, response)




@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = """
*Я бот-расписание для группы 21уКСК-1*. Вот что я умею:

- *Расписание*: Показывает расписание на текущий день.
- *Неделя*: Показывает расписание на всю неделю.
- *Пара*: Указывает, какая сейчас идет пара.
- *Напомнить*: Позволяет установить напоминание на определенное время.
-  Устанавливается с помощью /напомнить 13:37 жопа
- *Замены*: Выводит информацию о заменах на сегодня.
- *Надо ли на пару?*: Случайным образом говорит, стоит ли идти на пару.
- *Завтра*: Выводит информацию о завтрашних парах.
    """
    markup = types.InlineKeyboardMarkup()
    for cmd, desc in commands:
        markup.add(types.InlineKeyboardButton(text=desc, callback_data=cmd))
    bot.send_message(message.chat.id, help_text, reply_markup=markup, parse_mode="Markdown")

# Добавим обработчик для callback_query, чтобы обрабатывать нажатия на кнопки
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        if call.data == "/расписание":
            today_schedule(call.message)
        elif call.data == "/неделя":
            week_schedule(call.message)
        elif call.data == "/пара":
            current_lesson(call.message)
        elif call.data == "/замены":
            fetch_replacements(call.message)
        elif call.data == "/надолинапару":
            should_i_go_to_class(call.message)
        elif call.data == "/завтра":
            tomorrow_schedule(call.message)
        else:
            bot.send_message(call.message.chat.id, f"Неизвестная команда: {call.data}")






def format_lesson(lesson_num, lesson_info, day):
    if day in ['ПОНЕДЕЛЬНИК', 'ВТОРНИК', 'ЧЕТВЕРГ', 'ПЯТНИЦА']:
        day_key = 'default'
    elif day == 'СРЕДА':
        day_key = 'wednesday'
    elif day == 'СУББОТА':
        day_key = 'saturday'
    else:
        return f"Ошибка: Неизвестный день {day}"

    time_range = f"{bell_schedule[day_key][lesson_num][0]}-{bell_schedule[day_key][lesson_num][1]}"
    return f"{time_range} - {lesson_info[0]} - {lesson_info[1]} ({lesson_info[2]})"



@bot.message_handler(commands=['расписание', 'schedule'])
def today_schedule(message):
    today = days_mapping[datetime.today().strftime('%A').upper()]
    lessons = schedule.get(today, {})
    if not lessons:
        bot.reply_to(message, "Сегодня занятий нет. Ты че долбаеб это в воскресенье спрашивать?")
        return

    response = "\n".join([format_lesson(i, lesson, today) for i, lesson in lessons.items()])
    bot.reply_to(message, response)

@bot.message_handler(commands=['неделя', 'weekschedule'])
def week_schedule(message):
    response = ""
    for day, lessons in schedule.items():
        response += day + ":\n"
        response += "\n".join([format_lesson(i, lesson, day) for i, lesson in lessons.items()]) + "\n\n"
    bot.reply_to(message, response)

@bot.message_handler(commands=['пара', 'lesson'])
def current_lesson(message):
    today = days_mapping[datetime.today().strftime('%A').upper()]
    current_time = datetime.now().time()
    current_lesson = None
    next_lesson = None

    for i, (start, end) in enumerate(bell_schedule.get(today, bell_schedule['default'])):
        start_time = datetime.strptime(start, "%H:%M").time()
        end_time = datetime.strptime(end, "%H:%M").time()
        if start_time <= current_time <= end_time:
            current_lesson = i
        if current_time <= start_time:
            next_lesson = i
            break

    response = ""

    if current_lesson is not None and current_lesson in schedule.get(today, {}):
        lesson = schedule[today][current_lesson]
        time_range = f"{bell_schedule.get(today, bell_schedule['default'])[current_lesson][0]}-{bell_schedule.get(today, bell_schedule['default'])[current_lesson][1]}"
        response += f"Текущая пара ({time_range}): {lesson[0]} - {lesson[1]} ({lesson[2]})\n"

    if next_lesson is not None and next_lesson in schedule.get(today, {}):
        lesson = schedule[today][next_lesson]
        time_range = f"{bell_schedule.get(today, bell_schedule['default'])[next_lesson][0]}-{bell_schedule.get(today, bell_schedule['default'])[next_lesson][1]}"
        response += f"Следующая пара ({time_range}): {lesson[0]} - {lesson[1]} ({lesson[2]})"

    if not response:
        response = "Сейчас нет пары."

    bot.reply_to(message, response)



@bot.message_handler(commands=['надолинапару'])
def should_i_go_to_class(message):
    responses = ["Да, надо", "Нет, не надо"]
    bot.reply_to(message, random.choice(responses))



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

bot.polling(timeout=999)
