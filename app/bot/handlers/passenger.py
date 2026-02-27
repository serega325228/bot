import uuid
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards.keyboards import passenger_menu_keyboard, stops_keyboard, ticket_keyboard
from app.models.ticket import TicketStatus
from app.models.user import User, UserRole
from app.services.ride import RideService
from app.services.stop import StopService
from app.services.ticket import TicketService

router = Router()

@router.message(Command("start"))
async def start_bot_handler(
    message: Message,
    user: User,
):
    if user.role == UserRole.PASSENGER:
        await message.answer(
            f"✅ Добро пожаловать, <b>{user.full_name}</b>\n"
            f"Ваша роль: <b>{user.role}</b>",
            reply_markup=passenger_menu_keyboard()
        )

@router.message(Command("stops") or F.text == "Выбрать остановку")
async def get_stops_handler(
    message: Message,
    stop_service: StopService
):
    stops = await stop_service.get_active_stops()

    if not stops:
        await message.answer("Остановки не настроены.")
        return

    await message.answer(
        "📍 Выберите остановку:",
        reply_markup=stops_keyboard(stops, "passenger_select_stop")
    )

@router.callback_query(lambda c: c.data.startswith("passenger_select_stop:"))
async def passenger_stop_selected_handler(
    callback: CallbackQuery,
    ticket_service: TicketService,
    user: User
):
    stop_id = uuid.UUID(callback.data.split(":")[1])

    await ticket_service.create_or_update_ticket(
        user_id=user.id,
        stop_id=stop_id
    )

    await callback.message.edit_text(
        "✅ Вы отмечены на этой остановке"
    )

@router.message(Command("ticket") or F.text == "Мой билет")
async def check_active_ticket_handler(
    message: Message,
    ticket_service: TicketService,
    stop_service: StopService,
    user: User
):
    ticket = await ticket_service.get_active_ticket(user_id=user.id)

    if not ticket:
        await message.answer(
            "ℹ️ У вас нет активного билета.\n\n"+
            "Используй /stops чтобы выбрать остановку."
        )
        return

    if ticket.status == TicketStatus.ABSENT:
        await message.answer("\nБилет недействителен")
        return

    stop = await stop_service.get_stop_by_id(stop_id=ticket.stop_id)

    text = f"🎫 <b>Ваш билет</b>\n\n"
    text += f"📍 Остановка: {stop.name}\n"
    text += f"🔄 Статус: {ticket.status}\n"

    await message.answer(text, reply_markup=ticket_keyboard())

@router.message(Command("boarded") or F.text == "Я в автобусе")
async def passenger_boarded_handler(
    message: Message,
    ticket_service: TicketService,
    user: User
):
    ticket = await ticket_service.get_active_ticket(user_id=user.id)

    if ticket:
        await ticket_service.mark_as_boarded(ticket_id=ticket.id)

        await message.answer("Успешно отмечены")
    else:
        await message.answer("Нет активного билета")

@router.message(Command("cancel") or F.text == "Отменить")
async def canceled_active_ticket_handler(
    message: Message,
    ticket_service: TicketService,
    user: User
):
    ticket = await ticket_service.get_active_ticket(user_id=user.id)

    if ticket:
        await ticket_service.mark_as_absent(ticket_id=ticket.id)

        await message.answer("Успешная отмена")
    else:
        await message.answer("Нет активного билета")