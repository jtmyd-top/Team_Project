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
MIN_PYTHON_MAJOR="${MIN_PYTHON_MAJOR:-3}"
MIN_PYTHON_MINOR="${MIN_PYTHON_MINOR:-9}"
MIN_NODE_MAJOR="${MIN_NODE_MAJOR:-18}"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    printf 'This script must run as root because it installs a systemd service.\n' >&2
    exit 1
  fi
}

require_systemd() {
  if ! command -v systemctl >/dev/null 2>&1; then
    printf 'systemctl not found. This installer requires a systemd-based Linux server.\n' >&2
    exit 1
  fi
  if [ ! -d /run/systemd/system ]; then
    printf 'systemd does not appear to be PID 1. Cannot install/start a systemctl service here.\n' >&2
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
    "$PYTHON_BIN" python3-venv python3-dev

  if ! command -v node >/dev/null 2>&1 || [ "$(node -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null || printf 0)" -lt "$MIN_NODE_MAJOR" ]; then
    log "Installing Node.js 20 from NodeSource"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Missing command: %s\n' "$1" >&2
    printf 'Install system dependencies first, or rerun with INSTALL_SYSTEM_DEPS=1 on apt-based systems.\n' >&2
    exit 1
  fi
}

check_runtime_versions() {
  require_command git
  require_command "$PYTHON_BIN"
  require_command node
  require_command npm
  require_command curl

  "$PYTHON_BIN" - "$MIN_PYTHON_MAJOR" "$MIN_PYTHON_MINOR" <<'PY'
import sys
required = (int(sys.argv[1]), int(sys.argv[2]))
current = sys.version_info[:2]
if current < required:
    raise SystemExit(
        f"Python {required[0]}.{required[1]}+ is required, current is {current[0]}.{current[1]}"
    )
PY

  node_major="$(node -p 'Number(process.versions.node.split(".")[0])')"
  if [ "$node_major" -lt "$MIN_NODE_MAJOR" ]; then
    printf 'Node.js %s+ is required for Vite build, current is %s.\n' "$MIN_NODE_MAJOR" "$(node -v)" >&2
    printf 'Install Node.js %s+ and rerun this script.\n' "$MIN_NODE_MAJOR" >&2
    exit 1
  fi
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
    log "Preparing repository at $APP_DIR"
    mkdir -p "$APP_DIR"
    cd "$APP_DIR"
    git init
    if git remote get-url origin >/dev/null 2>&1; then
      git remote set-url origin "$REPO_URL"
    else
      git remote add origin "$REPO_URL"
    fi
    git fetch origin "$BRANCH"
    git checkout -B "$BRANCH" "origin/$BRANCH"
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

prepare_permissions() {
  log "Preparing filesystem permissions"
  mkdir -p "$APP_DIR/staticfiles" "$APP_DIR/knowledge_project/uploads"
  chown -R "$RUN_USER:$RUN_GROUP" \
    "$APP_DIR/.env" \
    "$APP_DIR/.npm-cache" \
    "$APP_DIR/staticfiles" \
    "$APP_DIR/knowledge_project/uploads" 2>/dev/null || true
}

validate_env_file() {
  log "Validating required .env keys"
  cd "$APP_DIR"
  .venv/bin/python - <<'PY'
import os
import sys
from dotenv import dotenv_values

env = dotenv_values(".env")

def has(key):
    value = env.get(key, os.environ.get(key))
    return bool(str(value or "").strip())

required = [
    "SECRET_KEY",
    "mysql_name",
    "mysql_user",
    "mysql_passwd",
    "mysql_ip",
    "mysql_port",
]
missing = [key for key in required if not has(key)]

alternatives = [
    ("REDIS_URL", "redis1", "redis"),
    ("VAULT_KEK", "VAULT_KEY_FILE"),
]
for group in alternatives:
    if not any(has(key) for key in group):
        missing.append(" or ".join(group))

if missing:
    print("Missing required .env keys:", ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)
PY
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
  require_systemd
  install_system_deps
  check_runtime_versions
  prepare_source
  check_env_file
  prepare_permissions
  setup_python
  validate_env_file
  setup_frontend
  run_django_tasks
  install_service
  verify_service

  log "Done"
  printf 'Reverse proxy target: http://<this-server-ip>:%s\n' "$PORT"
}

main "$@"
