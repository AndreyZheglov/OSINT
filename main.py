import pandas as pd
import re
import logging
import parsers
import apiS4F as S4f
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
    ChosenInlineResultHandler
)
from datetime import datetime
import random
from parsers import User
from ocr import ocr
import os
from mega import Mega
import json
from database_operations import db_ops


FILENAME = "settings.json"


# logging
logging.basicConfig(format='%(asctime)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                             filename="bot.log", encoding="utf-8")


# list of necessary variables
maitenance = False                                  # загрузка інфи у базу і тд
authorized_users = []                               # список авторизованих користувачів
settings = {}                                       # словник із налаштуваннями (завантажується із файлу)
created_user = None
created_user_admin_flag = False
created_user_parameter = None
table_name = None                                   # змінна для зберігання імені таблиці. Формат: file_
field_list = []


tablegroups_path = "database_operations/tablegroups.json"
table_groups = db_ops.read_tablegroups(tablegroups_path)

# Database necessary variables
db_record = []

# for authentication checkIn
user_iDs = []
active_user = []  # list of users, that are operating in bot

# regular expressions for handlers
choise_regex = 'Ввід інформації|Пошук інформації|Інструкція'
command_regex = ['Вручну', 'У вигляді файлу']
output_regex = "Пошук у базі бота|Пошук особи за фотографією|Вихід"
error_msg = "Сталась помилка під час використання бота. Радимо натиснути /cancel та почати роботу заново. Просимо вибачення за помилку"
bot_log = "bot.log"


# Handler constants
ADMIN_PANEL, ADMIN_CHOISE, AUTHORIZATION, MAIN_MENU, IO_CHOISE, INSERTION_MODE, FILE_INSERTION,  GET_PARAMETER, \
    GET_INFO, USER_ADDING, USER_DELETING, INSTRUCTION, TELEPHONE, UPLOAD_TO_MEGA, \
    CONTINUE, PHOTO_INSERTION, LINK_INSERTION, LOG_CHOICE, \
    USER_INFO_CONFIRMATION, USER_INFO_CORRECTION, S4F_TOKEN_INSERTION, TABLE_GROUP_SELECTION, \
    TABLE_GROUP_STRUCTURE, APPEND_CHOICE, PARAMETER_CONFIRMATION, PARAMETER_CORRECTION, TABLE_GROUP_INPUT_SELECTION, \
    TABLE_INDEX_CHOICE, TABLENAME_INSERTION = range(29)


# bot functions
def return_user(telegram_id) -> parsers.User:
    for user in authorized_users:
        if telegram_id == user.telegram_id:
            return user



# Function to check for admin
def admin(telegram_id):
    global authorized_users
    return telegram_id in [user.telegram_id for user in authorized_users if user.admin]


# User authorization
def start(update: Update, context: CallbackContext) -> int:
    sender = update.message.from_user

    global authorized_users
    global user_iDs
    user_iDs = [user.telegram_id for user in authorized_users]

    # sending the user in the direction of russian battleship if the user is not in authorized_users
    if sender.id not in user_iDs:
        update.message.reply_text("Вам користуватись ботом не дозволено, ідіть нахуй")
        # Chat.ban_member(user_id=sender.id)
    else:
        update.message.reply_text("Введіть ПІН для входу в систему")
        return AUTHORIZATION


def cancel(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    global authorized_users
    update.message.reply_text("Робота із ботом завершена", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def authorization(update: Update, context: CallbackContext) -> int:
    sender = update.message.from_user
    global active_user
    PIN = update.message.text.strip()
    if len(PIN) == 0:
        update.message.reply_text("Ви не ввели пароль. Повторіть спробу")
        return AUTHORIZATION

    global authorized_users
    for user in authorized_users:
        if sender.id == user.telegram_id and int(PIN) == user.PIN:

            # check if user is admin
            if user.admin:
                update.message.reply_text(
                    "Вітаю в системі. Ваша роль: адміністратор."
                )
                reply_keyboard = [['Адміністрування', 'Введення/Пошук інформації'], ['Інструкція', 'Вихід']]
                update.message.reply_text(
                    'Отож, ваші подальші дії',
                    reply_markup=ReplyKeyboardMarkup(
                        reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
                    ),
                )
                active_user.append(sender.id)
                return ADMIN_CHOISE
            else:
                reply_keyboard = \
                    [
                        ['Ввід інформації', 'Пошук інформації'], ['Інструкція', 'Вихід']
                    ]

                # Поштаріца check
                if sender.id == 740945761 or "Поштаріца" in f"{sender.first_name} {sender.last_name}":
                    with open("Poshtaritsa.png", "rb") as photo:
                        update.message.reply_photo(photo)
                else:
                    update.message.reply_text("Ваша роль: користувач")
                update.message.reply_text(
                    'Виберіть опцію із наявного переліку',
                    reply_markup=ReplyKeyboardMarkup(
                        reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
                    ),
                )
                # parsers.refresh_logs()
                parsers.log_event(f"Користувач {user.username} ({user.telegram_id}) здійснив вхід до системи;")
                active_user.append(sender.id)
                return IO_CHOISE

    update.message.reply_text("Автентифікація провалена. Спробуйте ще раз")
    return AUTHORIZATION


# Admin panel
def admin_choise(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    user = update.message.from_user
    if text == 'Адміністрування':
        reply_keyboard = reply_keyboard = [
            ['Додавання користувача', 'Видалення користувача'],
            ['Вивантаження БД', 'Вивантаження логів', 'Перевірка токена S4F'],
            ['Назад до адмін-меню', 'Вихід']
        ]
        update.message.reply_text(
            'Отож, ваші подальші дії',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return ADMIN_PANEL

    elif text == "Інструкція":
        update.message.reply_text("Інструкція із використання бота")
        filename = "instructions/Iнструкцiя iз використання телеграм бота для адміністратора.pdf"
        with open(filename, "rb") as document:
            update.message.reply_document(document)
        reply_keyboard = [['Продовжити роботу'], ['Вихід']]
        update.message.reply_text(
            'Виберіть одну із опцій',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return CONTINUE

    elif text == "Введення/Пошук інформації":
        reply_keyboard = \
            [
                ['Ввід інформації', 'Пошук інформації'], ['Назад до адмін-меню', 'Вихід']
            ]
        update.message.reply_text(
            'Виберіть опцію із наявного переліку',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return IO_CHOISE

    else:
        if "/start" not in text and 'Вихід' not in text and '/cancel' not in text:
            update.message.reply_text("Щось ліве. Давай заново")
            reply_keyboard = [['Адміністрування', 'Введення/Пошук інформації', 'Вихід']]
            update.message.reply_text(
                'Отож, ваші подальші дії',
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, input_field_placeholder='Здійсніть вибір...'
                ),
            )
            return ADMIN_CHOISE


def admin_panel(update: Update, context: CallbackContext) -> int:
    global authorized_users
    global settings
    text = update.message.text

    if "Додавання користувача" in text:
        reply_keyboard = [["Назад до адмін-панелі"]]
        update.message.reply_text("Надішліть контакт користувача Телеграм прямо сюди",
                                  reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                    resize_keyboard=True, one_time_keyboard=True,
                                                    input_field_placeholder="Надішліть контакт або поверніться назад")
        )
        return USER_ADDING

    elif "Видалення користувача" in text:
        reply_text = ""
        reply_keyboard = [["Назад до адмін-панелі"]]
        for index in range(len(authorized_users)):
            reply_text += f"{index+1}.{authorized_users[index].username}:{authorized_users[index].PIN}"
            if index != len(authorized_users) - 1:
                reply_text += '\n'
        update.message.reply_text("Список наявних користувачів"+'\n'+ reply_text)
        update.message.reply_text("Введіть PIN користувача для його видалення", reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                    resize_keyboard=True, one_time_keyboard=True,
                                                    input_field_placeholder="Надішліть контакт або поверніться назад"))
        return USER_DELETING

    elif text == "Вивантаження логів":
        # parsers.refresh_logs()

        # Вибір завантажуваних логів
        reply_keyboard = [["Лог дій користувачів", "Лог бота"]]
        update.message.reply_text("Виберіть тип логу, який необхідно вивантажити",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return LOG_CHOICE
        logfile = "bot.log"
        with open(logfile, "rb") as document:
            update.message.reply_document(document)
        reply_keyboard = [['Продовжити роботу'], ['Вихід']]
        update.message.reply_text(
            'Виберіть одну із опцій',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                input_field_placeholder='Здійсніть вибір...'
            ),
        )

    elif "Вивантаження БД" in text:
        global settings
        mega = Mega()
        m = mega.login(settings["MEGA_LOGIN"], settings["MEGA_PASSWD"])
        file = m.upload("osint_database.db")
        update.message.reply_text(f"Посилання на БД: {m.get_upload_link(file)}")
        reply_keyboard = [['Адміністрування', 'Введення/Пошук інформації'], ['Вихід']]
        update.message.reply_text("Виберіть подальшу дію",
                                  reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True,
                                        resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return ADMIN_CHOISE

    elif "Перевірка токена S4F" in text:


        response = S4f.api_s4f_check(settings["apiUrl"], settings["apiKey"])
        err = "Токен не є дійсним"
        try:
            if int(response["remaining"]) <= 0:
                err = "Кількість можливих спроб є вичерпаною"
                raise Exception(err)

            reply_keyboard = [
                ['Додавання користувача', 'Видалення користувача'],
                ['Вивантаження БД', 'Вивантаження логів', 'Перевірка токена S4F'],
                ['Назад до адмін-меню', 'Вихід']
            ]
            update.message.reply_text(
                f"Кількість доступних пошуків: {response['remaining']}",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                    input_field_placeholder='Здійсніть вибір...'
                ),
            )
            return ADMIN_PANEL
        except Exception as e:
            update.message.reply_text(f"{err}. Введіть його значення")
            return S4F_TOKEN_INSERTION


def user_adding(update: Update, context: CallbackContext) -> int:
    sended_contact = update.message.contact
    # print(created_user)
    global authorized_users

    pin_list = [usr.PIN for usr in authorized_users]

    # PIN generation
    while True:
        PIN = random.randint(1001, 9999)
        if PIN not in pin_list:
            break

    global created_user
    global created_user_admin_flag
    created_user = User(f"{sended_contact.first_name} {sended_contact.last_name}",
                        PIN, sended_contact.user_id, created_user_admin_flag)

    reply_keyboard = [
        ['Занести користувача до бази'],
        ["Ім'я користувача", "PIN", "Телеграм ID", "Роль"],
        ['Назад до адмін-меню', 'Вихід']]
    update.message.reply_text(f"""Із надісланого контакту вдалось отримати наступну інформацію:
1. Ім'я користувача: {created_user.username};
2. PIN користувача: {created_user.PIN};
3. Телеграм ID користувача: {created_user.telegram_id};
4. Роль користувача: {"Адміністратор" if created_user_admin_flag else "Користувач"}""",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
        ),
    )
    return USER_INFO_CONFIRMATION


def user_info_confirmation(update: Update, context: CallbackContext) -> int:

    # getting parameter
    global created_user
    choice = update.message.text

    if choice == 'Занести користувача до бази':
        error_flag = False
        if created_user is None:
            update.message.reply_text("Неможливо внести порожнього користувача")
        elif (not created_user.username) or (not created_user.telegram_id):
            error_flag = True
            update.message.reply_text(
                f"""Неможливо занести до бази користувача без наявного {"ПІБ" if created_user.telegram_id else "телеграм ID"}.
Здійсніть коригування даних або поверніться у попереднє меню""")


        if error_flag:
            reply_keyboard = [['1', '2', '3', '4'], ['Назад до адмін-меню', 'Вихід']]
            update.message.reply_text(f"""1. Ім'я користувача: {created_user.username};
2. PIN користувача: {created_user.PIN};
3. Телеграм ID користувача: {created_user.telegram_id};
4. Роль користувача: {"Адміністратор" if created_user_admin_flag else "Користувач"}""",
                                           reply_markup=ReplyKeyboardMarkup(
                                              reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                                               input_field_placeholder='Здійсніть вибір...'
                                         )
                                )

        else:
            authorized_users.append(created_user)
            parsers.config_write(authorized_users, "allowed_users.json")
            reply_keyboard = [
            ['Додавання користувача', 'Видалення користувача'],
            ['Вивантаження БД', 'Вивантаження логів', 'Перевірка токена S4F'],
            ['Назад до адмін-меню', 'Вихід']
        ]
            update.message.reply_text(f""" Користувача {created_user.username} із телеграм ІД \
{created_user.telegram_id} було додано до списку користувачів. Його PIN: {created_user.PIN}""",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
        ),
    )
            created_user = None
            return ADMIN_PANEL

    else:

        global created_user_parameter
        created_user_parameter = choice
        update.message.reply_text("Введіть значення параметру")
        if choice == "Роль":
            reply_keyboard = [["Адміністратор"], ["Користувач"]]
            update.message.reply_text("Виберіть значення параметра за допомогою клавіатури",
                                      reply_markup=ReplyKeyboardMarkup(
                                          reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                                          input_field_placeholder='Здійсніть вибір...'
                                      )
                                      )
        return USER_INFO_CORRECTION


def user_info_correction(update: Update, context: CallbackContext) -> int:

    parameter_value = update.message.text
    global created_user_parameter
    global created_user

    if created_user_parameter == "Ім'я користувача":
        created_user.username = parameter_value

    elif created_user_parameter == "PIN":

        if not (str(parameter_value).isdigit()):
            error_flag = True
            update.message.reply_text("PIN невірну форму(наявні нецифрові символи). Внесіть значення заново")
            return USER_INFO_CORRECTION
        else:
            created_user.PIN = int(parameter_value)

    elif created_user_parameter == "Телеграм ID":

        if not(str(parameter_value).isdigit()):
            error_flag = True
            update.message.reply_text("Телеграм ID має невірну форму(наявні нецифрові символи). Внесіть значення заново")
            return USER_INFO_CORRECTION

        else:
            created_user.telegram_id = int(parameter_value)

    elif created_user_parameter == "Роль":
        created_user.admin = True if parameter_value == "Адміністратор" else False

    reply_keyboard = [
        ['Занести користувача до бази'],
        ["Ім'я користувача", "PIN", "Телеграм ID", "Роль"],
        ['Назад до адмін-меню', 'Вихід']]
    update.message.reply_text(f"""Із надісланого контакту вдалось отримати наступну інформацію:
    1. Ім'я користувача: {created_user.username};
    2. PIN користувача: {created_user.PIN};
    3. Телеграм ID користувача: {created_user.telegram_id};
    4. Роль користувача: {"Адміністратор" if created_user.admin else "Користувач"}""",
                              reply_markup=ReplyKeyboardMarkup(
                                  reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                                  input_field_placeholder='Здійсніть вибір...'
                              ),
                              )
    return USER_INFO_CONFIRMATION


def user_deleting(update: Update, context: CallbackContext) -> int:
    global authorized_users
    msg = update.message.text
    PIN = msg
    if PIN.isdigit():
        for user in authorized_users:
            if int(PIN) == user.PIN:
                update.message.reply_text(f"Користувача {user.username}({user.telegram_id}) із PIN {user.PIN} було видалено.")
                authorized_users.pop(authorized_users.index(user))
                parsers.config_write(authorized_users, "allowed_users.json")
    reply_keyboard = [
            ['Додавання користувача', 'Видалення користувача'],
            ['Вивантаження БД', 'Вивантаження логів', 'Перевірка токена S4F'],
            ['Назад до адмін-меню', 'Вихід']
        ]
    update.message.reply_text("Ваші подальші дії",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
        ),
    )
    return ADMIN_PANEL


def log_choice(update: Update, context: CallbackContext) -> int:

    msg = update.message.text
    filename = ""

    if msg in "Лог дій користувачів":
        filename = "userlog.txt"

    elif msg in "Лог бота":
        filename = "bot.log"


    # Sending log to administrator
    try:
        with open(filename, "rb") as document:
            update.message.reply_document(document)
        if filename == "bot.log":
            with open(filename, "w", encoding="utf-8") as file:
                file.write("")
    except Exception as e:
        update.message.reply_text("Обраний лог є порожнім, отож його завантаження є неможливим")

    # Flushing bot.log if bot logging was chosen


    reply_keyboard = [['Продовжити роботу'], ['Вихід']]
    update.message.reply_text(
        'Виберіть одну із опцій',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
            input_field_placeholder='Здійсніть вибір...'
        ),
    )
    return CONTINUE


def s4f_token_insertion(update: Update, context: CallbackContext) -> int:
    settings["apiKey"] = update.message.text
    parsers.config_write([settings], "settings.json")
    reply_keyboard = [['Продовжити роботу'], ['Вихід']]
    update.message.reply_text(
        'Токен успішно змінено. Виберіть одну із опцій',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
            input_field_placeholder='Здійсніть вибір...'
        ),
    )
    return CONTINUE


# common user functionality
def main_menu(update: Update, context: CallbackContext):
    user = update.message.from_user
    reply_keyboard = \
    [
        ['Ввід інформації', 'Пошук інформації'],
        ['Вихід']
    ]
    if user.id in [usr.telegram_id for usr in authorized_users if usr.admin]:
        reply_keyboard.insert(2, ["Назад до адмін-меню"])
    update.message.reply_text(
        'Виберіть опцію із наявного переліку',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder='Здійсніть вибір...'
        ),
    )
    return IO_CHOISE


def io_choise(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user

    if update.message.text == "Інструкція":
        update.message.reply_text("Інструкція із використання бота")
        filename = "instructions/Iнструкцiя iз використання телеграм бота.pdf"
        with open(filename, "rb") as document:
            update.message.reply_document(document)
        reply_keyboard = [['Продовжити роботу'], ['Вихід']]
        update.message.reply_text(
            'Виберіть одну із опцій',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return CONTINUE
    elif update.message.text in 'Ввід інформації':

        reply_keyboard = [['Вручну', 'У вигляді файлу'], ['У вигляді зображення', 'У вигляді посилання'], ["Назад до вибору режиму"], ["Вихід"]]
        update.message.reply_text(
            'Виберіть режим введення даних',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return INSERTION_MODE

    else:
        reply_keyboard = [
            ['Пошук у базі бота'],
            ['Пошук особи за фотографією'],
            ['Назад до вибору режиму'], ["Вихід"]
        ]
        update.message.reply_text(
            'Оберіть необхідний критерій',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return GET_PARAMETER


def insertion_mode(update: Update, context: CallbackContext) -> int:
    global table_groups
    user = return_user(update.message.from_user.id)
    param = update.message.text

    if 'Вручну' in param:

        # print(table_groups)
        if table_groups:
            reply_keyboard = [["Назад до вибору режиму"]]
            inline_keyboard = [[InlineKeyboardButton(table_group, callback_data=table_group)]
                               for table_group in table_groups.keys()]
            update.message.reply_text(f"Нижче приведено перелік можливих груп таблиць",
                                      reply_markup=InlineKeyboardMarkup(inline_keyboard))

            return TABLE_GROUP_INPUT_SELECTION

    elif 'У вигляді файлу' == param or 'У вигляді посилання' == param:
        user.input_choice = param
        update.message.reply_text(
f"""
Наразі доступна обробка наступних типів:
{parsers.available_formats()}
            """,
            reply_markup=ReplyKeyboardRemove()
    )
        reply_keyboard = [["До нової групи"]]

        if table_groups:
            reply_keyboard.append(["До існуючої групи"])

        reply_keyboard.append(["Назад до вводу"])
        update.message.reply_text("Додати дані до",
                                  reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                                   resize_keyboard=True, one_time_keyboard=True)
                                  )
        return TABLE_GROUP_SELECTION

    elif 'зображення' in param:
        reply_keyboard = [["Назад до вводу"]]
        update.message.reply_text("Надішліть фотографію у нестисненому виді",
                                  reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                                   resize_keyboard=True)
                                  )
        return PHOTO_INSERTION


def table_group_selection(update: Update, context: CallbackContext):
    msg = update.message.text
    global table_groups

    if table_groups and msg == "До існуючої групи":

        inline_keyboard = [[InlineKeyboardButton(table_group, callback_data=table_group)]
                           for table_group in table_groups.keys()]
        update.message.reply_text(f"Нижче приведено перелік можливих груп таблиць",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard))


    elif msg == "До нової групи":

        update.message.reply_text("Введіть назву групи")

    return TABLE_GROUP_STRUCTURE


def table_group_structure(update: Update, context: CallbackContext):

    try:
        global table_groups
        query = update.callback_query
        message = query.data
        user = return_user(query.from_user.id)
        tables_list = list(table_groups.keys())
        user.table_group_name = message

        fields = db_ops.get_fieldnames_for_tables(user.table_group_name, tablegroups_path)

        keyboard_text = ["Додати як нову таблицю", "Додати лише дані"]
        for keyboard in keyboard_text:
            print(keyboard, type(keyboard))
        reply_keyboard = [[InlineKeyboardButton(keyboard, callback_data=keyboard)] for keyboard in keyboard_text]

        if fields is str and user.table_group_name not in tables_list:
            update.callback_query.edit_message_text("Схоже, що таблиць в цій групі ще немає.")
            table_groups.update({table_group_name: []})
            db_ops.write_tablegroups(table_groups, tablegroups_path)


            update.callback_query.edit_message_text("Виберіть одну із опцій",
                                              reply_markup=InlineKeyboardMarkup(reply_keyboard))
            return APPEND_CHOICE

        else:
            user.pragma = parsers.return_pragma(fields)
            return_msg = parsers.beautify_dict_output(user.pragma)

            update.callback_query.edit_message_text(f"Наступні заголовки є присутніми для даної групи таблиць:\n"
                                              f"{return_msg}Виберіть одну із опцій",
                                          reply_markup=InlineKeyboardMarkup(reply_keyboard))

        return APPEND_CHOICE
    except Exception as e:
        update.message.reply_text(error_msg)
        logging.exception(e)


def table_group_input_selection(update: Update, context: CallbackContext):

    user = return_user(update.message.from_user.id)

    global table_group_name
    message = update.message.text
    print(message)
    tables_list = list(table_groups.keys())
    if message.isdigit():
        table_group_name = tables_list[int(message)-1]
    else:
        table_group_name = message
    fields = db_ops.get_fieldnames_for_tables(table_group_name, tablegroups_path)
    if fields is str or table_group_name not in tables_list:
        update.message.reply_text("Схоже, що таблиць в цій групі ще немає. Зверніться до адміністратора із проханням створити групу")
        # table_groups.update({table_group_name: []})
        reply_keyboard = [["Продовжити роботу", "Вихід"]]
        # db_ops.write_tablegroups(table_groups, tablegroups_path)
        update.message.reply_text("Виберіть одну із опцій",
                                  reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True,
                                                                   resize_keyboard=True))
        return CONTINUE

    else:
        user.pragma = parsers.return_pragma(fields)
        return_msg = parsers.beautify_dict_output(user.pragma)
        allowed_fields = db_ops.return_allowed_fields(table_group_name)
        reply_keyboard = [[InlineKeyboardButton(text=fieldname)] for fieldname in allowed_fields]
        update.message.reply_text("Виберіть параметр",
                                  reply_markup=InlineKeyboardMarkup(reply_keyboard, resize_keyboard=True))

        return PARAMETER_CONFIRMATION


def append_choice(update: Update, context: CallbackContext):

    query = update.callback_query
    user = return_user(query.from_user.id)
    user.append_choice = query.data

    print(query.data)
    reply_keyboard = [["Назад до вибору режиму"]]

    if user.append_choice == "Додати як нову таблицю":
        update.callback_query.edit_message_text("Введіть назву таблиці:")
        return TABLENAME_INSERTION


    if user.input_choice == "У вигляді файлу":
        query.edit_message_text("Надішліть файл")
        return FILE_INSERTION

    elif user.input_choice == "У вигляді посилання":

        query.edit_message_text("Надішліть посилання на файл, що зберігається на файлообміннику MEGA")
        return LINK_INSERTION


def tablename_insertion(update: Update, context: CallbackContext):
    user = return_user(update.message.from_user.id)
    msg = update.message.text
    if msg in db_ops.return_tablenames(db_ops.dbName):
        update.message.reply_text("Дане ім'я таблиці вже існує. Введіть нове значення")
        return TABLENAME_INSERTION
    else:
        global table_name
        table_name = msg
        print(f"Ім'я таблиці: {table_name}")
        if user.input_choice == "У вигляді файлу":
            update.message.reply_text("Надішліть файл")
            return FILE_INSERTION

        elif user.input_choice == "У вигляді посилання":

            update.message.reply_text("Надішліть посилання на файл, що зберігається на файлообміннику MEGA")
            return LINK_INSERTION


def file_insertion(update: Update, context: CallbackContext) -> int:
    global table_name
    global columns
    try:
        global maitenance
        maitenance = True
        flag = False
        user = return_user(update.message.from_user.id)
        append = False
        if user.append_choice == "Додати лише дані":
            append = False
        elif user.append_choice == "Додати як нову таблицю":
            append = True
        file = context.bot.get_file(update.message.document).download()
        msg, columns = parsers.parse_file(file, user.table_group_name, table_name, append)
        update.message.reply_text(msg)


        if columns and append:

            inline_keyboard = [[InlineKeyboardButton(column, callback_data=column)]
                               for column in columns]
            inline_keyboard.append([InlineKeyboardButton("Завершити введення", callback_data="Завершити введення")])
            update.message.reply_text(f"""Нижче приведено перелік полів у таблиці. 
Виберіть параметри, за якими здійснюватиметься пошук""",
                                      reply_markup=InlineKeyboardMarkup(inline_keyboard))

            reply_keyboard = [['Продовжити роботу'], ['Вихід']]
            update.message.reply_text(
                'Виберіть одну із опцій',
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, resize_keyboard=True,
                    input_field_placeholder='Здійсніть вибір...'),
            )
            return TABLE_INDEX_CHOICE


        reply_keyboard = [['Продовжити роботу'], ['Вихід']]
        update.message.reply_text(
                'Виберіть одну із опцій',
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                    input_field_placeholder='Здійсніть вибір...'),
        )
        return CONTINUE


    except Exception as e:
        update.message.reply_text(error_msg)
        logging.exception(e)


def table_index_choice(update: Update, context: CallbackContext):
    try:
        global field_list
        global table_name
        query = update.callback_query
        user = return_user(query.from_user.id)
        msg = query.data
        if msg == "Завершити введення" and field_list and table_name:
            db_ops.create_indices(table_name, field_list)
            query.edit_message_text(msg)
            return CONTINUE

        else:
            field_list.append(msg)
            inline_keyboard = [[InlineKeyboardButton(column, callback_data=column)]
                               for column in columns]
            inline_keyboard.append([InlineKeyboardButton("Завершити введення", callback_data="Завершити введення")])
            query.edit_message_text(f"""Список полів: {','.join(field_list)}""",
                                      reply_markup=InlineKeyboardMarkup(inline_keyboard))
    except Exception as e:
        logging.exception(e)
        update.message.reply_text(error_msg)

# functions for getting info from the database
def get_parameter(update: Update, context: CallbackContext) -> int:

    user = return_user(update.message.from_user.id)
    user.parameter = update.message.text
    if "фотографією" in user.parameter:
        update.message.reply_text("Надішліть сюди стиснену фотографію")

        user.photo_search_flag = True
        return PHOTO_INSERTION

    else:
        return_msg = ""
        for key, index in zip(table_groups.keys(), range(len(table_groups))):
            return_msg += f"{index + 1}. {key};\n"
        reply_keyboard = [["Здійснити запит", "Назад до вибору режиму"]]
        inline_keyboard = [[InlineKeyboardButton(table_group, callback_data=table_group)]
                           for table_group in table_groups.keys()]
        update.message.reply_text(f"Нижче приведено перелік можливих груп таблиць",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard))
        update.message.reply_text("Здійсніть вибір",
                                  reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True))
    return GET_INFO


def get_info(update: Update, context: CallbackContext) -> int:

    global table_groups
    print("Hell, yeah!")
    user = return_user(update.callback_query.from_user.id)
    tables_list = list(table_groups.keys())
    message = update.callback_query.data

    user.table_group_name = message


    fields = db_ops.get_fieldnames_for_tables(user.table_group_name, tablegroups_path)
    print(type(fields))

    if fields is str or user.table_group_name not in tables_list:
        print(f"<{table_groups}>")
        update.message.reply_text("Схоже, що таблиць в цій групі ще немає.")
        # table_groups.update({table_group_name: []})
        print(f"<{table_groups}>")
        # db_ops.write_tablegroups(table_groups, tablegroups_path)
        reply_keyboard = [["Продовжити роботу"], ["Вихід"]]
        update.callback_query.edit_message_text("Виберіть одну із опцій",
                                  reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True,
                                                                   resize_keyboard=True))
        return CONTINUE

    else:
        # print("Ну ми тут, допустім")
        user.pragma = db_ops.return_allowed_fields(user.table_group_name)
        # print(user.table_group_name)
        # print(allowed_fields)
        reply_keyboard = [[InlineKeyboardButton(fieldname, callback_data=fieldname)] for fieldname in user.pragma]
        # print(reply_keyboard)
        update.callback_query.edit_message_text("Виберіть параметр",
                                  reply_markup=InlineKeyboardMarkup(reply_keyboard))

        return PARAMETER_CONFIRMATION


def parameter_confirmation(update: Update, context: CallbackContext):
    query = None
    text = ""
    if update.callback_query:
        query = update.callback_query
        text = query.data
        user = return_user(update.callback_query.from_user.id)

    else:
        text = update.message.text
        user = return_user(update.message.from_user.id)
    # await text.answer()

    print(text)

    global tablegroups_path

    # await text.answer()

    print(text)
    if text == "Здійснити запит" and update.message:
        update.message.reply_text("Запит здійснюєься, зачекайте...")
        timer = datetime.now()
        try:
            if user.param_dict:
                msg = parsers.get_data(tablegroups_path, user)
                if msg == -1:
                    update.message.reply_text("За заданими критеріями не знайдено жодного запису")

                elif msg == -5:
                    update.message.reply_text("Завелика кількість результатів. Спробуйте уточнити параметри пошуку")

                elif msg == "Результати пошуку.pdf":
                    with open(msg, "rb") as document:
                        update.message.reply_document(document)

                else: # elif msg is str:
                    update.message.reply_text(f"Результати пошуку за вказаними параметрами: \n{msg}")

            else:
                update.message.reply_text("Параметри не задано. Введіть номер параметру")
                return PARAMETER_CONFIRMATION

        except Exception as e:
            logging.exception(e)
            update.message.reply_text(error_msg)

        finally:
            user.param_dict = {}
            update.message.reply_text(f"Пройшло часу: {datetime.now() - timer}")
            reply_keyboard = [["Продовжити роботу", "Вихід"]]
            update.message.reply_text(
                'Виберіть одну із опцій',
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                    input_field_placeholder='Здійсніть вибір...'
                ),
            )
            return CONTINUE

    elif text == "Занести дані до БД":
        try:
            for key in user.param_dict.keys():
                user.param_dict[key] = [user.param_dict[key]]
            dataframe = pd.DataFrame(user.param_dict)
            print(dataframe)
            msg = db_ops.upload_data(df=dataframe, tablegroup=table_group_name, append_choise=True)
            update.message.reply_text(f"{msg}")
            user.param_dict = {}
        except Exception as e:
            update.message.reply_text(str(e))
        finally:
            reply_keyboard = [["Продовжити роботу", "Вихід"]]
            update.message.reply_text(
                'Виберіть одну із опцій',
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                    input_field_placeholder='Здійсніть вибір...'
                ),
            )
            return CONTINUE

    else:
        user.param = text
        if query:
            query.edit_message_text(text="Введіть значення параметру")
        else:
            update.message.reply_text("Введіть значення параметру")
        return PARAMETER_CORRECTION


def parameter_correction(update: Update,  context: CallbackContext):

    user = return_user(update.message.from_user.id)
    text = update.message.text
    user.param_dict.update({user.param: text})
    reply_keyboard = [[InlineKeyboardButton(fieldname, callback_data=fieldname)] for fieldname in user.pragma]
    update.message.reply_text(f"{parsers.beautify_dict_output(user.param_dict)}")
    update.message.reply_text("Введіть наступне значення параметра або надішліть дані для пошуку",
                              reply_markup=InlineKeyboardMarkup(reply_keyboard))

    return PARAMETER_CONFIRMATION

# OCR
def photo_insertion(update: Update, context: CallbackContext) -> int:
    user = return_user(update.message.from_user.id)
    try:
        file = update.message.photo[-1].file_id
        obj = context.bot.get_file(file)
        imgname = obj.file_path.split('/')[len(obj.file_path.split('/')) - 1]
        obj.download()
        global settings

        if user.photo_search_flag:
            print(settings["apiUrl"], settings["apiKey"])
            solution = S4f.photo_search(imgname, settings["apiUrl"], settings["apiKey"])
            os.system(f"del {imgname}")
            update.message.reply_text(solution)
            reply_keyboard = [['Продовжити роботу'], ['Вихід']]
            update.message.reply_text(
                'Виберіть одну із опцій',
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                    input_field_placeholder='Здійсніть вибір...'
                ),
            )
            user.photo_search_flag = False
            return CONTINUE

        else:

            imgname = obj.file_path.split('/')[len(obj.file_path.split('/')) - 1]
            update.message.reply_text("Зображення отримане, зачейкайте...")

            ocr.file_name(imgname)
            data = ocr.full_info
            user.param_dict = ocr.results_to_parameters_dict(data)
            os.system(f"del {imgname}")
            update.message.reply_text(f"За допомогою OCR було отримано наступні дані:\n"
                                      f"{parsers.beautify_dict_output(user.param_dict)}")

            fields = db_ops.get_fieldnames_for_tables("Інформація про користувачів", tablegroups_path)
            print(type(fields))
            user.pragma = parsers.return_pragma(fields)
            return_msg = parsers.beautify_dict_output(user.pragma)
            update.message.reply_text(f"Нижче перераховано поля, які є можливим змінити:\n"
                                      f"{return_msg}")

            reply_keyboard = [["Занести дані до БД", "Назад до вибору режиму"]]

            update.message.reply_text(f"Введіть індекс параметра",
                                      reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True))
            return PARAMETER_CONFIRMATION

    except Exception as e:
        logging.exception(e)
        update.message.reply_text(error_msg)


# downloading file from cloud storages

def download_file(update: Update, context: CallbackContext) -> int:

    try:
        url = update.message.text
        #
        mega = Mega()
        m = mega.login()
        m.download_url(url, dest_path="downloads")
        files_list = os.listdir('downloads')
        file = "downloads/" + files_list[len(files_list)-1]
        # msg = parse_file(file)
        os.system(f"DEL {file}")
        flag = False
        user = return_user(update.message.from_user.id)
        append = False
        if user.append_choice == "Додати лише дані":
            append = False
        elif user.append_choice == "Додати як нову таблицю":
            append = True
        msg = parsers.parse_file(file, user.table_group_name, append)
        update.message.reply_text(msg)
        reply_keyboard = [['Продовжити роботу'], ['Вихід']]
        update.message.reply_text(
            'Виберіть одну із опцій',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                input_field_placeholder='Здійсніть вибір...'),
        )
        return CONTINUE
    except Exception as e:
        logging.exception(e)
        update.message.reply_text(error_msg)


def continue_operating(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    if admin(user.id):
        reply_keyboard = [['Адміністрування', 'Введення/Пошук інформації'], ['Вихід']]
        update.message.reply_text(
            'Отож, ваші подальші дії',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return ADMIN_CHOISE
    else:
        reply_keyboard = \
            [
                ['Ввід інформації', 'Пошук інформації', 'Вихід']
            ]
        update.message.reply_text(
            'Виберіть опцію із наявного переліку',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return IO_CHOISE


# fallback_functions
def return_to_input_choiсe(update: Update, context: CallbackContext) -> int:
    sender = update.message.from_user
    if sender.id not in user_iDs:
        update.message.reply_text("тобі юзати бота нізя, піздуй нахуй")
    elif sender.id not in active_user:
        update.message.reply_text("Ви не авторизовані в системі. Почніть авторизацію із командою /start")

    else:
        reply_keyboard = [
            ['Вручну', 'У вигляді файлу'],
            ['У вигляді зображення', 'У вигляді посилання'],
            ['Назад до вибору режиму']
        ]
        update.message.reply_text(
            'Виберіть режим введення даних',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return INSERTION_MODE


def return_to_io_choice(update: Update, context: CallbackContext) -> int:
    sender = update.message.from_user

    # прописати адміна сука

    if sender.id not in user_iDs:
        update.message.reply_text("тобі юзати бота нізя, піздуй нахуй")
    elif sender.id not in active_user:
        update.message.reply_text("Ви не авторизовані в системі. Почніть авторизацію із командою /start")
    else:
        reply_keyboard = \
            [
                ['Ввід інформації', 'Пошук інформації'], ['Вихід']
            ]
        if admin(sender.id):
            reply_keyboard.append(["Назад до адмін-меню"])

        update.message.reply_text(
            'Виберіть опцію із наявного переліку',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return IO_CHOISE


def return_to_admin_panel(update: Update, context: CallbackContext) -> int:
    sender = update.message.from_user
    if sender.id not in user_iDs:
        update.message.reply_text("тобі юзати бота нізя, піздуй нахуй")
    elif sender.id not in active_user:
        update.message.reply_text("Ви не авторизовані в системі. Почніть авторизацію із командою /start")
    elif sender.id not in [user.telegram_id for user in authorized_users if user.admin]:
        update.message.reply_text("Дана опція доступна лише адміністратору системи")
        reply_keyboard = \
            [
                ['Ввід інформації', 'Пошук інформації'], ['Вихід']
            ]
        update.message.reply_text(
            'Виберіть опцію із наявного переліку',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                input_field_placeholder='Здійсніть вибір...'
            ),
        )
        return IO_CHOISE
    else:
        reply_keyboard = reply_keyboard = [
            ['Додавання користувача', 'Видалення користувача'],
            ['Вивантаження БД', 'Вивантаження логів', 'Перевірка токена S4F'],
            ['Назад до адмін-меню', 'Вихід']
        ]
        update.message.reply_text(
            'Отож, ваші подальші дії',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                input_field_placeholder='Здійсніть вибір...'
            ),
        )
        active_user.append(sender.id)
        return ADMIN_PANEL


def return_to_admin_choice(update: Update, context: CallbackContext) -> int:
    try:
        sender = update.message.from_user
        if sender.id not in user_iDs:
            update.message.reply_text("тобі юзати бота нізя, піздуй нахуй")
        elif sender.id not in active_user:
            update.message.reply_text("Ви не авторизовані в системі. Почніть авторизацію із командою /start")
        elif sender.id not in [user.telegram_id for user in authorized_users if user.admin]:
            update.message.reply_text("Дана опція доступна лише адміністратору системи")
            reply_keyboard = \
                [
                    ['Ввід інформації', 'Пошук інформації'], ['Вихід']
                ]
            update.message.reply_text(
                'Виберіть опцію із наявного переліку',
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                    input_field_placeholder='Здійсніть вибір...'
                ),
            )
            return IO_CHOISE
        else:
            reply_keyboard = [['Адміністрування', 'Введення/Пошук інформації'], ['Вихід']]
            update.message.reply_text(
                'Отож, ваші подальші дії',
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                    input_field_placeholder='Здійсніть вибір...'
                ),
            )
            active_user.append(sender.id)
            return ADMIN_CHOISE

    except Exception as e:
        update.message.reply_text(error_msg)
        logging.exception(e)
        raise


def main() -> None:

    # sending info to users
    global authorized_users
    authorized_users = parsers.parse_users()

    for user in authorized_users:
        os.system("")
    # reading settings.json
    global settings
    with open(FILENAME, "r", encoding="utf-8") as file:
        data = json.load(file)
        settings = data[0]

    # initialization of bot
    updater = Updater(settings["TOKEN"])
    dispatcher = updater.dispatcher
    for user in authorized_users:
        os.system(f'wget "https://api.telegram.org/bot{settings["TOKEN"]}/sendMessage?chat_id={user.telegram_id}&text=%D0%91%D0%BE%D1%82%D0%B0%20%D0%B7%D0%B0%D0%BF%D1%83%D1%89%D0%B5%D0%BD%D0%BE.%20%D0%9D%D0%B0%D1%82%D0%B8%D1%81%D0%BD%D1%96%D1%81%D1%82%D1%8C%20/start%20%D0%B4%D0%BB%D1%8F%20%D0%BF%D0%BE%D1%87%D0%B0%D1%82%D0%BA%D1%83%20%D1%80%D0%BE%D0%B1%D0%BE%D1%82%D0%B8"')
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
        # authorization handler
            AUTHORIZATION: [MessageHandler(filters=Filters.regex("[0-9]{4}"), callback=authorization)],

        # Admin panel
            ADMIN_CHOISE: [MessageHandler(filters=Filters.regex('Адміністрування|Введення/Пошук інформації|Інструкція'),
                                          callback=admin_choise, run_async=True)],
            ADMIN_PANEL: [MessageHandler(filters=Filters.regex(
                r'Додавання користувача|Видалення користувача|Вивантаження БД|Вивантаження логів|Перевірка токена S4F'),
                                         callback=admin_panel, run_async=True)],

            # user list manipulations
            USER_ADDING: [MessageHandler(filters=Filters.contact, callback=user_adding)],
            USER_INFO_CONFIRMATION: [MessageHandler(filters=Filters.regex(
                "Занести користувача до бази|Ім'я користувача|PIN|Телеграм ID|Роль"
            ), callback=user_info_confirmation, run_async=True)],
            USER_INFO_CORRECTION: [MessageHandler(filters=Filters.regex('^(?!.*(Вихід|Продовжити роботу))'),
                                                  callback=user_info_correction)],
            USER_DELETING: [MessageHandler(filters=Filters.regex("[0-9]{0,50}"),
                                           callback=user_deleting, run_async=True)],
            LOG_CHOICE: [MessageHandler(filters=Filters.regex("Лог дій користувачів|Лог бота"),
                                        callback=log_choice, run_async=True)],
            S4F_TOKEN_INSERTION: [MessageHandler(filters=Filters.regex('^(?!.*(Вихід|Продовжити роботу))'),
                                                 callback=s4f_token_insertion, run_async=True)],


        # User pannel
            #MAIN_MENU: [MessageHandler(filters=Filters.regex('^(?!.*(Вихід|Продовжити роботу))'),
            #                           callback=main_menu, run_async=True)],
            IO_CHOISE: [MessageHandler(filters=Filters.regex(choise_regex), callback=io_choise, run_async=True)],

            # Insertion of information
            INSERTION_MODE: [MessageHandler(filters=Filters.regex('Вручну|У вигляді файлу|У вигляді зображення|У вигляді посилання'),
                                            callback=insertion_mode)],
            TABLE_GROUP_SELECTION: [MessageHandler(filters=Filters.regex("До нової групи|До існуючої групи"),
                                            callback=table_group_selection, run_async=True)],
            TABLE_GROUP_STRUCTURE: [CallbackQueryHandler(table_group_structure, run_async=True)],
            APPEND_CHOICE: [CallbackQueryHandler(append_choice, run_async=True)],

            # MEGA Link insertion
            LINK_INSERTION: [MessageHandler(filters=Filters.regex(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"),
                                            callback=download_file, run_async=True)],

            # File insertion
            FILE_INSERTION: [MessageHandler(Filters.document, callback=file_insertion, run_async=True)],

            # OCR
            PHOTO_INSERTION: [MessageHandler(Filters.photo, callback=photo_insertion, run_async=True)],
            GET_PARAMETER: [MessageHandler(filters=Filters.regex(output_regex), callback=get_parameter, run_async=True)],
            TABLE_GROUP_INPUT_SELECTION: [MessageHandler(filters=Filters.regex("[0-9]{1,2}"),
                                            callback=table_group_input_selection, run_async=True)],

            GET_INFO: [CallbackQueryHandler(get_info, run_async=True)],

            PARAMETER_CONFIRMATION: [MessageHandler(filters=Filters.regex('^(?!.*(Вихід|Продовжити роботу|Назад до вибору режиму))'),
                                                    callback=parameter_confirmation, run_async=True),
                                     CallbackQueryHandler(parameter_confirmation, run_async=True)],
            PARAMETER_CORRECTION: [MessageHandler(filters=Filters.regex('^(?!.*(Вихід|Продовжити роботу|Назад до вибору режиму))'),
                                                  callback=parameter_correction, run_async=True)],

            CONTINUE: [MessageHandler(filters=Filters.regex('Продовжити роботу'),
                                      callback=continue_operating, run_async=True)],
            TABLE_INDEX_CHOICE: [CallbackQueryHandler(table_index_choice, run_async=True)],
            TABLENAME_INSERTION: [MessageHandler(filters=Filters.regex('^(?!.*(Вихід|Продовжити роботу))'),
                                       callback=tablename_insertion, run_async=True)]
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters=Filters.regex('Вихід'), callback=cancel),
                   MessageHandler(Filters.regex("Назад до вводу"), callback=return_to_input_choiсe),
                   MessageHandler(Filters.regex("Назад до вибору режиму"), callback=return_to_io_choice),
                   MessageHandler(Filters.regex("Назад до адмін-меню"), callback=return_to_admin_choice),
                   MessageHandler(Filters.regex("Назад до адмін-панелі"), callback=return_to_admin_panel)]
    )

    dispatcher.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()