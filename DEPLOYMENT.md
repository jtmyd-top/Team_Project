# Deployment Notes

## Topology

Recommended production topology:

`Nginx / Cloud Load Balancer -> multiple ASGI instances -> MySQL + Redis`

Key points:

- Static files: `collectstatic` to `STATIC_ROOT`, then serve with `Nginx` or a CDN.
- Media files: prefer object storage via `DEFAULT_FILE_STORAGE_BACKEND`; do not rely on per-node local disk when scaling horizontally.
- Sessions, rate limits, IP bans, vault state, and realtime fan-out must use shared backends.

## Required Environment Variables

Core:

- `DJANGO_ENV=production`
- `DEBUG=false`
- `SECRET_KEY=...`
- `ALLOWED_HOSTS=example.com,www.example.com`
- `CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com`

Reverse proxy:

- `TRUST_X_FORWARDED_PROTO=true`
- `USE_X_FORWARDED_HOST=true`
- `USE_X_FORWARDED_PORT=true`
- `TRUSTED_PROXY_CIDRS=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1/32`

Redis / shared state:

- `REDIS_URL=redis://:password@redis-host:6379/1`
- `CHANNEL_REDIS_URL=redis://:password@redis-host:6379/2`
- `REQUIRE_SHARED_CHANNEL_LAYER=true`

Security:

- `SESSION_COOKIE_SECURE=true`
- `CSRF_COOKIE_SECURE=true`
- `SECURE_SSL_REDIRECT=true`
- `SECURE_HSTS_SECONDS=31536000`

Optional object storage:

- `DEFAULT_FILE_STORAGE_BACKEND=storages.backends.s3.S3Storage`
- `MEDIA_URL=https://cdn.example.com/media/`

## Health Checks

- `GET /healthz`
  - Liveness only. Returns `200` if the Django process is alive.

- `GET /readyz`
  - Readiness check. Verifies:
    - database connectivity
    - cache / Redis connectivity
    - websocket channel layer configuration presence when realtime is enabled
  - Returns `200` when ready, otherwise `503`.

Configure the load balancer to use `GET /readyz` for readiness and `GET /healthz` for liveness.

## WebSocket Proxying

Your load balancer / Nginx must support:

- `Upgrade` and `Connection` headers
- long idle timeout
- forwarding `X-Forwarded-Proto`
- forwarding `X-Forwarded-For`

Sticky sessions are not required if:

- sessions are shared
- Redis channel layer is shared

## Example Nginx Notes

- proxy `/` and `/ws/` to ASGI upstreams
- serve `/static/` directly from `STATIC_ROOT`
- do not serve user media from per-node local disk in a multi-instance setup

## Before Go-Live

- run `python manage.py check --deploy`
- run `python manage.py collectstatic --noinput`
- confirm `readyz` returns `200`
- confirm websocket messaging works across at least two ASGI instances
