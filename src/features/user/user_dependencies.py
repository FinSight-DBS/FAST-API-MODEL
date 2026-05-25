from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.features.user.usecase.get_all_users_usecase import GetAllUsersUseCase


def get_get_all_users_use_case(
    db: AsyncSession = Depends(get_db),
) -> GetAllUsersUseCase:
    return GetAllUsersUseCase(db)
