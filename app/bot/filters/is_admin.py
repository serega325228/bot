from aiogram.filters import Filter, BaseFilter

from app.models.user import UserRole

class IsAdmin(BaseFilter):
    async def __call__(self, event, **data):
        user = data.get("user")
        return bool(user and user.role == UserRole.ADMIN)