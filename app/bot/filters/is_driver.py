from aiogram.filters import BaseFilter

from app.models.user import UserRole

class IsDriver(BaseFilter):
    async def __call__(self, event, **data):
        user = data.get("user")
        return bool(user and user.role == UserRole.DRIVER)