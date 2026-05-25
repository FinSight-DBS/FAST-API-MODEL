from fastapi import APIRouter, Depends

from src.core.http import HTTPDataResponse
from src.features.user.usecase.get_all_users_usecase import GetAllUsersRequest, GetAllUsersUseCase
from src.features.user.user_dependencies import get_get_all_users_use_case
from src.domain.entity.customer import Customer

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("", response_model=HTTPDataResponse[list[dict]])
async def get_all_users(
    use_case: GetAllUsersUseCase = Depends(get_get_all_users_use_case),
) -> HTTPDataResponse[list[dict]]:
    result = await use_case.execute(GetAllUsersRequest())
    return HTTPDataResponse(
        status="success",
        data=[
            {
                "id": c.id,
                "full_name": c.full_name,
                "base_persona": c.base_persona,
                "monthly_income": c.monthly_income,
                "savings_goal": c.savings_goal,
            }
            for c in result.users
        ],
        message="Customers fetched successfully",
    )
