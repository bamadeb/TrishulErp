# Trishul ERP – API

FastAPI + SQLAlchemy 2 on Amazon RDS for SQL Server. One deployable service (modular monolith),
one package per ERP module.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.13 itself): `winget install astral-sh.uv`
- Microsoft **ODBC Driver 18 for SQL Server**: `winget install --id Microsoft.msodbcsql.18 -e`.
  Driver 17 also works: set `TRISHUL_ODBC_DRIVER=ODBC Driver 17 for SQL Server`.
- **Trust the Amazon RDS certificate authority** (once per machine), or the encrypted connection
  fails with "certificate chain was issued by an authority that is not trusted". Download the bundle
  for the database's region from `https://truststore.pki.rds.amazonaws.com/<region>/<region>-bundle.pem`
  and add its root certificates to *Current User → Trusted Root Certification Authorities*. Don't
  work around it with `TrustServerCertificate`.

## Run

```sh
# create .env (git-ignored) with your TRISHUL_* settings; config.py lists and documents them all
uv sync
uv run alembic upgrade head                 # bring the database to the latest migration
uv run python scripts/create_dev_user.py    # once: the TRISHUL_DEV_USERNAME user for dev sign-in
# real users: create them in Cognito, then link: create_app_user.py <email> --cognito-sub <sub> --role ADMIN
uv run trishul-api                          # http://127.0.0.1:8000, docs at /api/v1/docs
```

With the API running, set `"useMockApi": false` in `frontend/apps/erp-web/public/config.json` and run
`npm start` in `frontend/`: the Angular dev server proxies `/api` to this API.

## Checks

```sh
uv run pytest                 # no database needed
uv run ruff check . && uv run ruff format --check .
uv run mypy                   # strict
```

## Layout

```
src/trishul_api/
  main.py              app factory: middleware, error handlers, routers, health checks
  config.py            settings from TRISHUL_* environment variables / .env
  db/
    engine.py          engine, pool reset, user_session() with SESSION_CONTEXT for row-level security
    models/            base.py (Base, Audited) + generated/: every table, one module per schema
  auth/
    tokens.py          Cognito access-token verification (JWKS); dev verifier for local work
    users.py           CurrentUser: roles, permissions, branches and brands from core.*
    deps.py            get_current_user, require_permission(...), get_scope (X-Branch-Id / X-Principal-Id), get_db
  common/              camelCase base model, paging, problem-details errors, If-Match / row_version
  modules/
    core/              GET /me, GET /core/lookups/{type}
    service/           GET /svc/service-calls
tests/
```

## Conventions

**API design follows [docs/Trishul_API_Standards.md](../docs/Trishul_API_Standards.md)**: URLs,
function names, status codes, errors, permissions and the Angular calling pattern.
`tests/test_api_conventions.py` checks every endpoint against it.

- **The SQL scripts in `database/` own the schema.** Never run `create_all()` or ORM migrations.
- **ORM models are generated** for all tables (220) by `scripts/generate_models.py`, from
  `database/01..07, 12`, the SQL in Alembic migrations, descriptions from `11_descriptions.sql`, and
  `scripts/model_options.toml` (audited tables, masked columns). Never edit `db/models/generated/`:
  change the SQL or the options file, then run `uv run python scripts/generate_models.py`.
  `tests/test_models.py` fails when they drift apart. CHECK value lists become `Literal` types
  (e.g. `ServiceCallCurrentStatus`); API schemas reuse them instead of repeating the values.
- **Every request uses `DbSession`.** It sets `app_user_id` in `SESSION_CONTEXT` (read-only) on a
  dedicated connection; the pool runs `sp_reset_connection` when the connection is returned, so one
  user's context can never leak to the next request.
- **Permissions** are `core.permission` codes: `dependencies=[Depends(require_permission("svc.call.assign"))]`.
- **Branch / brand**: use `ScopeDep`; it checks the headers against the user's roles. Row-level
  security is the backstop, not the only check.
- **Updates** take the record's `rowVersion` in `If-Match` (`common/concurrency.py`); models with
  `version_id_col` make SQLAlchemy reject stale updates, which the API returns as 409.
- **JSON is camelCase**; timestamps are UTC with an offset.
- **Layers**: `router.py` (HTTP) → `service.py` (business rules, the commit) → `repository.py` (queries).
  Read-only list and detail queries may skip the service and return response models straight
  from the repository (a projection of exactly the columns shown). **Anything that writes goes
  through a service.** Lists use `common.paging.order_by_sort()` and `paginate()`.
- **Modules plug in** by adding their router to `V1_ROUTERS` in `main.py`. The API is a sub-app
  mounted at `/api/v1`; in tests, override dependencies on the `api` fixture, not the root app.
- **Access rules** (who sees which branches and brands) live in `auth/access.py` as pure
  functions, mirroring `rls.fn_can_see`; change both together.
- **Request bodies extend `InputModel`** (`extra="forbid"`): unknown fields are rejected, so clients
  can't set fields an endpoint doesn't offer.
- **Auditing**: mark a model `Audited` and its inserts, updates and deletes are written to
  `core.audit_log` in the same transaction (`db/audit.py`). Put sensitive columns in `__audit_masked__`.
- **Document numbers** come from `common.numbering.next_document_no(...)`; it locks the series row
  until commit. On SQL Server, lock rows with `.with_hint(Model, "WITH (UPDLOCK, ROWLOCK)", "mssql")`:
  `.with_for_update()` is silently ignored by the dialect.
- **Operation ids are function names**, so keep them unique. After changing endpoints run
  `uv run python scripts/export_openapi.py`, then `npx nx run core-api:generate` in `frontend/`.
  CI fails if the committed `openapi.json` is stale.

## Migrations

Scripts `database/00`–`13` build schema v3. Later changes are Alembic revisions in `migrations/versions/`,
written as **idempotent SQL** (check the catalog first) and never autogenerated.

```sh
uv run alembic stamp v3_baseline       # once, on a database built from database/00..13
uv run alembic upgrade head --sql      # review the SQL
uv run alembic upgrade head            # apply; uses TRISHUL_MIGRATION_DB_USER / _PASSWORD if set
uv run alembic revision -m "add x"     # new revision from the template
```

## Deploy

`Dockerfile` builds a non-root image with ODBC Driver 18 for ECS Fargate. Set `TRISHUL_*` variables in
the task definition, `TRISHUL_DB_PASSWORD` from Secrets Manager, `TRISHUL_AUTH_MODE=cognito`.
Load balancer health check: `/health`; readiness including the database: `/health/ready`.
