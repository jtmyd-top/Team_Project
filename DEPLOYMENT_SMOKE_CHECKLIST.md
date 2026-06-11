# Deployment Smoke Checklist

Use this checklist for production releases on `/opt/Team_Project`.

## Build And Deploy Order

1. `git pull --ff-only`
2. Activate the virtualenv.
3. `pip install -r requirements.txt`
4. `python manage.py migrate`
5. `npm ci`
6. `npm run build`
7. `python manage.py collectstatic --noinput`
8. `systemctl restart team-project.service`
9. `systemctl status team-project.service --no-pager`

## Required Smoke Checks

- `GET /healthz`
- `GET /readyz`
- `GET /login/`
- `POST /api/login/` with a known valid test account.
- `GET /settings/`
- `GET /api/messages/groups/policy/`
- `GET /api/notifications/unread-count/`
- `GET /api/moderation/reports/?status=pending&type=all&page=1`
- `GET /api/vault/status/`
- Open a note list, move one test note, copy one test note, then confirm the source note remains unchanged.

## Static Asset Cache Rule

Settings and messages pages must include a version query string based on the built asset mtime. If a deployed frontend change is not visible, verify the generated file under `staticfiles/dist/`, run `collectstatic`, and restart the service before asking users to clear browser cache.
