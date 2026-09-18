import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Единый формат ошибок

class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


# Схемы запросов (Requests)

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., max_length=127)
    last_name: str = Field(..., max_length=127)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


# Схемы ответов (Responses)


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


class MessageResponse(BaseModel):
    message: str