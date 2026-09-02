"""App factory. Mounts routers, sets CORS, exposes a health check."""

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routers import auth, requests, units

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
app.include_router(requests.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """The one security header that is this application's job rather than the host's.

    HSTS belongs to whatever terminates TLS, and a content policy belongs to whatever serves the
    browser app. `nosniff` is about how a client treats *this* API's responses, so it belongs here.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Reports what was wrong without echoing what was sent.

    FastAPI's default handler puts the offending input back in the response, and that is enough to
    crash it: a body of `{"unit_id": 1e9999}` is correctly rejected, then the handler tries to
    serialise `inf` into JSON, fails, and the caller gets a 500 instead of a 422. Dropping the
    echo fixes that and stops the error reflecting caller-supplied content back out.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": [
                {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
                for error in exc.errors()
            ]
        },
    )


@app.get("/api/health", tags=["health"])
def health(response: Response) -> dict:
    """Green means the process is up *and* the database answers.

    It used to report `{"status": "ok", "database": "unavailable"}`, which is the exact thing the
    old comment claimed to avoid — a health check that lies. Nothing watching it would ever take
    the instance out of service. Now a database that does not answer makes the whole check
    degraded, and the status code says so too.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        # No exception class or message: this endpoint is unauthenticated, and the detail is
        # fingerprinting for anyone asking. The traceback still goes to the server log.
        database = "unavailable"

    if database != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "database": database}
    return {"status": "ok", "database": database}
