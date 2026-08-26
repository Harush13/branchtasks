# Branch Task Management System

Centralized task management for a four-branch organization (Tel Yitzhak,
Havatzelet, Nir Eliyahu, Emek Hefer). Every authenticated user sees every
task from every branch; roles differ only in what they may edit. Hebrew/RTL
is the primary UI language. Full spec: `../CLAUDE_CODE_PROMPT.md`.

## Status

**Phase 5 — Notifications.** `tasks/management/commands/run_task_alerts.py`
sends the two scheduled §7 alerts (`due_soon` at exactly 2 days out,
`overdue` for anything active past its due date, the latter also fanning out
to every manager/admin) once a day via cron:

```
0 7 * * * cd /path/to/branchtasks && python manage.py run_task_alerts
```

Both the scheduled alerts and the three immediate triggers from Phase 2 now
also send email through `notifications/services.py:send_notification_email`,
gated on `EMAIL_ENABLED` (still off by default in dev — console backend).
Idempotency (`tests/test_run_task_alerts.py::test_running_twice_is_idempotent`)
proves the Phase 5 gate: running the job twice does not double any
notification, because every call still goes through the same
`get_or_create` in `notify()` that Phase 2's immediate triggers already used.
Dashboard is Phase 6.

## Local setup (dev — SQLite)

Neither Docker nor PostgreSQL is installed on the reference dev machine, so
local development runs on SQLite. Docker Compose + Postgres 16 is the
production target (`docker-compose.yml`) and gets validated for real at
Phase 7.

```bash
python -m venv .venv
source .venv/Scripts/activate       # Windows Git Bash; use .venv\Scripts\activate on cmd
pip install -e ".[dev]"
cp .env.example .env                # fill in DJANGO_SECRET_KEY etc.
python manage.py check
python manage.py migrate
pytest
python manage.py runserver
```

Visit http://127.0.0.1:8000/admin/ (run `createsuperuser` first). Populate demo
data with `python manage.py seed_data` — on Windows, prefix with `PYTHONUTF8=1`
or the Hebrew branch/category names crash on the default `cp1252` console
encoding.

## Settings

`config/settings/base.py` holds everything shared; `dev.py` and `prod.py`
each import `*` from it and override only what differs (database, `DEBUG`,
email backend). Select with `DJANGO_SETTINGS_MODULE` in `.env`
(`manage.py` defaults to `config.settings.dev` if unset).

`AUTH_USER_MODEL = "accounts.User"` was set from the very first migration —
Django cannot swap the user model afterward without dropping the database.
`accounts/models.py` now carries the full field set from spec §3.2
(`full_name`, `phone`, `home_branch`, `role`).

## Known deviations from `CLAUDE_CODE_PROMPT.md`, agreed in planning sessions

- **Assignment model**: one `assignee` FK (unchanged) **plus** a plain
  `watchers` M2M on `Task` for status-change-only subscribers. (A dedicated
  `TaskWatcher` through-model was floated in the Phase 0 session but dropped
  in Phase 1 — nothing needs per-watch metadata, so a bare M2M is simpler.)
  Not in the original DDL.
- **User deactivation**: blocked while the user holds active tasks, rather
  than silently orphaning them.
- **`due_date`**: optional at creation, as the DDL already implies.
- **Cancel transition**: manager/admin only, narrowing §4's transition table.
- **Email**: written behind `EMAIL_ENABLED` (default off); console backend
  in dev. In-app bell is the only live channel until real SMTP is supplied.
- **`ref` generation**: derived from the primary key (`TSK-` + zero-padded
  pk) rather than a locked counter table, so it's race-free on both SQLite
  and Postgres without row locking. Trade-off: gaps in numbering on rolled
  back inserts.
- **Local dev database**: SQLite, not Postgres. The only spec feature this
  doesn't port cleanly is the `he-IL-x-icu` Hebrew collation (§10.4) — that
  gets isolated to one sort helper in `tasks/selectors.py` (Phase 2+) and
  re-verified on real Postgres at Phase 7.
- **Hebrew status/priority labels**: carried as `TextChoices`/`IntegerChoices`
  labels on `Task` (not a lookup table like Branch/Category), since the §4
  state machine already hardcodes the five statuses — a lookup-table row
  would have no transitions. Satisfies §10.6's "from the model, not
  gettext" without an extra table.
- **Deactivation guard and attachment validators**: pulled forward into
  Phase 1 (`accounts/validators.py`, `tasks/validators.py`) instead of
  waiting for their nominal phases, because Django Admin could violate both
  the moment the models existed.
- **Notification triggers pulled forward**: the three immediate §7 triggers
  (`assigned`, `reassigned`, `urgent`) were built in Phase 2 alongside
  `tasks/services.py` instead of waiting for Phase 5, since `change_status`'s
  own docstring in the spec ends with "fire notifications" — building the
  triggers now means the service call sites are never rewritten later. The
  scheduled `run_task_alerts` job, email, and the in-app bell UI are still
  Phase 5.
- **Notification dedup is permanent, not just idempotency**: the
  `UNIQUE(task, user, kind)` constraint that makes the Phase 5 daily job safe
  to rerun also means a user reassigned to the same task twice only ever gets
  one `reassigned` row — the second reassignment is silently a no-op on the
  notification side. This is the spec's own trade-off (§7), noted here so it
  isn't later mistaken for a bug.
- **`TaskAdmin.status` is read-only on change**: closes a gap Phase 1 left
  open — §4 says no admin action may write `status` directly, only
  `change_status()` may. Still editable on *add*, since a new task's status
  is just its default `new`.
- **Email fires for all five notification kinds, not just the two scheduled
  ones**: §7 scopes "email via SMTP" to the notification engine as a whole,
  not to `run_task_alerts` specifically, and `notify()` is the single choke
  point both halves already shared for the DB row — routing email through
  the same function (only on actual creation, not a `get_or_create` no-op)
  meant no call site needed to know or care which channel fired.

## Commands

```bash
pytest                          # run tests
ruff check .                    # lint
black .                         # format
python manage.py migrate
python manage.py createsuperuser
PYTHONUTF8=1 python manage.py seed_data   # 4 branches, 8 categories, 6 demo users
```

Demo user passwords are all `demo1234` (dev only, refused when `DEBUG=False`).
