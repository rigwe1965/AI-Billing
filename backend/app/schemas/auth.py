from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    password: str = Field(min_length=12, max_length=72)  # bcrypt ignores bytes past 72
    role: UserRole
    department_id: int | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=72)
