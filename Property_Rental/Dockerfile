# One image, both halves, one origin.
#
# The browser app is built here and served by the API process, which is the decision recorded in
# `api/app/main.py`: two origins would mean CORS with credentials and a login cookie downgraded to
# SameSite=None. It also means the deployment is a single service with a single cold start.
#
# Docker rather than a host's native Python runtime, because this build needs Node *and* Python and
# a language-specific runtime image reliably has only one of them. The cost is that the image is
# ours to keep patched; the gain is that "it built on my machine" and "it built on the host" are
# the same sentence.

# --- stage 1: build the browser app ----------------------------------------------------------
FROM node:22-alpine AS web

WORKDIR /web
# package.json and the lockfile first, so a change to application code does not re-resolve every
# dependency. `npm ci` rather than `npm install` — it installs exactly the lockfile.
COPY web/package.json web/package-lock.json* ./
RUN npm ci

COPY web/ ./
RUN npm run build


# --- stage 2: the service ---------------------------------------------------------------------
FROM python:3.12-slim AS service

# Unbuffered so log lines appear in the host's log viewer as they happen rather than in blocks,
# and no .pyc files in a layer that is thrown away on every deploy.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

COPY api/ ./api/
# Into the path main.py already looks in, so the same code serves the app locally and in
# production without an environment variable deciding where the files are.
COPY --from=web /web/dist ./web/dist

# Runs as nobody rather than root. There is nothing in this image that needs to write to it.
RUN useradd --create-home --shell /usr/sbin/nologin service \
    && chown -R service:service /srv
USER service

WORKDIR /srv/api
EXPOSE 8000

# The host supplies $PORT. Migrations run first, in the same command, so a deploy that cannot
# migrate never starts serving — a half-migrated schema answering requests is worse than downtime.
CMD ["sh", "-c", "alembic upgrade head && python seed.py --if-empty && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
