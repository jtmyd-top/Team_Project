# Team Project Execution Plan

## Baseline

- Backend check: `python manage.py check --settings=Team_Project.settings_test`
- Frontend build: `npm run build`
- Sample regression tests: `python manage.py test --settings=Team_Project.settings_test knowledge_project.tests.test_folder knowledge_project.tests.test_note knowledge_project.tests.test_message`
- Current sample result: 176 tests passed.

## Execution Schedule

| Phase | Priority | Target | Scope | Acceptance |
| --- | --- | --- | --- | --- |
| 1 | P0 | Stabilize release flow | Keep static asset versioning, document build/deploy order, verify `collectstatic` and service restart path | A fresh deploy loads new JS/CSS without manual cache clearing |
| 1 | P0 | Regression safety | Add a short smoke checklist for login, notes, settings, messages, moderation, vault | Core pages return 200 and core API actions pass after deploy |
| 2 | P1 | Note copy API | Implement copy note to folder, wire `MoveToDialog` copy mode, preserve title/content/tags/assets where applicable | User can copy a note into inbox or selected folder without changing source note |
| 2 | P1 | Profile visit statistics | Replace `views_count = 0` with real profile visit tracking and dashboard/profile display | Profile page and settings show real view counts with owner/self-view rules |
| 2 | P1 | Notification center | Use `UserNotification` for in-app notifications from comments, likes, follows, messages, moderation actions | User can view unread notifications and mark them read |
| 3 | P1 | Group messaging polish | Add group search, member roles, group avatar, ownership transfer, and clearer eligibility feedback | Group owners can manage groups without database/admin intervention |
| 3 | P2 | Public note discovery | Add public-note filters, sort modes, author/tag pages, and richer search | Public content can be browsed by tag/author/date/popularity |
| 3 | P2 | Moderation audit UX | Add report timelines, bulk operations, and sanction history cards | Admin can inspect a case history from one moderation detail panel |
| 4 | P2 | Vault recovery hardening | Add recovery-code lifecycle UI, unlock audit log, export confirmation flow | Vault recovery and export paths are visible, logged, and test-covered |
| 4 | P2 | Operational dashboard | Add deploy version, queue/cache status, disk/media growth, failed-login trends | Dashboard exposes actionable health signals, not only raw counters |
| 5 | P3 | Collaboration features | Shared folders, note-level collaborators, mention notifications, activity feed | Multiple users can collaborate on selected notes/folders with clear permissions |
| 5 | P3 | Product polish | Keyboard shortcuts, command palette, bulk note operations, saved searches | Heavy users can manage notes and messages faster from keyboard-first flows |

## Immediate Backlog

1. Implement note copy API and frontend copy mode. - Done in current optimization pass.
2. Add real profile visit statistics. - Done in current optimization pass.
3. Build the in-app notification center on top of `UserNotification`. - Done in current optimization pass.
4. Add deployment smoke checklist and run it before each production restart. - Done in `DEPLOYMENT_SMOKE_CHECKLIST.md`.

## P2/P3 Execution Guardrails

- Treat public discovery, moderation UX, vault recovery, operational dashboard, shared folders, and command-palette work as separate product increments.
- Each increment should ship behind existing auth/permission checks, include focused tests, and pass the deployment smoke checklist before production restart.
- Do not combine broad collaboration or search changes with release-flow fixes in the same deploy unless the production incident requires it.

## Verification Rule

Every completed phase should run:

```bash
python manage.py check --settings=Team_Project.settings_test
npm run build
python manage.py test --settings=Team_Project.settings_test knowledge_project
```
