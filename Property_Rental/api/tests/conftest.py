"""Test fixtures. Tests run against in-memory SQLite so the whole suite is a second or two.

That is also the reason ordering never relies on the column type: SQLite has no native enum, so
the same model column arrives here as VARCHAR. schema.md Decision 6.
"""

import os

# Set before importing the app: config reads the environment at import time.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
# Long enough to satisfy the production guard in config.py. Deliberately a real-shaped value:
# a test that runs with a weak secret would not be testing the same code path.
os.environ["JWT_SECRET"] = "test-only-secret-long-enough-to-pass-the-startup-guard"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import _pwd, hash_password

# bcrypt is deliberately slow, which is the point in production and pure cost here — the fixtures
# hash a password for every test. Four rounds keeps the same code path and the same verify() call
# while taking the work out. Production rounds are the library default, untouched.
_pwd.update(bcrypt__rounds=4)

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enforce_foreign_keys(dbapi_connection, _record):
    """SQLite ignores foreign keys unless asked. Without this the FK tests would pass falsely."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db():
    Base.metadata.create_all(engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def manager(db) -> User:
    user = User(
        name="Priya Nair",
        email="priya@example.com",
        password_hash=hash_password("manager-pw"),
        role=Role.manager,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def contractor(db) -> User:
    user = User(
        name="Tomas Vidal",
        email="tomas@example.com",
        password_hash=hash_password("contractor-pw"),
        role=Role.contractor,
    )
    db.add(user)
    db.commit()
    return user


def login(client: TestClient, email: str, password: str) -> None:
    """Logs the client in. The cookie is kept by the TestClient from here on."""
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


@pytest.fixture
def as_manager(client, manager):
    login(client, "priya@example.com", "manager-pw")
    return client


@pytest.fixture
def as_contractor(client, contractor):
    login(client, "tomas@example.com", "contractor-pw")
    return client


# --- units and requests -------------------------------------------------------------------------

@pytest.fixture
def unit(db):
    from datetime import date
    from decimal import Decimal

    from app.services.units import create_unit

    return create_unit(
        db,
        unit_number="4B",
        address="12 Rose Lane",
        tenant_name="Rahul Mehta",
        monthly_rent=Decimal("1200.00"),
        rent_effective_from=date(2026, 1, 1),
    )


@pytest.fixture
def second_contractor(db):
    user = User(
        name="Amara Diallo",
        email="amara@example.com",
        password_hash=hash_password("contractor-pw"),
        role=Role.contractor,
    )
    db.add(user)
    db.commit()
    return user


def make_request(db, unit, actor, description="Kitchen faucet leaking", priority=None):
    from app.models import Priority
    from app.services.requests import create_request

    return create_request(
        db,
        unit_id=unit.id,
        description=description,
        priority=priority or Priority.medium,
        actor=actor,
    )


# --- rent, alerts and the dashboard ---------------------------------------------------------------

@pytest.fixture
def make_unit(db):
    """A unit with one rent rate, for tests that need several units with different rents."""
    from datetime import date
    from decimal import Decimal

    from app.services.units import create_unit

    def _make(unit_number: str, rent: str = "1000.00", start: date = date(2026, 1, 1),
              tenant: str = "A Tenant", address: str = "1 Test Road"):
        return create_unit(
            db,
            unit_number=unit_number,
            address=address,
            tenant_name=tenant,
            monthly_rent=Decimal(rent),
            rent_effective_from=start,
        )

    return _make


@pytest.fixture
def pay(db, manager):
    """Record a payment against a unit for a month."""
    from decimal import Decimal

    from app.services.rent import record_payment

    def _pay(unit, amount: str, month):
        return record_payment(
            db,
            unit_id=unit.id,
            amount=Decimal(amount),
            period_month=month,
            recorded_by=manager,
        )

    return _pay


def months_ago(count: int):
    """A month relative to the current one, so tests do not go stale as the calendar moves."""
    from app.services.rent import add_months, month_start, today_utc

    return add_months(month_start(today_utc()), -count)
