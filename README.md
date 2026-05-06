# Oceanomics Database Explorer (Django + PostgreSQL)

Schema-driven frontend for the Oceanomics / Ocean Genomes database. The app reads a CSV schema export, renders a catalog of relations, and opens live table data from PostgreSQL when those relations are available on the configured explorer connection.

## What this app now does

- user login/logout
- schema dashboard for the exported database structure
- searchable catalog of tables and views
- live table browsing with pagination, search, and sort
- row inspection for relations with primary keys in the export
- per-user saved table layouts (visible columns + default sort)
- workbook-style worksheet navigation for lab workflows
- editable `1.MetaData` specimen intake page over the `sample` table
- editable `3.RNAExtractions` worksheet over the `rna_extraction` table
- per-user joined views that combine a base table with parent-table context through foreign keys

## Project structure

- `lab_portal/` Django project settings and URL routing
- `portal/` schema loader, data explorer views, saved table views, tests
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

## 2. Configure PostgreSQL and schema metadata

Edit `.env` and set:

- `APP_POSTGRES_DB`
- `APP_POSTGRES_USER`
- `APP_POSTGRES_PASSWORD`
- `APP_POSTGRES_HOST`
- `APP_POSTGRES_PORT`
- `OCEANOMICS_POSTGRES_DB`
- `OCEANOMICS_POSTGRES_USER`
- `OCEANOMICS_POSTGRES_PASSWORD`
- `OCEANOMICS_POSTGRES_HOST`
- `OCEANOMICS_POSTGRES_PORT`
- `SCHEMA_METADATA_PATH`

`SCHEMA_METADATA_PATH` should point at your exported schema CSV, for example:

```bash
SCHEMA_METADATA_PATH=/Users/tylerpeirce/oceanomics_db_frontend/db_schema.csv
```

If `SCHEMA_METADATA_PATH` is not set, the app tries to auto-discover the newest matching `db_schema.csv` near the project root.

The app uses two database roles:

- `default`: Django app database for auth, sessions, admin, and saved table views
- `oceanomics`: PostgreSQL connection for live Oceanomics table browsing

Recommended setup:

- `APP_POSTGRES_*` points to a separate Postgres database just for this Django app
- `OCEANOMICS_POSTGRES_*` points to the existing Oceanomics database

If `APP_POSTGRES_DB` is empty/unset, Django falls back to local SQLite for the app tables.
If `OCEANOMICS_POSTGRES_DB` is empty/unset, the explorer falls back to `POSTGRES_*` for backward compatibility. If neither is set, live Oceanomics table browsing is unavailable.

## 3. Initialize Django tables and create an admin user

```bash
python manage.py migrate
python manage.py createsuperuser
```

`migrate` creates Django auth/session tables and the app's saved-view tables in the `default` app database. It does not create or alter the Oceanomics PostgreSQL relations described in the schema export.

Optional demo explorer assets:

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
- Review schema coverage and key tables on the dashboard
- Open `Worksheets` for the Excel-style lab tabs
- Use `1.MetaData` to add or edit specimen intake rows in the `sample` table
- Use `3.RNAExtractions` to add or edit base RNA extraction rows while viewing linked specimen and tissue context
- Open shared lab workflow presets from the dashboard or `Saved Views`
- Use `Saved Views` -> `New joined view` to build read-only multi-table worksheet views without writing SQL
- Browse all exported relations from `Tables`
- Open a relation to search, sort, paginate, and inspect rows
- Save table-specific layouts from the table detail page
- Manage users and saved layouts in Django admin (`/admin/`)

Current worksheet coverage:

- `Summary` and the other workbook tabs route to preset or explorer-style views
- `1.MetaData` is the first dedicated editable worksheet page
- `3.RNAExtractions` is now an editable base-table worksheet with derived specimen/tissue context
- joined views are read-only and currently follow foreign keys from the base table to parent tables
- `2.Tissue`, extraction tabs, and sequencing still need dedicated write workflows

## Local app Postgres on this machine

I set up a local Postgres instance for the Django app database with these details:

- data directory: `/Users/tylerpeirce/oceanomics_db_frontend/.local_postgres/data`
- socket directory: `/Users/tylerpeirce/oceanomics_db_frontend/.local_postgres/socket`
- log file: `/Users/tylerpeirce/oceanomics_db_frontend/.local_postgres/log/postgres.log`
- host: `127.0.0.1`
- port: `5433`
- database: `oceanomics_frontend`
- user: `oceanomics_frontend_app`

Start it again later with:

```bash
/usr/local/opt/postgresql@16/bin/pg_ctl \
  -D /Users/tylerpeirce/oceanomics_db_frontend/.local_postgres/data \
  -l /Users/tylerpeirce/oceanomics_db_frontend/.local_postgres/log/postgres.log \
  start \
  -o "-p 5433 -h 127.0.0.1 -k /Users/tylerpeirce/oceanomics_db_frontend/.local_postgres/socket"
```

Stop it with:

```bash
/usr/local/opt/postgresql@16/bin/pg_ctl \
  -D /Users/tylerpeirce/oceanomics_db_frontend/.local_postgres/data \
  stop
```

## Notes

- Relation type is inferred from the schema export. Names ending in `_view` are treated as views in the UI.
- Live row detail depends on primary key columns being present in the CSV export.
- If a relation exists in the CSV but not in the configured explorer database connection, the schema metadata still renders and the live data panel shows a database error instead of rows.
- The old `POSTGRES_*` environment variables are still accepted as a fallback for the Oceanomics explorer connection.
