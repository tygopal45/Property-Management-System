"""App factory. Mounts routers, sets CORS, exposes a health check."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routers import alerts, auth, dashboard, rent, requests, units

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
app.include_router(rent.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)


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


# --- the browser app ------------------------------------------------------------------------
#
# The built React app is served by this same process, from this same origin. That is a
# deployment decision with a security consequence, so it is written down here rather than in a
# deploy script.
#
# Two origins would mean CORS with credentials, and a login cookie that has to become
# `SameSite=None` to survive the trip — which is the exact protection `config.py` refuses to give
# up when it rejects a wildcard origin. One origin means the cookie stays `SameSite=Lax`, the
# CORS middleware above never fires for real traffic, and there is one URL and one cold start
# instead of two.
#
# If `web/dist` has not been built, the API still runs. Nothing here is required for `/api`.

WEB_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"

if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.api_route(
        "/{path:path}",
        methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def browser_app(path: str, request: Request) -> FileResponse:
        """Serves the app, and lets the router own every path that is not an API route.

        The client routes on paths like `/units/4`, so a reload there has to return the app
        rather than a 404 — but only after the real files have had their chance.

        **Every method is registered, and everything but GET and HEAD is refused here.** That is
        not tidiness. With only GET registered, a `DELETE /api/requests/1/events/1` matches this
        path, finds no DELETE, and Starlette answers **405 Method Not Allowed** — which tells a
        caller the path exists for some other method. For requirement 9's timeline that is exactly
        the wrong answer, and it is a regression this route introduced: before the browser app was
        mounted, the same request returned 404. Registering the methods and refusing them here
        restores it, and a test asserts on that specific URL.
        """
        if path.startswith("api/") or request.method not in ("GET", "HEAD"):
            # An API path reaching this fallback is an endpoint that does not exist. It has to
            # 404 as JSON: answering with the HTML shell and a 200 turns a missing endpoint into
            # a parse error three layers away from the mistake.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such endpoint")

        candidate = (WEB_DIST / path).resolve()
        # `resolve()` then `is_relative_to` is the guard: without it, `GET /../../etc/passwd`
        # would be resolved against the dist directory and read straight off the disk.
        if path and candidate.is_relative_to(WEB_DIST) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
