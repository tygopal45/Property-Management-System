from pydantic import BaseModel, EmailStr, field_validator

from app.models.enums import Role


def normalise_email(value: str) -> str:
    """Emails are stored and compared lowercased, always.

    Without this the app behaves differently per engine: MySQL's default collation compares
    strings case-insensitively, so `Priya@example.com` finds the row, while Postgres and SQLite
    compare exactly and return nothing. Same code, same data, different answer — precisely the
    kind of engine-specific behaviour Decision 5 exists to keep out.

    On Postgres this is now load-bearing rather than belt-and-braces, in two directions. Login
    would fail on a capitalised address, and — worse, because it is silent — the unique index on
    `email` would no longer stop `Priya@example.com` and `priya@example.com` both being
    registered as separate accounts. MySQL's collation had been quietly preventing that.
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
