"""Request-scoped dependencies: who is calling, and what they are allowed to do.

The role check is on the server. Hiding a button stops nobody who can send an HTTP request.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.cookie_name)
    user_id = read_token(token)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


def read_token(token: str | None) -> int | None:
    if not token:
        return None
    from app.security import read_access_token

    return read_access_token(token)


def require_manager(user: User = Depends(current_user)) -> User:
    """403, not 404 — the caller is authenticated, they are just not allowed."""
    if not user.is_manager:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This action is for property managers only"
        )
    return user
