"""Password hashing and token minting. No route logic here."""

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# A real bcrypt hash of a value nobody can log in with. Verifying against it on the
# no-such-user path makes a failed login cost the same whether the email exists or not. Without
# it the two paths were 5ms and 405ms — a 75x gap, so one request told an attacker whether an
# address was registered. The identical error message was doing nothing on its own.
#
# Built on first use rather than at import, so it always matches the cost of the hashes it is
# standing in for. Computing it at import got this backwards in the test suite, which lowers the
# bcrypt rounds after importing: the placeholder stayed expensive while real hashes became cheap,
# and the timing gap reappeared pointing the other way.
_dummy_hash: str | None = None


def waste_a_password_check(plain: str) -> None:
    """Burns the same bcrypt time as a real verification, and always fails."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _pwd.hash("no-such-user-placeholder")
    _pwd.verify(plain, _dummy_hash)


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def read_access_token(token: str) -> int | None:
    """Returns the user id, or None if the token is missing, expired or tampered with."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            # Minting always sets `exp`, but insisting on it here means a token *without* one is
            # rejected rather than living for ever.
            options={"require": ["exp"]},
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None
