import uuid
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from app.bot.filters.is_driver import IsDriver
from app.bot.keyboards.keyboards import location_keyboard, stops_keyboard
from app.models.user import User
from app.services.location import LocationService
from app.services.ride import RideService

router = Router()
router.message.filter(IsDriver())
router.callback_query.filter(IsDriver())

@router.message(Command("start_tracking"))
async def start_tracking_driver_location_handler(
    message: Message,
):
    await message.answer(
        "📍 <b>Отслеживание геолокации</b>\n\n"+
        "Нажмите кнопку ниже и выберите:\n"+
        "• <b>«Поделиться геоданными»</b> (для постоянной передачи)\n"+
        "• Выбери время: 15 мин, 1 час или 8 часов\n\n"+
        "Telegram будет автоматически отправлять вашу позицию боту.",
        reply_markup=location_keyboard()
    )

@router.message(Command("start_ride"))
async def start_ride_request_handler(
    message: Message,
    user: User,
    ride_service: RideService
):
    if await ride_service.get_active_ride(driver_id=user.id):
        message.answer(
            "Поездка уже начата!"
        )   
    else:
        stops = await ride_service.get_active_stops()

        if not stops:
            await message.answer("Остановки не настроены.")
            return

        await message.answer(
            "📍 Выберите следующую остановку:",
            reply_markup=stops_keyboard(stops, "driver_select_stop")
        )

@router.callback_query(lambda c: c.data.startswith("driver_select_stop:"))
async def driver_stop_selected_handler(
    callback: CallbackQuery, 
    ride_service: RideService,
    user: User
):
    stop_id = uuid.UUID(callback.data.split(":")[1])

    await ride_service.start_ride(
        driver_id=user.id,
        next_stop_id=stop_id
    )

    await callback.message.edit_text(
        "✅ Поездка создана"
    )    

@router.message(F.location)
async def request_driver_location_handler(
    message: Message,
    ride_service: RideService,
    user: User
):
    await ride_service.process_driver_location(
        location=message.location,
        driver_id=user.id
    )

@router.edited_message(F.location)
async def driver_location_received_handler(
    message: Message,
    ride_service: RideService,
    user: User
):
    await ride_service.process_driver_location(
        location=message.location,
        driver_id=user.id
    )

@router.message(Command("stop_tracking"))
async def stop_driver_location_receiving_handler(message: Message):
    await message.answer(
        "🛑 <b>Остановка передачи</b>\n\n"+
        "Чтобы остановить передачу геолокации:\n"+
        "1. Найдите сообщение с Live Location\n"+
        "2. Нажмите «Остановить передачу»\n\n"+
        "Или просто закройте бота."
    )

@router.message(Command("personal_choice_stop"))
async def personal_choice_stop_handler(
    message: Message,
    ride_service: RideService
):
    stops = await ride_service.get_active_stops()

    if not stops:
        await message.answer("Остановки не настроены.")
        return

    await message.answer(
        "📍 Отметить остановку:",
        reply_markup=stops_keyboard(stops, "driver_note_stop")
    )

@router.callback_query(lambda c: c.data.startswith("driver_note_stop:"))
async def driver_stop_noted_handler(
    callback: CallbackQuery, 
    ride_service: RideService,
    user: User
):
    stop_id = uuid.UUID(callback.data.split(":")[1])

    stop = await ride_service.get_stop_by_id(stop_id=stop_id)

    ride = await ride_service.get_active_ride(driver_id=user.id)

    await ride_service.arrive_at_stop(
        ride=ride,
        stop=stop
    )



