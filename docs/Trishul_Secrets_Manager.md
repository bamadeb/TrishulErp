# AWS Secrets Manager integration

How the Trishul ERP backend stores and reads confidential values, and the AWS resources it needs.

The backend runs as a **FastAPI app on ECS Fargate** (see the Dockerfile and the implementation guide).
It reads secrets at runtime through the AWS SDK (`boto3`) using the **ECS task role** — there are no AWS
Lambda functions in the application. The only AWS-managed Lambda involved is the one Secrets Manager
provisions for RDS rotation, which is part of the Secrets Manager service, not of this application.

> **Already provisioned (dev).** In **us-east-1** (account `886375648882`):
> - **`trishul/dev/db-app`** holds the application login **`trishul_app`** (data rights, subject to RLS).
> - **`trishul/dev/db-migration`** holds the migration login **`trishul_migrator`** (DDL rights).
> - **`trishul/dev/cognito`** holds the Cognito identifiers (region, userPoolId, appClientId). These are
>   public, so this secret centralises config rather than hiding anything; verified the API resolves them
>   and reaches Cognito (`admindemo` = active). The local `.env` holds only `TRISHUL_COGNITO_SECRET_ID`
>   and `TRISHUL_SECRETS_REGION=us-east-1` for auth, plus `TRISHUL_AUTH_MODE`/`TRISHUL_DEV_USERNAME`.
>
> Both logins were created from `database/20_least_privilege_logins.sql`; their passwords were generated,
> set on the logins, and stored only in these secrets (no human ever typed them). The local `.env` holds
> **only** `TRISHUL_DB_SECRET_ID=trishul/dev/db-app` and `TRISHUL_MIGRATION_DB_SECRET_ID=trishul/dev/db-migration`
> for the database — host, port, database name and the login all come from the secrets. Verified: the API
> connects as `trishul_app` (not `db_owner`), and `alembic upgrade head` runs as `trishul_migrator`
> (head `0003`). The RDS master user `admin` is no longer used by the app or stored in the project. The
> `prod`/`uat` secrets and logins are still to be created (§11).

---

## 1. What is a secret, and what is not

| Value | Confidential? | Where it lives |
|---|---|---|
| Application DB password | **Yes** | Secrets Manager (`TRISHUL_DB_SECRET_ID`) |
| Migration (DDL) DB password | **Yes** | Secrets Manager (`TRISHUL_MIGRATION_DB_SECRET_ID`) |
| Integration credentials (Tally, GSP, DMS, WhatsApp), search-hash key | **Yes** (later) | Secrets Manager |
| Cognito region, **User Pool ID**, **App Client ID** | No — public identifiers | Secrets Manager (`TRISHUL_COGNITO_SECRET_ID`) to centralise config, or env; the browser still gets them via `config.json` |
| DB host, port, database name | No | Env vars |
| CORS origins, log level, cache TTLs | No | Env vars |

Access tokens, refresh tokens, DB passwords and client secrets are **never** sent to the frontend. The
browser receives only the public Cognito IDs (in `config.json`) and short-lived tokens the user's own
sign-in produces.

---

## 2. Secret naming convention

```
trishul/<environment>/<purpose>
```

| Secret | Example name |
|---|---|
| Application DB login | `trishul/prod/db-app` |
| Migration DB login | `trishul/prod/db-migration` |

Use a separate secret per environment (`dev`, `test`, `uat`, `prod`) so a lower environment can never read
a production credential.

---

## 3. Secret format

Store the DB logins in the **same JSON shape AWS RDS uses for managed rotation**, so RDS can rotate them in
place:

```json
{
  "username": "trishul_app",
  "password": "********",
  "engine": "sqlserver",
  "host": "trishulerp.xxxx.us-east-1.rds.amazonaws.com",
  "port": 1433,
  "dbname": "TrishulDev"
}
```

The application reads `username`, `password`, `host`, `port` and `dbname` from the secret. Host, port and
database name are read **once at startup**; the username and password are injected per connection so a
rotated password is picked up without a restart. `TRISHUL_DB_HOST`/`PORT`/`NAME` act only as a fallback for
a field the secret omits, so the running environment needs **no DB details beyond the secret id**.

---

## 4. Environment configuration

Set these as **ECS task environment variables** (identifiers only — never secret values):

```
TRISHUL_ENVIRONMENT=prod
TRISHUL_DB_SECRET_ID=trishul/prod/db-app
TRISHUL_MIGRATION_DB_SECRET_ID=trishul/prod/db-migration
TRISHUL_COGNITO_SECRET_ID=trishul/prod/cognito
TRISHUL_SECRETS_REGION=us-east-1          # region for ALL Secrets Manager reads; set it explicitly
TRISHUL_SECRETS_CACHE_SECONDS=300         # optional; default 300
```

Set `TRISHUL_SECRETS_REGION` explicitly: it is the region used to reach Secrets Manager, and once the
Cognito region comes from a secret it can no longer be the fallback for it. The Cognito identifiers may
instead be given inline (`TRISHUL_COGNITO_REGION`/`USER_POOL_ID`/`APP_CLIENT_ID`) if you prefer not to use
a secret for them.

The secret supplies host, port, database name, username and password, so **no `TRISHUL_DB_*` values are
needed** when `TRISHUL_DB_SECRET_ID` is set. (`TRISHUL_DB_HOST`/`PORT`/`NAME` may still be set as a
fallback, but are not required; never set `TRISHUL_DB_USER`/`TRISHUL_DB_PASSWORD` alongside a secret.)

**Local development** can either (a) use the dev secret, as the committed setup now does — the only DB line
in `.env` is `TRISHUL_DB_SECRET_ID=trishul/dev/db-app`, and the AWS CLI profile `TRISHUL_AWS_PROFILE`
authenticates the read; or (b) run fully offline by clearing `TRISHUL_DB_SECRET_ID` and setting
`TRISHUL_DB_HOST`/`NAME`/`USER`/`TRISHUL_DB_PASSWORD` in the git-ignored `.env` instead.

Behaviour matrix:

| `TRISHUL_DB_SECRET_ID` | Source of the DB login |
|---|---|
| empty (local/dev) | `TRISHUL_DB_USER` / `TRISHUL_DB_PASSWORD` env |
| set (AWS) | Secrets Manager, refreshed in the background |

Migrations use `TRISHUL_MIGRATION_DB_SECRET_ID` if set, else `TRISHUL_MIGRATION_DB_USER/PASSWORD`, else the
application's own DB credentials.

---

## 5. IAM — least privilege

Attach to the **ECS task role** (not the execution role) a policy that grants read access only to the
secrets this service uses:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadTrishulSecrets",
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:<account>:secret:trishul/prod/db-app-*",
        "arn:aws:secretsmanager:us-east-1:<account>:secret:trishul/prod/db-migration-*",
        "arn:aws:secretsmanager:us-east-1:<account>:secret:trishul/prod/cognito-*"
      ]
    },
    {
      "Sid": "DecryptWithCmk",
      "Effect": "Allow",
      "Action": ["kms:Decrypt"],
      "Resource": "arn:aws:kms:us-east-1:<account>:key/<secrets-cmk-id>",
      "Condition": {
        "StringEquals": { "kms:ViaService": "secretsmanager.us-east-1.amazonaws.com" }
      }
    }
  ]
}
```

- The trailing `-*` matches the random suffix Secrets Manager appends to a secret's ARN.
- The `kms:Decrypt` statement is required **only if** the secret is encrypted with a customer-managed KMS
  key. With the default `aws/secretsmanager` key it can be omitted.
- No `secretsmanager:PutSecretValue`/`UpdateSecret` — the app never writes secrets.
- **No AWS access keys** are configured anywhere. Credentials come from the task role via the default
  provider chain; locally the AWS CLI profile `TRISHUL_AWS_PROFILE` is used.

---

## 6. Encryption, transport and auditing

- **At rest:** Secrets Manager encrypts with KMS (default `aws/secretsmanager` or a customer-managed CMK).
- **In transit:** the SDK calls Secrets Manager and SQL Server over TLS (`Encrypt=yes` is already set for
  the DB).
- **Audit:** every `GetSecretValue` is recorded in **AWS CloudTrail** (management + data events). Rotation
  events are logged too. Enable a CloudTrail trail covering Secrets Manager if one is not already active.

---

## 7. Rotation and caching (no application downtime)

- The provider caches each secret for `TRISHUL_SECRETS_CACHE_SECONDS` (default 5 min), so Secrets Manager
  is off the request hot path.
- The DB login is injected **per physical connection** (SQLAlchemy `do_connect`), not baked into the engine
  URL. When the password rotates:
  - existing pooled connections keep working (SQL Server does not drop them on a password change);
  - the next new connection after the cache lapses uses the new password;
  - if a new connection is rejected with a login error (SQLSTATE 28000 / error 18456), the cached secret is
    dropped immediately and the following connection re-reads the rotated value — so recovery does not wait
    for the TTL.
- `pool_pre_ping=True` and `pool_recycle=1800` already discard stale/broken connections safely.

**To enable automatic rotation** (optional): in Secrets Manager, turn on rotation for `trishul/prod/db-app`
using the AWS-provided SQL Server rotation function and a rotation window of e.g. 30 days. That rotation
function is an AWS-managed Lambda belonging to the Secrets Manager service; it is **not** part of the
FastAPI application and does not change the ECS architecture. Prefer **single-user** rotation for the app
login. If you must avoid any Lambda entirely, rotate manually or on a schedule by updating the secret value
— the application picks up the new value the same way.

---

## 8. Deployment

1. Create the secrets (`trishul/<env>/db-app`, `-migration`) with the JSON in §3.
2. Attach the IAM policy in §5 to the ECS task role.
3. Set the task environment variables in §4 (no `TRISHUL_DB_PASSWORD`).
4. Deploy the new task definition. The one-off `alembic upgrade head` task reads the migration secret the
   same way, **before** the API tasks start (existing deploy flow).
5. Check `/health/ready` — it runs `SELECT 1`, which forces a real connection using the secret.

## 9. Rollback

Because the secret path is opt-in per environment, rollback is config-only and needs no code change:

- **Fast fallback:** set `TRISHUL_DB_USER` / `TRISHUL_DB_PASSWORD` on the task and clear
  `TRISHUL_DB_SECRET_ID`, then redeploy. The app reverts to the env-based login immediately.
- **Code rollback:** deploy the previous image; it never read the new settings, so no data or schema change
  is involved.
- **Bad rotation:** restore the previous secret value from the Secrets Manager version history
  (`AWSPREVIOUS` staging label); the app re-reads it within the cache TTL, or at once after a login error.

---

## 10. Changes in this integration

**New files**
- `backend/src/trishul_api/secrets.py` — reusable secret provider: swappable fetcher (AWS / in-memory),
  TTL cache, JSON parsing, safe errors that never contain secret values.
- `backend/src/trishul_api/db/credentials.py` — parses the RDS-format DB secret; redacts the password in
  `repr`.
- `backend/src/trishul_api/auth/cognito_secret.py` — fills the Cognito region/userPoolId/appClientId from
  a secret at startup (env fallback). Config, `main.py` and `.env` updated accordingly; `config.py` accepts
  `TRISHUL_COGNITO_SECRET_ID` as an alternative to the inline Cognito ids.
- `backend/tests/test_secrets.py` — caching, JSON parsing, AWS fetcher (fake client), credential parsing,
  connection-string assembly, engine wiring.
- `docs/Trishul_Secrets_Manager.md` — this document.

**Changed files**
- `backend/src/trishul_api/config.py` — added `db_secret_id`, `migration_db_secret_id`, `secrets_region`,
  `secrets_cache_seconds`, and an `aws_region` helper. Identifiers only.
- `backend/src/trishul_api/db/engine.py` — when a secret is configured, host/port/dbname are read from it
  (env as fallback) and the login is injected at connect time, with cache refresh on a login failure, and
  `Trusted_Connection` stripped so SQL auth is used. Env path unchanged when no secret is configured.
- `backend/.env` (local, git-ignored) — DB host/port/name/user/password removed; only `TRISHUL_DB_SECRET_ID`
  remains for the database.
- `database/20_least_privilege_logins.sql` — idempotent script creating the `trishul_app` and
  `trishul_migrator` logins with least-privilege grants.
- `backend/src/trishul_api/main.py` — builds the secret provider in the composition root and passes it to
  the engine; stored on app state for future consumers.
- `backend/migrations/env.py` — migrations resolve their DDL login from Secrets Manager when configured.
- `backend/pyproject.toml` — added the `secretsmanager` boto3 type stubs (dev only).

**Security improvements**
- DB password is no longer required in the ECS environment; it is read from Secrets Manager with a
  least-privilege task-role policy.
- Password is injected per connection, never baked into the engine URL or logged (`DbCredentials.__repr__`
  redacts it; `SecretStr` still guards env-based config).
- Secret fetch errors log only the error *type* and the secret *id*, never the value.
- Supports rotation without downtime and recovers automatically from a rejected login.
- Public config (Cognito IDs, host) kept separate from confidential values.

**Test results** — `uv run pytest`: **176 passed**. `ruff check` + `ruff format --check`: clean. `mypy`
(strict): clean. `alembic upgrade head --sql`: renders. Live read-only connection via the env path to RDS:
OK (DB `TrishulDev`).

---

## 11. Remaining manual AWS steps

These require AWS console/CLI access and are **not** done by the code:

1. Create the Secrets Manager secrets per environment (§2–§3).
2. Create a least-privilege **application DB login** (data rights) and a **migration login** (DDL rights)
   by running `database/20_least_privilege_logins.sql` as the RDS master user; put each login's password in
   its secret (`username` `trishul_app` / `trishul_migrator`). This replaces the `admin` master user, which
   the dev secret currently holds.
3. Attach the IAM policy (§5) to the ECS task role.
4. Set the ECS task environment variables (§4).
5. (Optional) Enable rotation on the DB-app secret (§7).
6. Ensure a CloudTrail trail covers Secrets Manager (§6).
