from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    role: Literal["attempter", "reviewer"] = "attempter"  # default to attempter


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class DeleteAccountRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    email_verified: bool
    role: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
