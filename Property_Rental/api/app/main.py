"""App factory. Mounts routers, sets CORS, exposes a health check."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routers import auth, units

app = FastAPI(
    title="Property Rental & Maintenance",
    description="Property management API. Interactive docs below are generated from the code.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,  # the login cookie has to travel
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(units.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    """Green means the process is up *and* the database answers."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:  # surfaced deliberately: a health check that lies is worthless
        database = f"unavailable: {type(exc).__name__}"
    return {"status": "ok", "database": database}
