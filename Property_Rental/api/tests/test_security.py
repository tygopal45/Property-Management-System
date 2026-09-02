"""Regression tests for the findings of the security review.

Each one failed before its fix. They are grouped here rather than spread through the feature
tests because what they protect is a property of the whole app, not of one endpoint.
"""

import time

import jwt
import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.security import create_access_token


# --- configuration ------------------------------------------------------------------------------

def _settings(**overrides):
    """Builds Settings in isolation.

    `_env_file=None` matters: without it pydantic-settings reads the developer's real `api/.env`
    and quietly supplies the very value the test is trying to withhold.
    """
    base = {
        "_env_file": None,
        "database_url": "sqlite://",
        "jwt_secret": "a-real-secret-that-is-long-enough-to-be-accepted",
    }
    base.update(overrides)
    return Settings(**base)


def test_the_app_refuses_to_start_without_a_jwt_secret():
    """The whole app used to ship a default secret. Anyone reading the repository could forge a
    manager cookie for user 1 — no password — and every role check would correctly let them
    through, because the token was genuinely valid. There is now no default to forget."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite://", jwt_secret=None)


@pytest.mark.parametrize(
    "bad", ["dev-secret-not-for-production", "change-me", "secret", "short", "x" * 31]
)
def test_a_weak_or_known_jwt_secret_is_refused(bad):
    with pytest.raises(ValidationError):
        _settings(jwt_secret=bad)


@pytest.mark.parametrize("bad", ["*", "http://localhost:5173,*"])
def test_a_wildcard_cors_origin_is_refused(bad):
    """This API allows credentials. Starlette answers a wildcard by reflecting the caller's
    origin *and* keeping credentials on, so any site could read authenticated responses. Today
    SameSite=Lax stops it; on split domains that cookie becomes SameSite=None and it would not."""
    with pytest.raises(ValidationError):
        _settings(cors_origins=bad)


def test_a_real_configuration_is_accepted():
    assert _settings(cors_origins="https://app.example.com").jwt_secret


# --- tokens -------------------------------------------------------------------------------------

def test_a_token_without_an_expiry_is_rejected(client, manager):
    """Minting always sets `exp`. Insisting on it when reading means a forged token that omits
    one does not live for ever."""
    forever = jwt.encode({"sub": str(manager.id)}, settings.jwt_secret, algorithm="HS256")
    client.cookies.set(settings.cookie_name, forever)
    assert client.get("/api/auth/me").status_code == 401

    client.cookies.set(settings.cookie_name, create_access_token(manager.id))
    assert client.get("/api/auth/me").status_code == 200


# --- the login timing oracle --------------------------------------------------------------------

def test_a_failed_login_costs_the_same_whether_the_email_exists(client, manager):
    """The message was already identical for both cases. The *timing* was not: bcrypt ran only
    when the row existed, so a known email took 405ms and an unknown one 5ms — one request told
    an attacker whether an address was registered. Both paths now hash.

    The assertion is a ratio rather than a fixed figure, because the absolute cost depends on the
    bcrypt rounds, which the test suite lowers.
    """
    def cost(email):
        samples = []
        for _ in range(5):
            start = time.perf_counter()
            response = client.post("/api/auth/login",
                                   json={"email": email, "password": "definitely-wrong"})
            samples.append(time.perf_counter() - start)
            assert response.status_code == 401
        return sorted(samples)[len(samples) // 2]

    known = cost("priya@example.com")
    unknown = cost("nobody@example.com")
    ratio = max(known, unknown) / max(min(known, unknown), 1e-9)
    assert ratio < 5, f"timing still separates the two paths: {known=:.4f} {unknown=:.4f}"


# --- client-triggerable 500s ---------------------------------------------------------------------

def test_a_huge_page_number_is_refused_rather_than_crashing(as_manager):
    """`page=10**18` made the OFFSET overflow what MySQL will parse, and the request 500ed."""
    assert as_manager.get("/api/requests?page=1000000000000000000").status_code == 422
    assert as_manager.get("/api/requests?page=1000001").status_code == 422
    assert as_manager.get("/api/requests?page=1000000").status_code == 200


def test_an_unserialisable_number_gives_422_not_500(as_manager, unit):
    """Validation always rejected `1e9999`. Then the default error handler tried to echo `inf`
    back into the JSON body, could not, and turned its own 422 into a 500."""
    # Sent as a raw body: the HTTP client refuses to encode `inf` itself, so `json=` never
    # reaches the server. `1e9999` is valid JSON that Python parses to infinity.
    response = as_manager.post(
        "/api/requests",
        content='{"unit_id": 1e9999, "description": "x"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]


def test_a_validation_error_does_not_echo_what_was_sent(as_manager, unit):
    """The error says what was wrong, not what was submitted."""
    secret = "SENSITIVE-VALUE-abc123"
    response = as_manager.post("/api/requests",
                               json={"unit_id": "not-an-int", "description": secret})
    assert response.status_code == 422
    assert secret not in response.text


def test_request_text_is_capped(as_manager, unit):
    """The columns are TEXT. Uncapped, a signed-in user could post megabytes."""
    assert as_manager.post("/api/requests",
                           json={"unit_id": unit.id, "description": "x" * 4001}
                           ).status_code == 422
    assert as_manager.post("/api/requests",
                           json={"unit_id": unit.id, "description": "x" * 4000}
                           ).status_code == 201


# --- responses ----------------------------------------------------------------------------------

def test_every_response_carries_nosniff(client, as_manager):
    for response in (client.get("/api/health"), as_manager.get("/api/requests")):
        assert response.headers["x-content-type-options"] == "nosniff"


def test_the_assignment_refusal_does_not_name_the_user(as_manager, db, unit, manager):
    """Probing ids sequentially would otherwise separate exists-as-manager (with their name) from
    exists-as-contractor from absent, which walks the whole users table."""
    from tests.conftest import make_request

    request = make_request(db, unit, manager)
    response = as_manager.post(f"/api/requests/{request.id}/assignments",
                               json={"contractor_id": manager.id})
    assert response.status_code == 422
    assert manager.name not in response.text


def test_health_reports_degraded_when_the_database_is_gone(client, monkeypatch):
    """It used to answer `{"status": "ok", "database": "unavailable"}` — a health check that lies,
    which is what the comment above it claimed to avoid. Nothing would ever drain the instance."""
    import app.main as main

    def broken():
        raise RuntimeError("no database")

    monkeypatch.setattr(main.engine, "connect", broken)
    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    # And it does not name the exception class to an unauthenticated caller.
    assert "RuntimeError" not in response.text
