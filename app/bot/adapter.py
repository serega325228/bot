from aiogram import Bot
from aiogram.types import Message

class TelegramBotAdapter:
    def __init__(self, bot: Bot):
        self.__bot = bot

    async def edit_timer(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str
    ) -> None:
        await self.__bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text
        )

    async def send_timer_message(
        self,
        *,
        chat_id: int,
        text: str
    ) -> Message:
        return await self.__bot.send_message(
            chat_id=chat_id, 
            text=text
        )
