from pydantic import BaseModel, EmailStr

from app.models.enums import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: Role

    model_config = {"from_attributes": True}
