# Trishul ERP: FastAPI backend implementation guide

**Audience:** the backend team building the Trishul ERP API.
**Scope:** architecture, structure, database, API design, security, operations, testing and the phased plan for an ERP serving about 700 employees (office staff, field engineers, management and a customer portal).
**Status (2026-10-26):** the foundation is in `backend/` and runs: settings, SQL Server engine, Cognito token checks, permissions, branch / brand scope, row-level-security session context, error format, paging, and the first endpoints (`/me`, lookups, service calls). It has 31 tests and passes ruff and strict mypy. It has **not yet run against the real RDS database**. Sections marked ✅ describe code that exists; everything else is to be built.

---

## 0. Decisions at a glance

| Topic | Decision | Why |
|---|---|---|
| Shape | **Modular monolith**: one deployable FastAPI service, one package per ERP module | Sales, inventory and accounts must post in **one transaction** (an invoice moves stock and writes GL entries). 700 users don't need microservices. |
| Database | **SQL Server on Amazon RDS** (existing, 220 tables) | Already built; upgrade from Express to **Standard Edition** before go-live (section 3.1) |
| DB access | **SQLAlchemy 2 (sync) + pyodbc + ODBC Driver 18** | Python has no mature native-async SQL Server driver; sync endpoints run in FastAPI's thread pool, which is plenty at this scale |
| Schema ownership | **The SQL scripts in `database/` own the schema**; later changes are versioned migrations written in SQL | The schema was designed first, with RLS, CHECKs and filtered indexes that ORMs don't generate well |
| Sign-in | **Amazon Cognito** (OIDC, authorization code + PKCE). The ERP stores **no passwords**. | Password hashing, lockout, MFA, refresh tokens and revocation come from a managed service instead of hand-written code |
| Authorization | Permission codes from `core.permission`, roles per branch, brand access, **row-level security** in SQL Server as the backstop | Already modelled in the schema |
| Background work | **Celery + Redis (ElastiCache)** worker and scheduler | SQL Server Express has no SQL Agent; ERP needs scheduled and long-running jobs |
| Hosting | **ECS Fargate** behind an ALB, AWS WAF, Secrets Manager, CloudWatch | Managed, scales by task count, no servers to patch |
| Infrastructure as code | **AWS CDK in Python** | The team already writes Python |

---

## 1. System architecture

```
 Browsers (Angular, Angular Material)      Field app (Ionic/Capacitor)      Customer portal
                 │                                   │                             │
                 └──────────────── HTTPS (TLS 1.2+) ─┴─────────────────────────────┘
                                         │
                         CloudFront (static Angular)  +  AWS WAF
                                         │
                              Application Load Balancer
                                         │
              ┌──────────────────────────┴───────────────────────────┐
              │         ECS Fargate: trishul-api (2+ tasks, 2 AZs)   │
              │  FastAPI  ─ auth ─ modules (core, svc, inv, pur,     │
              │             sal, pre, hr, acc, int, rpt)             │
              └───────┬──────────────────┬─────────────────┬─────────┘
                      │                  │                 │
          RDS SQL Server (Standard,   ElastiCache Redis   S3 (attachments,
          Multi-AZ, KMS-encrypted)    (cache, queue,       imports, PDFs;
                      ▲               rate limits)          SSE-KMS)
                      │                  │
              ┌───────┴──────────────────┴───────┐
              │ ECS Fargate: trishul-worker      │──► Tally, Atlas Copco DMS, Grey8,
              │ Celery worker + beat scheduler   │    e-invoice / e-way bill (GSP),
              └──────────────────────────────────┘    SES e-mail, WhatsApp, FCM push
                         Cognito ◄── token checks (JWKS) from API
```

**How a request is handled:**
1. The **client** sends a Cognito access token plus `X-Branch-Id` / `X-Principal-Id` headers.
2. The **API** checks the token's signature, issuer, expiry and client (`auth/tokens.py`).
3. The **API** loads the user's roles, permissions, branches and brands. This is cached for 60 s (`auth/users.py`).
4. The **route** checks the permission code (`require_permission`), then the branch / brand scope (`get_scope`).
5. The **API** opens a DB session tagged with `SESSION_CONTEXT('app_user_id')`, so SQL Server row-level security applies (`db/engine.py`).
6. The **service layer** runs the business rules in **one transaction**, writes the audit rows and commits.
7. The **API** returns camelCase JSON. Errors use RFC 7807 problem details.

**Sizing for 700 employees.** Assume about 250 people use the system at the same time at peak, at about 0.1–0.2 requests/s each: **25–50 requests/s**, with bursts at month-end.

| Resource | Sizing |
|---|---|
| ECS tasks | 2 Fargate tasks (1 vCPU, 2 GB) × 2 Uvicorn workers |
| Threads | 40 threads per worker (FastAPI's default thread pool) for sync endpoints |
| Headroom | Covers more than 10× the expected load |
| Bottleneck | The database, so effort goes into queries and indexes, not into async Python |

---

## 2. Project structure

Today's layout (✅) plus the parts to add:

```
backend/
├── pyproject.toml               dependencies (uv), ruff, mypy, pytest settings
├── uv.lock                      pinned versions: commit it
├── Dockerfile                   ✅ non-root image with ODBC Driver 18
├── .env                         local settings only (git-ignored); every TRISHUL_* setting is in config.py
├── migrations/                  ⬜ Alembic: SQL migrations after the v3 baseline
├── infra/                       ⬜ AWS CDK app (VPC, ECS, ALB, WAF, Redis, alarms)
├── src/trishul_api/
│   ├── main.py                  ✅ app factory: middleware, error handlers, routers, health
│   ├── config.py                ✅ Settings from TRISHUL_* variables
│   ├── db/
│   │   ├── engine.py            ✅ pool, connection reset, user_session() with SESSION_CONTEXT
│   │   ├── audit.py             ⬜ flush listener that writes core.audit_log
│   │   └── models/              ✅ all 220 tables, generated from database/*.sql (scripts/generate_models.py)
│   ├── auth/                    ✅ tokens.py, access.py (rules), user_repository.py, users.py (cache), deps.py
│   ├── common/
│   │   ├── schemas.py           ✅ ApiModel (camelCase), Page, UtcDateTime, RowVersion
│   │   ├── errors.py            ✅ ApiError hierarchy, problem+json handlers
│   │   ├── concurrency.py       ✅ If-Match / row_version
│   │   ├── numbering.py         ⬜ document numbers from core.number_series
│   │   ├── crypto.py            ⬜ field encryption (KMS) for PAN, bank accounts, salary
│   │   └── security.py          ⬜ security headers, rate limits
│   ├── modules/                 one package per DB schema
│   │   ├── core/                ✅ /me, lookups; ⬜ masters, admin
│   │   ├── service/             ✅ call register; ⬜ create, assign, visits, reports, parts
│   │   │   ├── router.py        HTTP only: parse, authorize, call service, shape response
│   │   │   ├── schemas.py       request / response models
│   │   │   ├── service.py       ⬜ business rules + transaction boundary
│   │   │   ├── repository.py    queries; no business rules, no commits
│   │   │   └── __init__.py      the module's public API for other modules
│   │   ├── inventory/  purchase/  sales/  presales/  hr/  accounts/  integration/  reports/
│   └── worker/                  ⬜ Celery app, schedules, tasks
└── tests/
    ├── unit/                    services and helpers, no I/O
    ├── api/                     ✅ routers with dependency overrides (no DB)
    ├── integration/             ⬜ real SQL Server in Docker (Testcontainers)
    └── load/                    ⬜ Locust scenarios
```

**What each layer does:**

| Layer | Does | Never does |
|---|---|---|
| `router.py` | HTTP mapping, permission dependencies, status codes | SQL, business rules |
| `schemas.py` | Validation and JSON shape (Pydantic) | Database access |
| `service.py` | Business rules, calls to other modules, the **commit** | Read HTTP headers |
| `repository.py` | Building and running queries | Commit, apply rules |
| `db/models/` | Column mappings, **generated** from the SQL scripts | Logic, hand edits |

**Read-only queries (agreed 2026-10-26):** list and detail endpoints may skip `service.py`, and their repository may return the response model directly. Such a query selects exactly the columns the screen shows, so a mapping step would only copy fields. **Every write goes through `service.py`**, which works with ORM objects and owns the commit. Shared helpers keep list queries consistent: `common/paging.py` (`order_by_sort`, `paginate`).

**Rules between modules:** a module may import `auth`, `common` and `db`, plus **another module's package root only**. For example, `from trishul_api.modules.inventory import reserve_stock` is allowed; reaching into `inventory.repository` is not. A test in CI checks the imports (an import-linter contract), the same way Nx enforces this on the frontend.

---

## 3. Database integration

### 3.1 Database and edition

- **Keep SQL Server on RDS.** The schema relies on its features: row-level security, `ROWVERSION`, filtered unique indexes and read-committed snapshot.
- **Upgrade from Express to Standard Edition before go-live.** The RDS instance currently runs Express, which has hard limits:
  - a **10 GB** database cap;
  - about **1.4 GB** of memory for caching data;
  - **no Multi-AZ** (no automatic failover);
  - **no SQL Agent**.

  GPS points, telemetry and the audit log alone will reach 10 GB. Standard Edition with Multi-AZ gives automatic failover.
- **Check storage encryption now.** RDS storage encryption can only be chosen when an instance is created. If the current instance isn't encrypted, the fix is: snapshot → copy the snapshot with a KMS key → restore. That's easiest before real data arrives.

### 3.2 Driver and connection pool ✅

`db/engine.py` creates one engine per process:

```python
create_engine(
    URL.create("mssql+pyodbc", ..., query={"driver": "ODBC Driver 18 for SQL Server",
                                           "Encrypt": "yes", "TrustServerCertificate": "no"}),
    pool_size=10, max_overflow=20,      # per process
    pool_pre_ping=True, pool_recycle=1800,
    pool_reset_on_return=None,          # replaced by sp_reset_connection, below
)
```

- **Connection budget:** tasks × workers × (pool_size + max_overflow) = 2 × 2 × 30 = **120** connections at most, well within SQL Server's limit. If more tasks are added, recompute.
- **Pool reset:** when a connection goes back to the pool, `sys.sp_reset_connection` runs. This clears `SESSION_CONTEXT`, so one user's identity can never carry over into another user's request.
- **Database login:** the API connects as a **least-privilege SQL login**, never `admin`:
  - grant only `SELECT/INSERT/UPDATE/DELETE` on the application schemas, plus `EXECUTE` on the procedures it needs;
  - no DDL rights;
  - migrations run as a separate login.

### 3.3 Row-level security context ✅

Every request uses `DbSession`. It sets `app_user_id` read-only on a dedicated connection, so the policy in `database/10_row_level_security.sql` filters every query. Today the policy is **OFF**. Turn it on after the integration tests in section 9.3 pass:

```sql
ALTER SECURITY POLICY [rls].[brand_branch_policy] WITH (STATE = ON);
```

Background jobs run as a dedicated `SYSTEM` app user with the `ADMIN` role, so they see every branch.

### 3.4 Transactions: one business action = one commit

The service layer owns the transaction. Repositories never commit. If anything raises an exception, the session closes without committing and SQL Server rolls back.

**Document numbers** ✅ come from `core.number_series` through `common/numbering.py`.
- **Which series:** the helper picks the most specific active series. A NULL branch, brand or fiscal year means "any".
- **Locking:** it locks the row until commit, so two users never get the same invoice number, and a rollback gives the number back.
- **GST length:** invoice numbers can be checked against the 16-character GST limit (`max_length=GST_DOCUMENT_NO_MAX_LENGTH`).

```python
call_no = next_document_no(db, company_id=company_id, document_type="SERVICE_CALL",
                           branch_id=scope.branch_id, fiscal_year_id=fiscal_year_id)
```

> **SQL Server pitfall:** SQLAlchemy's SQL Server dialect **silently ignores** `.with_for_update()`. Write the hint explicitly: `.with_hint(Model, "WITH (UPDLOCK, ROWLOCK)", "mssql")`. A test checks the generated SQL (`tests/test_numbering.py`). Use the same pattern for stock balances and anything else that must be locked.

**A complete write path** (router → service → commit):

```python
# modules/service/schemas.py
class ServiceCallCreate(InputModel):          # InputModel = ApiModel with extra="forbid"
    client_uuid: UUID                          # idempotency key from web / mobile
    customer_id: int
    customer_site_id: int | None = None
    machine_unit_id: int | None = None
    call_source_lookup_id: int
    call_type_lookup_id: int
    complaint_description: str = Field(min_length=5, max_length=2000)
    caller_name: str | None = Field(None, max_length=100)
    caller_phone: str = Field(pattern=r"^(\+91|0)?[6-9]\d{9}$")
    priority: CallPriority = "Normal"
    is_machine_down: bool = False

# modules/service/service.py
class ServiceCallService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ServiceCallRepository(db)

    def create(self, user: CurrentUser, scope: RequestScope, data: ServiceCallCreate) -> ServiceCall:
        if existing := self.repo.by_client_uuid(data.client_uuid):
            return existing                                    # retried request: same result
        if scope.branch_id is None:
            raise ApiError("Select a branch before logging a call.")
        customer = self.repo.customer(data.customer_id)        # RLS also applies here
        if customer is None:
            raise NotFound("Customer not found.")
        call = ServiceCall(
            **data.model_dump(),
            company_id=customer.company_id,
            branch_id=scope.branch_id,
            principal_id=self.repo.principal_for(data.machine_unit_id, scope),
            call_no=next_document_no(self.db, company_id=customer.company_id, document_type="SERVICE_CALL",
                                     branch_id=scope.branch_id, fiscal_year_id=current_fiscal_year(self.db)),
            current_status="Logged",
            received_at=utcnow(),
            received_by_user_id=user.id,
            created_by_user_id=user.id,
        )
        self.db.add(call)
        self.db.add(CallStatusLog(service_call=call, to_status="Logged", changed_by_user_id=user.id))
        self.db.commit()                                       # number, call, log and audit commit together
        return call

# modules/service/router.py
@router.post("/service-calls", status_code=201,
             dependencies=[Depends(require_permission("svc.call.create"))])
def create_service_call(data: ServiceCallCreate, user: CurrentUserDep, scope: ScopeDep,
                        db: DbSession, response: Response) -> ServiceCallDetail:
    call = ServiceCallService(db).create(user, scope, data)
    response.headers["Location"] = f"{settings.api_prefix}/svc/service-calls/{call.id}"
    return ServiceCallDetail.model_validate(call)
```

**Posting engines.** Stock movements (`inv.stock_move`, `stock_balance`, `cost_layer`) and GL entries (`acc.journal`, `gl_entry`) are written **only** by two shared services:
- `inventory.post_stock_movement(...)`
- `accounts.post_journal(...)`

Every module calls these; none writes to those tables directly. Each posting service:
- locks the affected balances (`WITH (UPDLOCK, ROWLOCK)` hint, as above);
- checks the rules: no negative stock (Q12), a balanced journal, the period is open;
- writes its rows.

### 3.5 Optimistic concurrency ✅

- Every record sent to the client carries `rowVersion`, encoded as base64.
- Updates send it back in `If-Match` (Angular's `withRowVersion()`).
- The update endpoint passes the value to `check_row_version(...)`.
- Models set `version_id_col = row_version`, so SQLAlchemy adds `WHERE row_version = ?` to the `UPDATE`.
- A stale write returns **409 Conflict** with the "Record changed" message.

### 3.6 Migrations

- **Baseline:** scripts `00`–`13` define schema **v3**. Keep them as the baseline and never edit them again.
- **New changes:** from now on, every schema change is an **Alembic revision written in SQL**. Never autogenerate one from the ORM.
- **Idempotent:** each revision checks the catalog first, as scripts 12 and 13 already do.

```python
# migrations/versions/20261101_0001_add_svc_call_view_permission.py
def upgrade() -> None:
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM core.permission WHERE code = N'svc.call.view')
            INSERT INTO core.permission (code, module, description)
            VALUES (N'svc.call.view', N'Service', N'View the service call register');
    """)
```

- **Existing databases:** mark them with `alembic stamp v3_baseline`.
- **Deployment:** the CI/CD pipeline runs `alembic upgrade head` as a one-off ECS task with the migration login, **before** the new API version starts.
- **Backward compatibility:** migrations must not break the running version: add a column first, use it in the next release, drop it later.

### 3.7 Query performance

- **Select only the columns a screen needs** (the call register already does), and use projections for lists. Load full ORM objects only to edit them.
- **Avoid N+1 queries:** use `selectinload()` for one-to-many relationships on detail pages, and never load lazily in loops.
- **Indexes:** `database/08_performance_indexes.sql` covers the common screens. Add indexes from real query plans, using **Query Store**, which is on by default in SQL Server 2022.
- **Paging:** page-number paging is limited to `pageSize ≤ 200`. Exports and the mobile sync use **keyset paging** (`WHERE id > :last_id ORDER BY id`) instead.
- **Reports:** use the reporting views (`acc.v_receivables_ageing`, `inv.v_stock_ageing`, ...) and hand-written `text()` SQL with bound parameters. Heavy reports run in the worker and are delivered as files.
- **Concurrency:** `READ_COMMITTED_SNAPSHOT` is on, so reports don't block writers.
- **Large tables:** partition or archive `svc.trip_gps_point`, `svc.duty_gps_point`, `core.machine_telemetry` and `core.audit_log` monthly, moving old months to S3 and Athena.

---

## 4. REST API design standards

**URLs:** `/api/v{n}/{module}/{resource-plural}/{id}/{sub-resource}`. The module prefix matches the schema: `core`, `svc`, `inv`, `pur`, `sal`, `pre`, `hr`, `acc`, `int`, `rpt`.

| Operation | Method and path | Success |
|---|---|---|
| List / search | `GET /svc/service-calls?page=1&pageSize=20&sort=-receivedAt&status=Logged` | 200 + `Page` |
| Read | `GET /svc/service-calls/{id}` | 200 (+ `ETag`) |
| Create | `POST /svc/service-calls` | 201 + `Location` |
| Edit fields | `PATCH /svc/service-calls/{id}` + `If-Match` | 200 |
| Business action | `POST /svc/service-calls/{id}/assign`, `/close`, `/reopen` | 200 |
| Cancel / void | `POST .../cancel` (soft: `is_active` / status) | 200 |
| Delete | `DELETE` only for drafts and masters never referenced | 204 |

**Status changes are actions, not field edits.** `PATCH {"currentStatus": "Closed"}` is rejected. Each action endpoint checks its own permission (`svc.call.close`) and the allowed transitions, and writes `call_status_log`.

**Errors:**

| Code | Meaning |
|---|---|
| 400 | Business rule failed |
| 401 | Not signed in |
| 403 | No permission or outside scope |
| 404 | Not found, or not visible to this user |
| 409 | Stale `rowVersion` or duplicate |
| 422 | Validation (✅ field errors keyed by camelCase name) |
| 428 | `If-Match` missing |
| 429 | Rate limited |
| 500 | Error with a `traceId` and no internals |

**Other conventions:**
- **Versioning:** `/api/v1`. Additive changes (new fields, new endpoints) stay in v1. Breaking changes go to `/api/v2` for that resource only, and v1 stays until the Angular app and the field app have both moved over. The field app is installed on phones and updates slowly, so plan for at least one release of overlap.
- **Validation:**
  - Request models use `extra="forbid"`, so unknown fields are rejected. This stops mass assignment: a client can't set `branchId` or `approvedByUserId`.
  - Money is `Decimal`, never `float`.
  - Dates are ISO 8601, stored in UTC and shown in IST by the client.
- **Idempotency:** create endpoints that the field app may retry take a `clientUuid`; `service_call.client_uuid` already exists for this.
- **Documentation:** OpenAPI at `/api/v1/openapi.json`; Swagger UI at `/api/v1/docs` outside production (✅). Operation IDs are function names (✅), and the Angular client is generated from the spec (`nx run core-api:generate`, ✅).
- **Contract check in CI:** export the OpenAPI document and fail the build if it changed without the generated client being updated.

---

## 5. Authentication and authorization

### 5.1 Why Cognito instead of hand-made JWT login

The request asks for secure login, access and refresh tokens, password hashing and session management. **Cognito provides all of these**, and `core.app_user` was designed for it (`cognito_sub`, no password column). Building our own would mean writing and maintaining:
- password hashing;
- reset e-mails;
- lockout;
- MFA;
- refresh-token storage and rotation;
- revocation;
- a token-signing key rotation.

Each of these is a common source of security bugs. Instead:

| Need | Cognito setting |
|---|---|
| Web sign-in | Hosted UI, authorization code flow + **PKCE**, public app client (no secret in the browser) ✅ frontend |
| Field app | Separate app client, same flow through the system browser |
| Password policy | Minimum 12 characters, with breached-password checks from **threat protection** (Plus feature plan) |
| MFA | **Required** for the ADMIN, ACCOUNTS and MANAGEMENT roles (Cognito groups); optional for others |
| Brute force | Cognito lockout, plus threat protection's adaptive authentication |
| Access token | **15–30 minutes** |
| Refresh token | **10–12 hours** (one working day), with **refresh-token rotation** on |
| Sign out | Revoke the refresh token; `GlobalSignOut` for "sign out everywhere" |
| Integrations (Tally connector, DMS jobs) | Separate app client with the **client-credentials** grant and its own scopes |
| Customer portal | **Separate user pool**, so customers can never get staff tokens |

**API side (✅ `auth/tokens.py`):**
- verify the RS256 signature against the pool's JWKS;
- check `iss`, `exp`, `token_use == "access"` and `client_id`;
- reject `alg: none` and ID tokens.

### 5.2 Linking Cognito users to ERP users

On first sign-in the API finds `core.app_user` by `cognito_sub` (✅). User administration works like this:
1. Admin creates the employee and app user in the ERP.
2. The API creates the Cognito user (`AdminCreateUser`) and stores the `sub`.
3. Cognito e-mails a temporary password.

**Locking a user:** set `is_locked = 1` **and** call `AdminUserGlobalSignOut`. The API's user cache expires within 60 s, so access ends within a minute even for tokens already issued.

### 5.3 Authorization: three layers, all required

| Layer | Question | Where |
|---|---|---|
| **Function** | May this user do this kind of action? | `require_permission("svc.call.assign")` on the route ✅ |
| **Scope** | In this branch and brand? | `get_scope`: headers checked against `user_role.branch_id` and `user_principal_access` ✅; SQL Server RLS as the backstop |
| **Object** | On *this* record? | In the service layer, e.g. an engineer only sees calls assigned to them; approvals respect `approval_rule` amount bands |

**Object-level check example** (OWASP API1, broken object-level authorization):

```python
def get_for_user(self, call_id: int, user: CurrentUser) -> ServiceCall:
    call = self.repo.get(call_id)                     # RLS already hides other branches / brands
    if call is None:
        raise NotFound("Service call not found.")     # 404, not 403: don't confirm it exists
    if not user.can("svc.call.view", "svc.call.assign") and not self.repo.is_assigned(call.id, user.employee_id):
        raise NotFound("Service call not found.")
    return call
```

**Approvals** (discount, credit override, PO, price override):
- read `core.approval_rule` for the bands;
- write `core.approval_request`;
- block the action until it's approved.

Never trust an `approved` flag sent by the client.

### 5.4 Session management in the browser

- Tokens are kept in `sessionStorage` by the OIDC library. They are short-lived, and sessionStorage is cleared when the tab closes.
- XSS is the real risk to tokens stored this way, so section 6 requires a strict Content Security Policy.
- The Angular app signs out after **30 minutes idle**. That's an ERP norm; adjust per role.
- A backend-for-frontend with HttpOnly cookies is stronger against XSS but adds CSRF handling and another service. Revisit it if a security audit asks.

---

## 6. API security (OWASP API Security Top 10, 2023)

| Risk | Control in Trishul | Status |
|---|---|---|
| **API1 Broken object-level authorization** | RLS + scope check + object check in services (5.3); return 404 for records the user can't see | ✅ scope / RLS context, ⬜ per-module object checks |
| **API2 Broken authentication** | Cognito, MFA for privileged roles, strict token checks, no API keys in the browser | ✅ token checks |
| **API3 Broken object-property-level authorization** | `extra="forbid"` request models; separate Create / Update / Response schemas; never return ORM objects directly; sensitive fields (PAN, bank, salary) only in dedicated permissioned endpoints | ⬜ `InputModel` |
| **API4 Unrestricted resource consumption** | `pageSize ≤ 200` ✅; request body limit (ALB/WAF, 10 MB; uploads go straight to S3); rate limits; statement timeouts; query string limits | partly |
| **API5 Broken function-level authorization** | Every route has `require_permission`; a CI test fails if a router endpoint has none (except `/me`, health) | ✅ dependency, ⬜ CI test |
| **API6 Unrestricted access to sensitive business flows** | Rate limits on OTP / portal / quotation endpoints; approvals for discounts and credit; duplicate checks | ⬜ |
| **API7 Server-side request forgery** | Integration URLs come from configuration only, never from request data; no fetching of user-supplied URLs | design rule |
| **API8 Security misconfiguration** | Docs off in production ✅; dev sign-in refused in UAT/production ✅; CORS allowlist ✅; security headers; no stack traces in responses ✅; least-privilege DB login | partly |
| **API9 Improper inventory management** | One versioned API; OpenAPI published per release; old versions removed on schedule; no "test" endpoints in production builds | ✅ |
| **API10 Unsafe consumption of APIs** | Validate every Tally / DMS / GSP response with Pydantic before use; timeouts and retries; don't trust their data for authorization | ⬜ |

**SQL injection.** All SQL goes through SQLAlchemy with bound parameters. Rules:
- Never build SQL with f-strings or `%` formatting.
- `text()` queries must use `:named` parameters.
- Column names for sorting come from a **whitelist** (✅ `_SORT_COLUMNS`); unknown keys fall back to the default sort.
- `LIKE` searches use `autoescape=True` (✅).
- Ruff's `S608` rule flags string-built SQL in CI.

**Brute force and abuse:**
1. **Cognito** handles sign-in brute force.
2. **AWS WAF** in front of the ALB:
   - AWS managed rule groups (core rule set, known bad inputs, IP reputation);
   - a rate-based rule per IP, e.g. 2,000 requests per 5 minutes;
   - a stricter rule on the customer-portal paths.
3. **API rate limits** per user for expensive or sensitive endpoints, backed by Redis so all tasks share the counters:

```python
# common/security.py — with the `limits` library (also used by slowapi)
limiter = MovingWindowRateLimiter(RedisStorage(settings.redis_url))
EXPORT_LIMIT = parse("10/minute")

def rate_limited(limit: RateLimitItem, key: str) -> Callable[[CurrentUser], None]:
    def check(user: CurrentUserDep) -> None:
        if not limiter.hit(limit, key, str(user.id)):
            raise TooManyRequests("Too many requests. Wait a minute and try again.")
    return check

@router.get("/service-calls/export", dependencies=[Depends(rate_limited(EXPORT_LIMIT, "svc-export"))])
```

**CSRF.** The API authenticates with the `Authorization: Bearer` header, never cookies, so cross-site requests can't carry credentials and CSRF doesn't apply. If cookies are ever introduced (for a backend-for-frontend), add `SameSite=Strict` and a double-submit CSRF token at the same time.

**XSS:**
- The API returns JSON only, with `X-Content-Type-Options: nosniff`.
- Angular escapes interpolated text by default. Never use `bypassSecurityTrustHtml` on user data.
- Rich text (remarks, e-mail templates) is sanitised on save with `nh3`.
- CloudFront serves the Angular app with a strict **Content Security Policy**: `default-src 'self'`; scripts only from self; `connect-src` the API and Cognito domains; `frame-ancestors 'none'`.

**CORS** (✅): an explicit origin list per environment; never `*`; only the needed headers (`Authorization`, `Content-Type`, `If-Match`, `X-Branch-Id`, `X-Principal-Id`).

**Security headers** on every API response (to add):

```python
@app.middleware("http")
async def security_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    if not request.url.path.endswith(("/docs", "/openapi.json")):
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        response.headers.setdefault("Cache-Control", "no-store")   # ERP data must not sit in shared caches
    return response
```

**File uploads** (service photos, signatures, PODs, imports):
1. The API issues a **pre-signed S3 PUT URL** with a fixed key, content type and size limit (`core.attachment.s3_key`).
2. The browser uploads straight to S3; the bucket blocks all public access.
3. An S3 event triggers a malware scan (Amazon GuardDuty Malware Protection for S3) before the attachment is marked usable.
4. Downloads use short-lived pre-signed GET URLs, issued only after the object-level check.

---

## 7. Data protection

**In transit:**
- **Client to AWS:** TLS 1.2+ at CloudFront and the ALB, with ACM certificates; HTTP redirects to HTTPS.
- **API to RDS:** `Encrypt=yes` in the driver (✅). Set `rds.force_ssl = 1` in the DB parameter group so unencrypted connections are refused.
- **API to Redis:** ElastiCache with in-transit encryption and AUTH.

**At rest:**
- **RDS:** KMS encryption, including backups and snapshots (check section 3.1).
- **S3:** SSE-KMS with a dedicated key, versioning on, and a lifecycle policy for import files.
- **Redis:** at-rest encryption enabled; never store full documents there, only lookups and counters.

**Sensitive columns** (`hr.employee_profile.pan`, `bank_account_no`, `pur.supplier.bank_account_no`, salary amounts): these need protection beyond disk encryption, because a database user or a leaked backup could read them.

The gap analysis offered two options:
- **Always Encrypted:** its keys must sit in a key store the ODBC driver can reach. That is awkward from Linux containers on AWS.
- **Application-level encryption with AWS KMS (recommended):**
  - widen the columns to `VARBINARY(1024)`;
  - encrypt in the API with the AWS Encryption SDK;
  - add a keyed hash column where equality search is needed (e.g. "find employee by PAN").

```python
# common/crypto.py
_client = aws_encryption_sdk.EncryptionSDKClient(
    commitment_policy=CommitmentPolicy.REQUIRE_ENCRYPT_REQUIRE_DECRYPT)
_keys = aws_encryption_sdk.StrictAwsKmsMasterKeyProvider(key_ids=[settings.field_kms_key_arn])

def encrypt_field(value: str, *, table: str, column: str) -> bytes:
    ciphertext, _ = _client.encrypt(source=value.encode(), key_provider=_keys,
                                    encryption_context={"table": table, "column": column})
    return ciphertext

def decrypt_field(blob: bytes, *, table: str, column: str) -> str:
    plaintext, header = _client.decrypt(source=blob, key_provider=_keys)
    if header.encryption_context.get("column") != column:   # stop ciphertext being swapped between columns
        raise ValueError("Encryption context mismatch")
    return plaintext.decode()

def search_hash(value: str) -> bytes:                         # stored alongside, indexed, for lookups
    return hmac.new(settings.search_hash_key.get_secret_value().encode(),
                    value.strip().upper().encode(), hashlib.sha256).digest()
```

How these fields are handled:
- They are decrypted only in endpoints that require a specific permission (e.g. `hr.employee.sensitive.view`).
- Each such read is written to `core.audit_log`.
- Responses show them masked by default (`XXXXXX1234F`).

**Passwords:** none are stored in the ERP (Cognito). If a local credential is ever unavoidable, hash it with **Argon2id** (`argon2-cffi`), never SHA-256 or bcrypt with a low cost.

**Secrets:**
- **Storage:** all secrets live in **AWS Secrets Manager**: DB passwords (rotation on), the Redis AUTH token, integration credentials (Tally, GSP, DMS, WhatsApp) and the search-hash key.
- **Delivery:** ECS injects them as environment variables using the task's IAM role. Nothing secret is placed in `config.json`, committed `.env` files, Docker images or logs.
- **Git:** `.env` is git-ignored (✅). Add **gitleaks** to CI to block committed secrets.

**Audit logging** ✅. The schema has no triggers, so the API writes `core.audit_log` itself (`db/audit.py`).
- **Which models:** any model marked `Audited` is recorded on insert, update and delete, from a session `after_flush` listener.
- **Transaction:** audit rows are written in the **same transaction**, so a rollback removes them too.
- **What's recorded:** updates store only the changed columns, old and new. Columns in `__audit_masked__` are stored as `***`.
- **Who and where:** `get_db()` adds the user, the platform (`X-Client-Platform`: Web, Android, iOS, API) and the client IP.

```python
class EmployeeProfile(Audited, AuditMixin, Base):
    __audit_masked__ = frozenset({"pan", "bank_account_no"})
```

Other events to log:
- **Security events:** sign-in failures (from Cognito), 403s, permission changes, data exports, and reads of sensitive fields. These go to CloudWatch Logs as structured JSON, kept 1 year.
- **Ledger:** GL postings are never edited. Corrections are reversal entries.

**Logs never contain:** tokens, passwords, full PAN or bank numbers, or request bodies of HR and payroll endpoints. Apply a redaction filter in the logging configuration.

**Backups and retention:**
- **RDS:** automated backups with point-in-time restore, 14–35 days retention.
- **Monthly:** a snapshot copied to a second region for disaster recovery; test a restore every quarter.
- **Personal data:** follow India's **Digital Personal Data Protection Act 2023** for employee and customer data:
  - use data only for its stated purpose;
  - keep a retention schedule;
  - have a process to answer data-principal requests.

---

## 8. Performance and scalability

**Threads and connections.** Endpoints are sync `def`. FastAPI runs them in a thread pool of 40 per worker, and each worker's DB pool allows 30 connections. Keep the two figures aligned, so threads don't queue for connections without limit. Use `async def` only for endpoints that do no database work (e.g. proxying to S3 or Cognito).

**Caching:**

| Data | Where | Invalidation |
|---|---|---|
| User, roles, permissions | In-process, 60 s ✅ | Time-based; lock takes effect within 60 s |
| Lookups, states, HSN, UOM, branches | Redis, 10 min + `ETag` / `Cache-Control: private, max-age=300` on the endpoint | Delete the key when an admin edits the list |
| Item / price lists | Redis per branch and brand, 5 min | Delete on edit |
| Transactional data (stock, balances, calls) | **Not cached** | — |

**Background jobs (Celery + Redis):**

| Job | Trigger |
|---|---|
| SLA warnings and breaches (`svc.sla_event`) | Every 5 min |
| Planned services from contracts and HMR | Nightly |
| Machine alerts from telemetry | On ingest / every 15 min |
| KPI actuals (`rpt.kpi_actual`), pipeline snapshot | Nightly |
| Contract expiry, `is_asc_customer` refresh | Nightly |
| Excel imports (OEM case lists, claims, opening balances) | On upload |
| e-invoice IRN / e-way bill, Tally sync | On posting, with retries |
| PDF invoices / service reports, e-mail, WhatsApp, push | On demand |
| Big exports | On demand → S3 link |

```python
# worker/app.py
celery = Celery("trishul", broker=settings.redis_url)
celery.conf.update(
    task_acks_late=True, worker_prefetch_multiplier=1,          # a crash re-runs the task
    task_time_limit=900, timezone="Asia/Kolkata",
    beat_schedule={
        "sla-alerts": {"task": "trishul.svc.raise_sla_alerts", "schedule": 300.0},
        "planned-services": {"task": "trishul.svc.generate_planned_services",
                             "schedule": crontab(hour=1, minute=30)},
    },
)

@celery.task(name="trishul.svc.raise_sla_alerts", autoretry_for=(OperationalError,),
             retry_backoff=True, max_retries=5)
def raise_sla_alerts() -> int:
    with user_session(engine, SYSTEM_USER_ID) as db:            # same RLS context as the API
        return SlaService(db).raise_due_alerts(now=utcnow())     # idempotent: skips existing events
```

Every task is **idempotent**: it checks whether the work is already done, because tasks may run more than once. Run **exactly one** beat scheduler.

**Monitoring:**
- **Logs:** structured JSON (`structlog`) with a request ID, user ID, branch, route and duration, sent to CloudWatch Logs.
- **Traces:** OpenTelemetry (FastAPI, SQLAlchemy, Celery and HTTP-client instrumentation), sent to AWS X-Ray / CloudWatch Application Signals.
- **Alarms:**
  - API p95 latency > 800 ms;
  - 5xx rate > 1 %;
  - DB CPU > 70 %;
  - DB free storage < 20 %;
  - Celery queue length / oldest task age;
  - failed integration syncs;
  - WAF blocked spikes.
- **Health checks:** the ALB uses `/health` (✅); `/health/ready` (✅) checks the database for deploy verification.

**Deployment:**
1. CI/CD builds the image and pushes it to ECR.
2. The migration task runs.
3. ECS does a **rolling deploy**: minimum 100 % healthy, maximum 200 %, with circuit-breaker rollback.
4. Auto-scaling adds tasks at 60 % CPU, from 2 up to 6.
5. The worker service scales separately.

Releases go to **UAT** first, then production after sign-off.

---

## 9. Testing and quality assurance

| Level | Tool | What | When |
|---|---|---|---|
| Static | ruff (incl. `S` security rules) ✅, mypy strict ✅, import-linter, gitleaks, `pip-audit` | Style, types, module boundaries, secrets, vulnerable packages | Every push |
| Unit | pytest ✅ | Services and helpers with fake repositories: pricing, tax, status transitions, numbering format | Every push |
| API | pytest + FastAPI `TestClient` with dependency overrides ✅ | Status codes, validation, permissions, JSON contract | Every push |
| Integration | pytest + **Testcontainers** SQL Server 2022 | Real SQL: queries, RLS, row_version conflicts, posting rules, migrations | Every push / PR |
| Authorization matrix | pytest, parametrised by role × endpoint | Every role gets exactly the expected 200 / 403 / 404 | Every PR |
| API fuzzing | **Schemathesis** against the OpenAPI document | Crashes, 500s, schema violations | Nightly |
| Security scan | **OWASP ZAP** API scan on UAT | Headers, injection, misconfiguration | Weekly + before release |
| Load | **Locust** | Peak scenarios | Before each phase go-live |
| Penetration test | External party | Whole system | Before production go-live |

**Integration tests against a real SQL Server:**

```python
# tests/integration/conftest.py
@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    with SqlServerContainer("mcr.microsoft.com/mssql/server:2022-latest",
                            dialect="mssql+pyodbc") as server:
        engine = create_engine(server.get_connection_url() + "&driver=ODBC+Driver+18+for+SQL+Server"
                               "&TrustServerCertificate=yes")
        for script in sorted(Path("../database").glob("[0-1][0-9]_*.sql")):
            run_sql_script(engine, script)            # splits on GO lines, like sqlcmd
        run_sql_script(engine, Path("tests/integration/seed_test_users.sql"))
        yield engine

def test_rls_hides_other_branches(engine: Engine) -> None:
    with engine.connect() as c:
        c.execute(text("ALTER SECURITY POLICY rls.brand_branch_policy WITH (STATE = ON)"))
        c.commit()
    with user_session(engine, PUNE_ENGINEER_ID) as db:
        assert {c.branch_id for c in db.scalars(select(ServiceCall))} == {PUNE_BRANCH_ID}
```

**Load-test targets** (Locust, against UAT sized like production):
- **Users:** 300 concurrent: 60 % browsing lists, 25 % opening details, 10 % creating or updating, 5 % reports.
- **Response times:** p95 under 500 ms for lists and details, under 1 s for creates and posts.
- **Errors:** no errors.
- **Month-end:** a separate scenario of 50 users posting invoices at the same time, to prove the number-series and stock locking hold up.

**CI/CD pipeline** (GitHub Actions shown; the same steps work in GitLab or CodePipeline):

```yaml
# .github/workflows/backend.yml
on: { push: { paths: ["backend/**", "database/**"] }, pull_request: {} }
jobs:
  check:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: backend } }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run mypy
      - run: uvx pip-audit
      - run: uv run pytest --cov=trishul_api --cov-fail-under=80   # unit + API + integration
  deploy-uat:
    needs: check
    if: github.ref == 'refs/heads/Development'
    permissions: { id-token: write, contents: read }               # OIDC to AWS, no stored keys
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with: { role-to-assume: "${{ vars.AWS_DEPLOY_ROLE_UAT }}", aws-region: ap-south-1 }
      - run: ./backend/scripts/deploy.sh uat    # build → push ECR → run migrations → update ECS service
```

Production deploys run from `main` with a manual approval step in the pipeline.

---

## 10. Implementation roadmap

The backend phases run alongside the frontend phases in the Angular roadmap. A module's API is ready about one week before its screens, so the frontend can use the real API instead of mocks.

| Phase | Weeks | Backend scope | Exit criteria |
|---|---|---|---|
| **B0 Foundation** | ✅ mostly done + 1–2 | Done: app factory, settings, engine with RLS context, Cognito checks, permissions, scope, errors, paging, row_version, `/me`, lookups, call register, `InputModel`, security headers, document numbering, audit log, Alembic baseline + first migration, CI workflows. To do: connect to RDS; least-privilege DB logins; structured logs; Testcontainers suite; CDK stacks for UAT (VPC, ECS, ALB, WAF, Redis, Secrets) and a deploy job | UAT deployed from CI; integration tests green; RLS tests pass |
| **B1 Admin & masters** | 4–5 | Users and roles (with Cognito admin API), branches, territories, customers, sites, contacts, suppliers, items, HSN / GST, machines, fiscal years, number series, approval rules | Every master has CRUD, audit, permission tests |
| **B2 Service** | 6–8 | Calls (create, assign by skill, status actions, reopen), visits, trips and GPS ingest, service reports, part requests, contracts / AMC, planned services, SLA jobs, OEM imports; **field-app sync endpoints** (idempotent, keyset delta sync) | 18-step workflow passes end to end in UAT |
| **B3 Inventory** | 4–5 | **Stock posting engine**, balances, reservations, issues, transfers (HSN, challan), adjustments, counts, stock ageing | Concurrent-posting load test passes; no negative stock |
| **B4 Purchase** | 4 | Request → PO → GRN (transit) → supplier invoice → payment, debit notes, allocations | GRN posts stock through the engine |
| **B5 Sales** | 5–6 | Price lists, quotations (versions, OEM price check), approvals, orders + credit check, delivery, invoice + **GL posting engine**, e-invoice / e-way bill, receipts, credit notes | Invoice posts stock + GL in one transaction |
| **B6 Pre-sales** | 4 | Leads, activities, opportunities, SOP stages, finance applications, targets | — |
| **B7 HR** | 6 | Employee profiles (**field encryption**), attendance, leave, shifts, vehicles, expenses, payroll | Sensitive-field access audited |
| **B8 Accounts** | 4–5 | Journals, period lock, bank reconciliation, cheques, TDS, cash reconciliation, ageing | Trial balance matches test data |
| **B9 Integrations** | 3 | Tally (direction per Q3), Atlas Copco DMS, Grey8, WhatsApp / e-mail inbound | Retries and failure alerts tested |
| **B10 Reports & portal** | 4–5 | KPI jobs, dashboards, exports; customer-portal API on a separate user pool | — |
| **B11 Hardening & go-live** | 3–4 | Load tests, ZAP + external penetration test, DR restore drill, RLS ON in production, Standard Edition + Multi-AZ, data migration, runbooks | Go-live checklist signed off |

**Business decisions the backend needs** (from the gap analysis, section 9). Without them some endpoints can't be finished:
- **Q3:** Tally direction and stock master.
- **Q5:** SLA hours.
- **Q7:** who closes a call.
- **Q11:** FIFO or weighted-average valuation.
- **Q12:** whether negative stock is allowed.
- **Q15:** customer-portal scope.

---

## Security checklist

✅ = in the codebase today.

**Identity and access**
- [x] Cognito access tokens checked: signature (JWKS), issuer, expiry, `token_use`, `client_id`; `alg: none` rejected
- [x] Dev sign-in mode refused in UAT and production
- [x] Permission dependency on routes; branch / brand scope validated against the user's roles
- [x] Row-level-security context set per request; pooled connections reset
- [ ] MFA required for ADMIN, ACCOUNTS, MANAGEMENT; Cognito threat protection on
- [ ] Access token ≤ 30 min, refresh token ≤ 12 h with rotation; idle sign-out in the UI
- [ ] CI test: every endpoint declares a permission
- [ ] Object-level checks in every module's service layer; 404 for records the user can't see
- [ ] RLS policy switched ON (after integration tests)
- [ ] Separate Cognito user pool for the customer portal

**Input and output**
- [x] Pydantic validation; sort-column whitelist; escaped LIKE searches; bound SQL parameters only
- [x] Problem-details errors with no stack traces; trace ID for 500s
- [x] Page size capped at 200
- [x] `InputModel` base with `extra="forbid"` (use it for every request body); money as `Decimal`
- [x] Security headers middleware on the API
- [ ] Strict CSP on CloudFront for the Angular app
- [ ] Rich text sanitised (`nh3`)
- [ ] Uploads only through pre-signed S3 URLs with size / type limits and malware scanning

**Infrastructure**
- [x] CORS allowlist; Swagger UI off in production; non-root container
- [ ] AWS WAF (managed rules + rate rules) on the ALB
- [ ] TLS 1.2+ everywhere; `rds.force_ssl = 1`
- [ ] RDS, S3, Redis and backups encrypted with KMS
- [ ] Least-privilege DB logins (API, migrations, reporting)
- [ ] Secrets in Secrets Manager with rotation; gitleaks in CI
- [ ] Private subnets for ECS, RDS and Redis; security groups allow only the needed ports

**Data**
- [ ] PAN / bank / salary encrypted at field level; masked in responses; reads audited
- [x] `core.audit_log` written for audited tables in the same transaction
- [ ] Logs redact tokens and personal data
- [ ] Backups tested by restore every quarter; cross-region copy
- [ ] DPDP Act 2023 retention and request process documented

**Process**
- [x] ruff security rules, mypy strict, tests in the repo
- [x] CI on every push / PR (`.github/workflows`): lint, types, tests, `pip-audit`, `npm audit`, migrations render, OpenAPI contract check, Docker build, Playwright
- [ ] CI: Schemathesis, ZAP, coverage gate, gitleaks; OIDC deploy role (no AWS keys in CI)
- [ ] External penetration test before go-live; findings fixed or accepted in writing

---

## Appendix: libraries

| Purpose | Library | Status |
|---|---|---|
| Web framework / server | `fastapi`, `uvicorn[standard]` | ✅ |
| Settings | `pydantic-settings` | ✅ |
| Database | `sqlalchemy` 2, `pyodbc`, Microsoft ODBC Driver 18 | ✅ |
| Migrations | `alembic` (SQL revisions) | add |
| Tokens | `pyjwt[crypto]` | ✅ |
| AWS | `boto3` (Cognito admin, S3, KMS, Secrets Manager) | add |
| Field encryption | `aws-encryption-sdk` | add |
| Jobs | `celery[redis]`, `redis` | add |
| Rate limiting | `limits` (or `slowapi`) with Redis storage | add |
| HTTP clients for integrations | `httpx` with timeouts, `tenacity` for retries | add |
| Excel / PDF | `openpyxl`, `weasyprint` | add |
| HTML sanitising | `nh3` | add |
| Logging / tracing | `structlog`, `opentelemetry-distro` + FastAPI / SQLAlchemy / Celery instrumentation | add |
| Tests | `pytest` ✅, `httpx2` ✅, `testcontainers[mssql]`, `schemathesis`, `locust`, `pytest-cov` | partly |
| Quality | `ruff` ✅, `mypy` ✅, `import-linter`, `pip-audit`, `gitleaks` | partly |
| Infrastructure | AWS CDK (Python) | add |
