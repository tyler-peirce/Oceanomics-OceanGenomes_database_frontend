# Lab Data Portal (Django + PostgreSQL)

Web frontend starter for a small lab team (about 10 users) with:

- user login/logout
- per-user saved views (column layout, filters, default ordering)
- dashboard reporting for operations and management
- validated data entry (form validation + model/database constraints)
- browser-based UI for daily lab use

## Project structure

- `lab_portal/` Django project settings and URL routing
- `portal/` models, forms, views, admin, tests, and seed command
- `templates/` HTML templates
- `static/` CSS and JS assets

## 1. Setup

```bash
cd /scratch/pawsey0964/tpeirce/database_stuff
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Configure PostgreSQL

Edit `.env` and set:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

If `POSTGRES_DB` is empty/unset, the app falls back to SQLite for local testing.

## 3. Initialize database and create admin user

```bash
python manage.py migrate
python manage.py createsuperuser
```

Optional demo data:

```bash
python manage.py seed_demo_data
```

## 4. Run in browser

```bash
python manage.py runserver 0.0.0.0:8000
```

Open:

- `http://127.0.0.1:8000/`

## Usage

- Sign in at `/accounts/login/`
- Create/update records at `Records` and `+ New Record`
- Build user-specific presets in `View Presets`
- Review KPIs/charts on the `Dashboard`
- Manage users/permissions/groups in Django admin (`/admin/`)

## Data quality controls implemented

- sample code regex format check: `PREFIX-YYYY-NNNN`
- QC score bounds: 0 to 100
- no future `received_at` values
- `processed_at` cannot predate `received_at`
- `processed_at` required for completed/failed records
- DB-level constraints for key date/QC rules

## Suggested production hardening

- run with Gunicorn + reverse proxy (Nginx/Traefik)
- set `DJANGO_DEBUG=0`
- set secure `DJANGO_SECRET_KEY`
- set explicit `DJANGO_ALLOWED_HOSTS`
- enforce HTTPS and strong password policies
