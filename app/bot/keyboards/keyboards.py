from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

from app.models.stop import Stop
from app.models.user import User

def passenger_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Выбрать остановку")],
            [KeyboardButton(text="Мой билет")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие"
    )

def driver_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Выбрать следующую остановку")],
            [KeyboardButton(text="Включить геолокацию")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие"
    )

def admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Остановки")],
            [KeyboardButton(text="Пользователи")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие"
    )

def location_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="🚍 Начать поездку",
                request_location=True
            )]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )   

def stops_keyboard(stops: list[Stop], prefix: str):
    keyboard = []

    for stop in stops:
        keyboard.append([
            InlineKeyboardButton(
                text=stop.name,
                callback_data=f"{prefix}:{stop.id}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def users_keyboard(users: list[User], prefix: str):
    keyboard = []

    for user in users:
        keyboard.append([
            InlineKeyboardButton(
                text=user.full_name,
                callback_data=f"{prefix}:{user.id}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard) 

def ticket_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Я в автобусе")],
            [KeyboardButton(text="Отмена")]
        ]
    )

def backspace_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Остановки")],
            [KeyboardButton(text="Пользователи")]
        ]
    )

def users_management_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Список пользователей")],
            [KeyboardButton(text="Изменить данные пользователя")],
            [
                KeyboardButton(text="Добавить пользователя"), 
                KeyboardButton(text="Удалить пользователя")
            ],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие"
    )

def stops_management_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Список остановок")],
            [KeyboardButton(text="Изменить данные остановки")],
            [
                KeyboardButton(text="Добавить остановку"), 
                KeyboardButton(text="Удалить остановку")
            ],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие"
    )
