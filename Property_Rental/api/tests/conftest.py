"""Test fixtures. Tests run against in-memory SQLite so the whole suite is a second or two.

That is also the reason ordering never relies on the column type: SQLite has no native enum, so
the same model column arrives here as VARCHAR. schema.md Decision 6.
"""

import os

# Set before importing the app: config reads the environment at import time.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import hash_password

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
