from typing import Protocol
from aiogram.types import Message

class BotPort(Protocol):
    async def edit_timer(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str
    ) -> None:
        ...
    
    async def send_timer_message(
        self,
        *,
        chat_id: int,
        text: str,
    ) -> Message:
        ...