"""Requirement 1: two roles, and the check is on the server."""


def test_login_sets_httponly_cookie(client, manager):
    response = client.post(
        "/api/auth/login", json={"email": "priya@example.com", "password": "manager-pw"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "manager"

    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie  # page JavaScript must not be able to read the token
    assert "samesite=lax" in cookie


def test_wrong_password_is_rejected(client, manager):
    response = client.post(
        "/api/auth/login", json={"email": "priya@example.com", "password": "wrong"}
    )
    assert response.status_code == 401


def test_unknown_email_gives_the_same_message_as_a_wrong_password(client, manager):
    """Different messages would tell an attacker which addresses are registered."""
    unknown = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "manager-pw"}
    )
    wrong_pw = client.post(
        "/api/auth/login", json={"email": "priya@example.com", "password": "wrong"}
    )
    assert unknown.status_code == wrong_pw.status_code == 401
    assert unknown.json()["detail"] == wrong_pw.json()["detail"]


def test_me_requires_a_cookie(client, manager):
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_the_session(as_manager):
    assert as_manager.get("/api/auth/me").status_code == 200
    as_manager.post("/api/auth/logout")
    assert as_manager.get("/api/auth/me").status_code == 401
