"""Adversarial tests on the login and the cookie."""

import jwt

from app.config import settings
from app.security import create_access_token


def test_a_tampered_cookie_is_rejected(client, manager):
    """Signed with the wrong key. If this passed, anyone could mint their own session."""
    forged = jwt.encode({"sub": str(manager.id)}, "not-the-real-secret", algorithm="HS256")
    client.cookies.set(settings.cookie_name, forged)
    assert client.get("/api/auth/me").status_code == 401


def test_a_cookie_claiming_another_user_id_only_gets_that_user(client, manager, contractor):
    """The id in the token is the whole identity, so a *validly signed* token for the contractor
    must not grant manager rights. This is the check that the role is read from the database and
    not from the token."""
    client.cookies.set(settings.cookie_name, create_access_token(contractor.id))
    assert client.get("/api/auth/me").json()["role"] == "contractor"
    assert client.post("/api/units", json={"unit_number": "X", "address": "a",
                                           "tenant_name": "t", "monthly_rent": "1.00"}
                       ).status_code == 403


def test_an_expired_token_is_rejected(client, manager):
    from datetime import datetime, timedelta, timezone

    stale = jwt.encode(
        {"sub": str(manager.id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    client.cookies.set(settings.cookie_name, stale)
    assert client.get("/api/auth/me").status_code == 401


def test_a_token_for_a_user_who_no_longer_exists_is_rejected(client, db, manager):
    token = create_access_token(manager.id)
    db.delete(manager)
    db.commit()
    client.cookies.set(settings.cookie_name, token)
    assert client.get("/api/auth/me").status_code == 401


def test_garbage_in_the_cookie_is_rejected_not_crashed(client, manager):
    for junk in ("", "not-a-jwt", "a.b.c", "null", "{}"):
        client.cookies.set(settings.cookie_name, junk)
        assert client.get("/api/auth/me").status_code == 401


def test_a_token_with_no_subject_is_rejected(client, manager):
    empty = jwt.encode({"nothing": True}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    client.cookies.set(settings.cookie_name, empty)
    assert client.get("/api/auth/me").status_code == 401


def test_no_response_ever_contains_a_password_hash(as_manager, manager):
    for path in ("/api/auth/me", "/api/units", "/api/requests"):
        assert "password" not in as_manager.get(path).text.lower()


def test_login_is_case_insensitive_on_the_email(client, manager):
    """MySQL's default collation makes email comparison case-insensitive; SQLite's is not. The
    application lowercases on both sides so the behaviour is the same on either engine."""
    response = client.post("/api/auth/login",
                           json={"email": "PRIYA@example.com", "password": "manager-pw"})
    assert response.status_code == 200
