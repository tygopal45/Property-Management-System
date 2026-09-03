from pydantic import BaseModel, EmailStr, field_validator

from app.models.enums import Role


def normalise_email(value: str) -> str:
    """Emails are stored and compared lowercased, always.

    Without this the app behaves differently per engine: MySQL's default collation compares
    strings case-insensitively, so `Priya@example.com` finds the row, while SQLite compares
    exactly and returns nothing. Same code, same data, different answer — which is precisely the
    kind of engine-specific behaviour Decision 5 exists to keep out.
    """
    return value.strip().lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lowercase(cls, value: str) -> str:
        return normalise_email(value)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: Role

    model_config = {"from_attributes": True}


class ContractorOut(BaseModel):
    """A name and an id, for the assignment control. Notice what is absent: the email address.

    The screen needs to label a dropdown, not to identify a person, so this returns the least it
    can. A response model that happens to contain a field is a response model that leaks it.
    """

    id: int
    name: str

    model_config = {"from_attributes": True}
