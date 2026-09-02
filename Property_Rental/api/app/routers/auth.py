"""Login, logout, and "who am I". HTTP only — the rules live in services and security."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import current_user
from app.models import User
from app.schemas.auth import LoginRequest, UserOut
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.scalars(select(User).where(User.email == body.email)).first()
    # One message for both a wrong email and a wrong password: saying which was wrong tells an
    # attacker which addresses are registered.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")

    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(user.id),
        httponly=True,  # page JavaScript cannot read it
        samesite="lax",  # the CSRF mitigation that comes with using a cookie
        secure=settings.cookie_secure,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user
