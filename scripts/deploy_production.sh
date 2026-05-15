#!/usr/bin/env bash
set -euo pipefail

cd /opt/Team_Project

if [ ! -x .venv/bin/python ]; then
  python3.9 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -r requirements.txt

npm install --prefix frontend --cache /opt/Team_Project/.npm-cache --no-audit --no-fund
npm run build --prefix frontend

.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput

install -m 0644 deploy/team-project.service /etc/systemd/system/team-project.service
systemctl daemon-reload
systemctl enable --now team-project.service
systemctl restart team-project.service
systemctl --no-pager --full status team-project.service
