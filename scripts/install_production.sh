#!/usr/bin/env bash
set -euo pipefail

# Team_Project production installer/updater.
#
# Usage on a new server:
#   sudo APP_DIR=/opt/Team_Project REPO_URL=git@github.com:jtmyd-top/Team_Project.git bash scripts/install_production.sh
#
# Required before running:
#   1. Put a valid .env file at "$APP_DIR/.env".
#   2. Ensure this server can access MySQL/Redis from that .env.
#   3. If REPO_URL uses SSH, configure the deploy key in advance.
#
# This script intentionally never creates or prints .env contents.

APP_DIR="${APP_DIR:-/opt/Team_Project}"
REPO_URL="${REPO_URL:-git@github.com:jtmyd-top/Team_Project.git}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-team-project}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RUN_USER="${RUN_USER:-root}"
RUN_GROUP="${RUN_GROUP:-root}"
INSTALL_SYSTEM_DEPS="${INSTALL_SYSTEM_DEPS:-0}"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-0}"
SKIP_MIGRATE="${SKIP_MIGRATE:-0}"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    printf 'This script must run as root because it installs a systemd service.\n' >&2
    exit 1
  fi
}

install_system_deps() {
  if [ "$INSTALL_SYSTEM_DEPS" != "1" ]; then
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    printf 'INSTALL_SYSTEM_DEPS=1 currently supports apt-based systems only.\n' >&2
    exit 1
  fi

  log "Installing system dependencies"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git curl ca-certificates build-essential pkg-config \
    "$PYTHON_BIN" python3-venv python3-dev \
    nodejs npm
}

prepare_source() {
  if [ -d "$APP_DIR/.git" ]; then
    log "Using existing repository at $APP_DIR"
    cd "$APP_DIR"
    if [ "$SKIP_GIT_PULL" != "1" ]; then
      git fetch origin
      git checkout "$BRANCH"
      git pull --ff-only origin "$BRANCH"
    fi
  else
    log "Cloning $REPO_URL into $APP_DIR"
    mkdir -p "$(dirname "$APP_DIR")"
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
  fi
}

check_env_file() {
  if [ ! -f "$APP_DIR/.env" ]; then
    printf '\nMissing %s/.env\n' "$APP_DIR" >&2
    printf 'Copy the production .env from the working server, then rerun this script.\n' >&2
    exit 1
  fi
  chmod 600 "$APP_DIR/.env"
  chown "$RUN_USER:$RUN_GROUP" "$APP_DIR/.env"
}

setup_python() {
  log "Setting up Python virtualenv"
  cd "$APP_DIR"
  if [ ! -x .venv/bin/python ]; then
    "$PYTHON_BIN" -m venv .venv
  fi
  .venv/bin/python -m pip install --upgrade pip setuptools wheel
  .venv/bin/python -m pip install -r requirements.txt
}

setup_frontend() {
  log "Installing frontend dependencies and building assets"
  cd "$APP_DIR"
  npm install --prefix frontend --cache "$APP_DIR/.npm-cache" --no-audit --no-fund
  npm run build --prefix frontend
}

run_django_tasks() {
  log "Running Django checks"
  cd "$APP_DIR"
  .venv/bin/python manage.py check --deploy

  if [ "$SKIP_MIGRATE" != "1" ]; then
    log "Applying database migrations"
    .venv/bin/python manage.py migrate --noinput
  fi

  log "Collecting static files"
  .venv/bin/python manage.py collectstatic --noinput
}

install_service() {
  log "Installing systemd service: $SERVICE_NAME.service"
  cat >"/etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=Team Project Django ASGI service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/daphne -b $HOST -p $PORT Team_Project.asgi:application
Restart=always
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME.service"
  systemctl restart "$SERVICE_NAME.service"
}

verify_service() {
  log "Service status"
  systemctl --no-pager --full status "$SERVICE_NAME.service" || true

  log "Local health check"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS -H "X-Forwarded-Proto: https" "http://127.0.0.1:$PORT/readyz" || true
    printf '\n'
  else
    printf 'curl not found; skipped /readyz check.\n'
  fi
}

main() {
  require_root
  install_system_deps
  prepare_source
  check_env_file
  setup_python
  setup_frontend
  run_django_tasks
  install_service
  verify_service

  log "Done"
  printf 'Reverse proxy target: http://<this-server-ip>:%s\n' "$PORT"
}

main "$@"
