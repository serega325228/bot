import re
import uuid
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, or_f
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.bot.filters.is_admin import IsAdmin
from app.bot.keyboards.keyboards import admin_menu_keyboard, stops_keyboard, stops_management_keyboard, users_keyboard, users_management_keyboard
from app.models.user import User, UserRole
from app.services.ride import RideService

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin()) 

class AddUser(StatesGroup):
    waiting_for_forward = State()
    waiting_for_full_name = State()

class AddStop(StatesGroup):
    waiting_for_name = State()
    waiting_for_coordinates = State()
    waiting_for_order = State()

class ChangeUser(StatesGroup):
    waiting_for_field = State()
    waiting_for_role = State()
    waiting_for_is_active = State()
    waiting_for_nickname = State()
    waiting_for_full_name = State()

class ChangeStop(StatesGroup):
    waiting_for_field = State()
    waiting_for_name = State()
    waiting_for_coordinates = State()
    waiting_for_order = State()
    waiting_for_is_active = State()

class MenuState(StatesGroup):
    main_menu = State()
    stops_menu = State()
    users_menu = State()


async def go_to(state: FSMContext, new_state):
    data = await state.get_data()
    history = data.get("history", [])

    current = await state.get_state()
    if current:
        history.append(current)

    await state.update_data(history=history)
    await state.set_state(new_state)

async def show_menu(message: Message, state_name):
    match state_name:
        case MenuState.main_menu:
            await message.answer("Основное меню", reply_markup=admin_menu_keyboard())
        case MenuState.users_menu:
            await message.answer("Меню пользователей", reply_markup=users_management_keyboard())
        case MenuState.stops_menu:
            await message.answer("Меню остановок", reply_markup=stops_management_keyboard())

@router.message(Command("start"))
async def start_bot_handler(
    message: Message,
    state: FSMContext,
):
    await go_to(state, MenuState.main_menu)
    await show_menu(message, MenuState.main_menu.state)

@router.message(
    or_f(
        F.text == "Назад",
        Command("back")
    )
)
async def go_back_handler(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()
    history = data.get("history", [])

    if not history:
        await message.answer("Ты уже в главном меню")
        return
    
    previous = history.pop()

    await state.update_data(history=history)
    await state.set_state(previous)

    await show_menu(message, previous)

@router.message(
    or_f(
        Command("users_menu"),
        F.text == "Пользователи"
    )
)
async def get_users_menu_handler(
    message: Message,
    state: FSMContext
):
    await go_to(state, MenuState.users_menu)
    await show_menu(message, MenuState.users_menu.state)

@router.message(
    or_f(
        Command("users_list"),
        F.text == "Список пользователей"
    )
)
async def get_list_of_users_handler(
    message: Message,
    ride_service: RideService
):
    users = await ride_service.get_all_users()
    
    text = "👥 <b>Пользователи:</b>\n\n"
    
    for u in users:
        status = "✅" if u.is_active else "❌"
        role = "👑" if u.role == UserRole.ADMIN else "👤"
        text += f"{status} {role} @{u.nickname} {u.full_name}\n"
    
    await message.answer(text)

@router.message(
    or_f(
        Command("add_user"),
        F.text == "Добавить пользователя"
    )
)
async def add_user_start_handler(
    message: Message,
    state: FSMContext
):
    await state.set_state(AddUser.waiting_for_forward)
    await message.answer(
        "👤 <b>Добавление пользователя</b>\n\n"+
        "Перешлите сообщение от пользователя, которого нужно добавить.\n\n"+
        "Или отправь /cancel для отмены."
    )

@router.message(AddUser.waiting_for_forward)
async def add_user_waiting_forward_message_handler(
    message: Message,
    state: FSMContext,
    ride_service: RideService
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    if not message.forward_from and not message.forward_sender_name:
        await message.answer("❌ Нужно переслать сообщение от пользователя")
        return
    
    telegram_id = message.forward_from.id if message.forward_from else None
    nickname = message.forward_from.username if message.forward_from else None
    
    if not telegram_id:
        await message.answer("❌ Не удалось получить ID пользователя")
        return
    
    existing = await ride_service.get_user_by_id(id=telegram_id)
    if existing:
        await message.answer("❌ Пользователь с таким ID уже существует")
        await state.clear()
        return
    
    await state.update_data(id=telegram_id, nickname=nickname)

    await message.answer("Теперь введите ФИО")
    await state.set_state(AddUser.waiting_for_full_name)

@router.message(AddUser.waiting_for_full_name)
async def add_user_waiting_full_name_handler(
    message: Message,
    state: FSMContext,
    ride_service: RideService
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    data = await state.get_data()
    full_name = message.text

    if not full_name:
        await message.answer("Введите ФИО")
        return
    
    await ride_service.create_user(
        id=data["id"],
        nickname=data["nickname"],
        full_name=full_name,
    )
    
    await state.clear()
    await message.answer(
        f"✅ Пользователь добавлен!\n\n"
        f"👤 {full_name}\n"
    )

@router.message(
    or_f(
        Command("change_user_data"),
        F.text == "Изменить данные пользователя"
    )
)
async def select_change_user_handler(
    message: Message,
    ride_service: RideService
):
    users = await ride_service.get_all_users()

    await message.answer(
        "👤 Выберите пользователя:",
        reply_markup=users_keyboard(users, "admin_change_user")
    )

@router.callback_query(lambda c: c.data.startswith("admin_change_user:"))
async def select_change_user_field_handler(
    callback: CallbackQuery,
    state: FSMContext
):
    user_id = int(callback.data.split(":")[1])

    await state.set_state(ChangeUser.waiting_for_field)
    await state.update_data(user_id=user_id)

    await callback.message.edit_text("Выберите 1 из: роль, активен, фио, никнейм")
    
@router.message(ChangeUser.waiting_for_field)
async def change_user_field_handler(
    message: Message,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    field = str.lower(message.text)

    if field not in ["роль", "активен", "фио", "никнейм"]:
        await message.answer("Выберите поле из перечня")
        return
    
    match field:
        case "роль":
            await state.set_state(ChangeUser.waiting_for_role)
            await message.answer("Выберите новую роль: пассажир, админ, водитель")
        case "активен":
            await state.set_state(ChangeUser.waiting_for_is_active)
            await message.answer("Выберите новое состояние: да/нет")
        case "фио":
            await state.set_state(ChangeUser.waiting_for_full_name)
            await message.answer("Введите новое ФИО")
        case "никнейм":
            await state.set_state(ChangeUser.waiting_for_nickname)
            await message.answer("Введите новый никнейм")

@router.message(ChangeUser.waiting_for_role)
async def change_user_role_handler(
    message: Message,
    ride_service: RideService,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    role = str.lower(message.text)

    if role not in ["пассажир", "админ", "водитель"]:
        await message.answer("Выберите роль из перечня")
        return
    
    data = await state.get_data()

    match role:
        case "пассажир":
            await ride_service.make_passenger(id=data["user_id"])
        case "админ":
            await ride_service.make_admin(id=data["user_id"])
        case "водитель":
            await ride_service.make_driver(id=data["user_id"])

    await state.clear()
    await message.answer("✅ Роль успешно изменена")

@router.message(ChangeUser.waiting_for_is_active)
async def change_user_is_active_handler(
    message: Message,
    ride_service: RideService,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    answer = str.lower(message.text)

    if answer not in ["да", "нет"]:
        await message.answer("Выберите состояние из перечня")
        return
    
    data = await state.get_data()

    match answer:
        case "да":
            await ride_service.deactivate_user(id=data["user_id"])
            await message.answer("✅ Теперь пользователь активен")
        case "нет":
            await ride_service.activate_user(id=data["user_id"])
            await message.answer("❌ Теперь пользователь неактивен")

    await state.clear()

@router.message(ChangeUser.waiting_for_nickname)
async def change_user_nickname_handler(
    message: Message,
    ride_service: RideService,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    nickname = message.text

    data = await state.get_data()

    await ride_service.change_nickname(id=data["user_id"], nickname=nickname)

    await state.clear()
    await message.answer("✅ Никнейм успешно изменен")

@router.message(ChangeUser.waiting_for_full_name)
async def change_user_full_name_handler(
    message: Message,
    ride_service: RideService,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    full_name = message.text

    data = await state.get_data()

    await ride_service.change_full_name(id=data["user_id"], full_name=full_name)

    await state.clear()
    await message.answer("✅ ФИО успешно изменено")

@router.message(
    or_f(    
        Command("delete_user"),
        F.text == "Удалить пользователя"
    )
)
async def select_delete_user_handler(
    message: Message,
    ride_service: RideService
):
    users = await ride_service.get_all_users()

    await message.answer(
        "👤 Выберите пользователя:",
        reply_markup=users_keyboard(users, "admin_delete_user")
    )

@router.callback_query(lambda c: c.data.startswith("admin_delete_user:"))
async def delete_user_handler(
    callback: CallbackQuery, 
    ride_service: RideService,
):
    user_id = int(callback.data.split(":")[1])

    await ride_service.delete_user(id=user_id)

    await callback.message.edit_text("✅ Пользователь успешно удален")



@router.message(
    or_f(    
        Command("stops_menu"),
        F.text == "Остановки"
    )
)
async def get_stops_menu_handler(
    message: Message,
    state: FSMContext
):
    await go_to(state, MenuState.stops_menu)
    await show_menu(message, MenuState.stops_menu.state)

@router.message(
    or_f(
        Command("stops_list"),
        F.text == "Список остановок"
    )
)
async def get_all_stops_handler(
    message: Message,
    ride_service: RideService
):
    stops = await ride_service.get_all_stops()

    if not stops:
        await message.answer("Остановки не настроены")
        return
    
    text = "📍 <b>Остановки:</b>\n\n"
    
    for stop in sorted(stops, key=lambda s: s.order):
        status = "✅" if stop.is_active else "❌"
        text += f"{status} {stop.order}. {stop.name}\n"
    
    await message.answer(text, reply_markup=stops_management_keyboard())

@router.message(
    or_f(
        Command("add_stop"),
        F.text == "Добавить остановку"
    )
)
async def add_stop_start_handler(
    message: Message,
    state: FSMContext
):
    await state.set_state(AddStop.waiting_for_name)
    await message.answer(
        "📍 <b>Добавление остановки</b>\n\n"+
        'Введите название остановки\n'+
        "Или отправьте /cancel для отмены."
    )

@router.message(AddStop.waiting_for_name)
async def add_stop_waiting_name_handler(
    message: Message,
    state: FSMContext,
    ride_service: RideService
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    existing = await ride_service.get_stop_by_name(name=message.text)
    if existing:
        await message.answer("❌ Остановка уже добавлена")
        await state.clear()
        return
    
    await message.answer("Введите координаты остановки через пробел")
    
    await state.update_data(name=message.text)
    await state.set_state(AddStop.waiting_for_coordinates)

@router.message(AddStop.waiting_for_coordinates)
async def add_stop_waiting_coordinates_handler(
    message: Message,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    coordinates = list(map(float, message.text.replace(",", ".").split()))
    
    await message.answer("Введите порядковый номер остановки")

    await state.update_data(coordinates=coordinates)
    await state.set_state(AddStop.waiting_for_order)

@router.message(AddStop.waiting_for_order)
async def add_stop_waiting_order_handler(
    message: Message,
    state: FSMContext,
    ride_service: RideService
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    order = int(message.text)
    data = await state.get_data()

    await ride_service.create_stop(
        name=data["name"],
        latitude=data["coordinates"][0],
        longitude=data["coordinates"][1],
        order=order
    )
    
    await state.clear()
    await message.answer(
        f"✅ Остановка добавлен!\n\n"
        f"📍 {data["name"]}\n"
    )

@router.message(
    or_f(
        Command("change_stop"),
        F.text == "Изменить данные остановки"
    )
)
async def select_change_stop_handler(
    message: Message,
    ride_service: RideService
):
    stops = await ride_service.get_active_stops()

    await message.answer(
        "📍 Выберите остановку:",
        reply_markup=stops_keyboard(stops, "admin_change_stop")
    )

@router.callback_query(lambda c: c.data.startswith("admin_change_stop:"))
async def change_stop_handler(
    callback: CallbackQuery, 
    ride_service: RideService,
    state: FSMContext
):
    stop_id = int(callback.data.split(":")[1])

    await state.set_state(ChangeStop.waiting_for_field)
    await state.update_data(stop_id=stop_id)

    await callback.message.edit_text("Выберите 1 из: название, координаты, порядок, активная")

@router.message(ChangeStop.waiting_for_field)
async def change_stop_field_handler(
    message: Message,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    field = str.lower(message.text)

    if field not in ["название", "координаты", "порядок", "активная"]:
        await message.answer("Выберите поле из перечня")
        return
    
    match field:
        case "название":
            await state.set_state(ChangeStop.waiting_for_name)
            message.answer("Введите новое название")
        case "кооридинаты":
            await state.set_state(ChangeStop.waiting_for_coordinates)
            message.answer("Введите координаты через пробел")
        case "порядок":
            await state.set_state(ChangeStop.waiting_for_order)
            message.answer("Введите новые порядковый номер")
        case "активная":
            await state.set_state(ChangeStop.waiting_for_is_active)
            message.answer("Выберите да/нет")

@router.message(ChangeStop.waiting_for_name)
async def change_stop_name_handler(
    message: Message,
    ride_service: RideService,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    name = message.text

    data = await state.get_data()

    await ride_service.change_stop_name(id=data["stop_id"], name=name)

    await message.answer("Название успешно изменено")

    await state.clear()

@router.message(ChangeStop.waiting_for_coordinates)
async def change_stop_coordinates_handler(
    message: Message,
    ride_service: RideService,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    coordinates = list(map(float, message.text.split()))

    data = await state.get_data()

    await ride_service.change_stop_coordinates(
        id=data["stop_id"], 
        latitude=coordinates[0], 
        longitude=coordinates[1]
    )

    await message.answer("Координаты успешно изменены")

    await state.clear()

@router.message(ChangeStop.waiting_for_order)
async def change_stop_order_handler(
    message: Message,
    ride_service: RideService,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    order = int(message.text)

    data = await state.get_data()

    await ride_service.change_stop_order(
        id=data["stop_id"], 
        order=order
    )

    await message.answer("порядковый номер успешно изменен")

    await state.clear()

@router.message(ChangeStop.waiting_for_is_active)
async def change_stop_is_active_handler(
    message: Message,
    ride_service: RideService,
    state: FSMContext
):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    answer = str.lower(message.text)

    if answer not in ["да", "нет"]:
        await message.answer("Выберите состояние из перечня")
        return
    
    data = await state.get_data()

    match answer:
        case "да":
            await ride_service.deactivate_user(id=data["stop_id"])
            await message.answer("✅ Теперь остановка активена")
        case "нет":
            await ride_service.activate_user(id=data["stop_id"])
            await message.answer("❌ Теперь остановка неактивна")

    await state.clear()

@router.message(
    or_f(
        Command("delete_stop"),
        F.text == "Удалить остановку"
    )
)
async def select_delete_stop_handler(
    message: Message,
    ride_service: RideService
):
    stops = await ride_service.get_active_stops()

    await message.answer(
        "📍 Выберите остановку:",
        reply_markup=stops_keyboard(stops, "admin_delete_stop")
    )

@router.callback_query(lambda c: c.data.startswith("admin_delete_stop:"))
async def delete_stop_handler(
    callback: CallbackQuery, 
    ride_service: RideService,
):
    stop_id = uuid.UUID(callback.data.split(":")[1])

    await ride_service.delete_stop(id=stop_id)

    await callback.message.edit_text("✅ Остановка успешно удалена")

