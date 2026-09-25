import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., max_length=127)
    last_name: str = Field(..., max_length=127)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRolesUpdateByEmailRequest(BaseModel):
    email: EmailStr
    roles: list[str] = Field(..., min_length=1, description="admin, engineer, foreman, user")


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    roles: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 900
    user: UserResponse


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 900