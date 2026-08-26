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

**Phase 6 — Dashboard.** `GET /api/dashboard/summary` and
`GET /api/dashboard/breakdown?by=branch|assignee|status|priority|category`
(manager/admin only, `tasks/api.py`), backed by three new
`tasks/selectors.py` functions (`dashboard_counters`, `dashboard_breakdown`,
`needs_attention`). The `/tasks/dashboard/` HTML screen renders the four
counters (HTMX-polled every 60s via `/tasks/dashboard/counters/`), five
Chart.js charts fed client-side from the breakdown endpoint, and the
needs-attention table sorted by days-late.

**Phase 7 — KPIs and deployment.** §9's four KPIs
(`kpi_avg_days_to_close`, `kpi_opened_vs_closed_by_month`,
`kpi_on_time_closure_rate`, `kpi_performance_by_branch` in
`tasks/selectors.py`) behind `GET /api/dashboard/kpis` (manager/admin only),
surfaced on the dashboard screen as two headline stats, an opened-vs-closed
chart, and a performance-by-branch table. `GET /api/tasks/export` streams
the filtered task list as CSV (same visibility as the list endpoint — any
authenticated member), with an "ייצוא ל-CSV" link on the task list screen
that carries the active filters. `scripts/backup.sh` covers nightly DB +
media backups. See **Deployment** below for the runbook — reviewed by eye,
not yet run for real (no Docker on this dev machine).

## Local setup (dev — SQLite)

Neither Docker nor PostgreSQL is installed on the reference dev machine, so
local development runs on SQLite. Docker Compose + Postgres 16 is the
production target (`docker-compose.yml`) — see **Deployment** below.

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
- **`DJANGO_FORCE_HTTPS` env var, default `True`, added in Phase 7**: not in
  the original spec. `nginx.conf` only ever terminated plain HTTP (no TLS
  server block), but Phase 0's `prod.py` hardcoded `SECURE_SSL_REDIRECT =
  True` anyway — deployed as originally written, every request would have
  redirected to an `https://` nothing serves. The env var lets the runbook's
  bring-up window run HTTP-only before certbot exists, then flips to `True`
  (the default) once TLS is actually terminated.
- **`POSTGRES_PASSWORD` added to `.env.example`, Phase 7**: `docker-compose.yml`'s
  `db` service reads `${POSTGRES_PASSWORD}` via Compose's own `.env`
  substitution (separate from the `env_file: .env` Compose hands to `web`),
  but Phase 0 never added the variable — the `db` container would have
  started with an empty password, inconsistent with whatever password is
  embedded in `DATABASE_URL` for `web`. Both variables live in the same
  `.env` file and must match.

## Deployment

Single VPS, Docker Compose (`web` + `db` + `nginx`), ~$10/mo (spec §2/§13).
Reviewed by eye at Phase 7; not yet run for real — no Docker on this dev
machine, so **run through this on the actual target host before trusting
it**, and fix forward anything that doesn't match.

1. Provision a VPS, install Docker + the Compose plugin, clone this repo.
2. `cp .env.example .env` and fill in: `DJANGO_SECRET_KEY` (a fresh one —
   never reuse the dev value), `DJANGO_SETTINGS_MODULE=config.settings.prod`,
   `DJANGO_ALLOWED_HOSTS` (your domain), `POSTGRES_PASSWORD` and a matching
   `DATABASE_URL` (`postgres://branchtasks:<same password>@db:5432/branchtasks`),
   and `DJANGO_FORCE_HTTPS=False` for now (step 5 flips it).
3. `docker compose up -d --build`. The `web` entrypoint runs `migrate` and
   `collectstatic` automatically before gunicorn starts.
4. `docker compose exec web python manage.py createsuperuser`. Optionally
   `docker compose exec web env PYTHONUTF8=1 python manage.py seed_data` for
   demo data — skip this on a real deployment.
5. Point the domain's DNS at the VPS, then terminate TLS (e.g.
   `certbot --nginx` against the `nginx` container, or a separate
   Caddy/Traefik proxy in front of it — `nginx.conf` as committed has no TLS
   server block, so this step is required, not optional). Once HTTPS
   actually works, set `DJANGO_FORCE_HTTPS=True` in `.env` and
   `docker compose up -d` again to pick it up.
6. Add two cron entries on the host (spec §7, §13):
   ```
   0 7 * * * cd /path/to/branchtasks && docker compose exec -T web python manage.py run_task_alerts
   0 3 * * * cd /path/to/branchtasks && ./scripts/backup.sh >> /var/log/branchtasks-backup.log 2>&1
   ```
7. Verify: the four-branch task lifecycle works end-to-end over HTTPS, the
   dashboard loads for a manager account, and `run_task_alerts` /
   `scripts/backup.sh` both succeed when run manually once before trusting
   the cron entries.

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
