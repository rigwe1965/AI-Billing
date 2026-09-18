from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: UserRole
    department_id: int | None
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole
    department_id: int | None = None
