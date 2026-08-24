# Branch Task Management System

Centralized task management for a four-branch organization (Tel Yitzhak,
Havatzelet, Nir Eliyahu, Emek Hefer). Every authenticated user sees every
task from every branch; roles differ only in what they may edit. Hebrew/RTL
is the primary UI language. Full spec: `../CLAUDE_CODE_PROMPT.md`.

## Status

**Phase 0 — Scaffold.** Project skeleton, settings, Docker files, empty apps.
No models, no views, no API yet — those are Phases 1–7.

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

Visit http://127.0.0.1:8000/ — Django's welcome page. http://127.0.0.1:8000/admin/
is live but empty until Phase 1 adds models and a superuser.

## Settings

`config/settings/base.py` holds everything shared; `dev.py` and `prod.py`
each import `*` from it and override only what differs (database, `DEBUG`,
email backend). Select with `DJANGO_SETTINGS_MODULE` in `.env`
(`manage.py` defaults to `config.settings.dev` if unset).

`AUTH_USER_MODEL = "accounts.User"` is set from the very first migration —
Django cannot swap the user model afterward without dropping the database.
`accounts/models.py` currently just extends `AbstractUser`; Phase 1 adds the
real fields (`full_name`, `phone`, `home_branch`, `role`).

## Known deviations from `CLAUDE_CODE_PROMPT.md`, agreed in the Phase 0 session

- **Assignment model**: one `assignee` FK (unchanged) **plus** a `TaskWatcher`
  M2M for status-change-only subscribers. Not in the original DDL.
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

## Commands

```bash
pytest              # run tests
ruff check .         # lint
black .              # format
python manage.py migrate
python manage.py createsuperuser
```
