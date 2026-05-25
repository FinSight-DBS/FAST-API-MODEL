from dataclasses import dataclass
from typing import Optional

from src.domain.entity.enums import CredentialStatusEnum


@dataclass
class UserCredentials:
    id: str
    customer_id: str
    username: str
    email: str
    password: str
    status: CredentialStatusEnum
    mpin: Optional[str] = None
    active_token: Optional[str] = None
