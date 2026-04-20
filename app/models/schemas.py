from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")


class AskResponse(BaseModel):
    answer: str
    references: list[str]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: str
    last_login_at: str | None = None


class LoginResponse(BaseModel):
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3)
    display_name: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)
    role: str = "user"
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserPasswordResetRequest(BaseModel):
    password: str = Field(..., min_length=8)
