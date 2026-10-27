# Trishul ERP: API standards

**Audience:** everyone who adds or changes an API endpoint (backend) or calls one (frontend).
**Status:** in force from 2026-10-27. Most rules are checked automatically (section 10); a change that breaks one fails the tests or lint.

---

## 1. URLs

```
/api/v1/{module}/{resource}                 collection           /api/v1/svc/service-calls
/api/v1/{module}/{resource}/{id}            one record           /api/v1/svc/service-calls/{callId}
/api/v1/{module}/{resource}/{id}/{child}    records it owns      /api/v1/core/lookups/{typeCode}/values
/api/v1/{module}/{resource}/{id}/{action}   business action      /api/v1/svc/service-calls/{callId}/assign
```

- **Module prefix** = the database schema: `core`, `svc`, `inv`, `pur`, `sal`, `pre`, `hr`, `acc`, `int`, `rpt`. The only top-level path is `/me`.
- **Resources** are plural nouns in **kebab-case**: `service-calls`, `purchase-orders`.
- **Path parameters** are **camelCase**: `{callId}`. In Python: `call_id: Annotated[int, Path(alias="callId")]`.
- **Versioning:** `/api/v1` is a mounted sub-app (`main.py`). Breaking changes go into a v2 app beside it; additive changes stay in v1.

## 2. Methods, function names and status codes

The endpoint function's name becomes the generated Angular function (`list_service_calls` → `listServiceCalls`), so names follow the action:

| Action | Method and path | Function name | Success |
|---|---|---|---|
| List / search | `GET /svc/service-calls` | `list_…` | 200 + `Page` |
| Read one | `GET /svc/service-calls/{callId}` | `get_…` | 200 |
| Create | `POST /svc/service-calls` | `create_…` | **201** + `Location` header |
| Edit fields | `PATCH /svc/service-calls/{callId}` (+ `If-Match`) | `update_…` | 200 |
| Business action | `POST /svc/service-calls/{callId}/close` | a verb: `close_service_call` | 200 |
| Delete (drafts, unused masters only) | `DELETE /…/{id}` (+ `If-Match`) | `delete_…` | **204** |

- **Status changes are actions, not field edits.** `PATCH {"currentStatus": "Closed"}` is wrong; `POST …/close` checks its own permission and the allowed transitions, and writes the status log.
- **Every endpoint** has `summary="…"` (shown in Swagger) and a unique function name.

## 3. Requests

| What | Rule |
|---|---|
| Query parameters | camelCase. Lists take a model extending `PageQuery` (`page`, `pageSize` ≤ 200, `sort`, `search`): `query: Annotated[XQuery, Query()]` |
| Sorting | `sort=field` or `sort=-field`; allowed fields are a `SortColumns` map, and `order_by_sort()` rejects anything else |
| Request bodies | Pydantic models extending **`InputModel`**: camelCase JSON, unknown fields rejected (no mass assignment), strings trimmed |
| Money | `Decimal`, never `float` |
| Dates | ISO 8601, UTC (`UtcDateTime`); the client shows local time |
| Retries | Create endpoints called from the field app take a `clientUuid` and return the existing record on a retry |
| Context headers | `Authorization`, `X-Branch-Id`, `X-Principal-Id`, `X-Client-Platform` are sent by the Angular interceptors on every call. Endpoints read them through `CurrentUserDep` / `ScopeDep` / `DbSession`, never as their own parameters |

## 4. Responses

- **Response models** extend `ApiModel`: camelCase JSON, built from the database row (`from_attributes`).
- **Paged lists** return `Page[T]`: `{ "items": [...], "total": 87, "page": 1, "pageSize": 20 }`. Use `paginate()`.
- **Short reference lists** (dropdowns, at most a few hundred values) may return a plain array, e.g. lookup values.
- **Records that can be edited** include `rowVersion` (`RowVersion` type, base64).
- **Return the declared type** (`-> Page[ServiceCallListItem]`): it becomes the OpenAPI schema and the generated TypeScript type.

## 5. Errors

Every error is **RFC 7807 problem-JSON**, as `ProblemDetails`:

```json
{ "status": 422, "title": "Please check the form", "detail": "Some values are not valid.",
  "errors": { "pageSize": ["Input should be less than or equal to 200"] } }
```

| Status | When | How |
|---|---|---|
| 400 | Business rule failed | `raise ApiError("…")` |
| 401 | Not signed in / session expired | automatic |
| 403 | No permission, or outside the user's branches / brands | automatic (`require_permission`, `ScopeDep`) or `raise Forbidden(...)` |
| 404 | No such record, **or the user may not see it** | `raise NotFound(...)`; add `responses=NOT_FOUND_RESPONSE` |
| 409 | `rowVersion` is stale | automatic on update; add `responses=CONCURRENCY_RESPONSES` |
| 422 | Invalid input; `errors` per field | automatic |
| 428 | `If-Match` missing on update / delete | `if_match_row_version` dependency |
| 500 | Bug; the body has a `traceId` for the logs | automatic |

401, 403, 422 and 500 are documented on every endpoint automatically. Never return error details such as stack traces or SQL to the client.

## 6. Security, on every endpoint

1. **Permission:** `dependencies=[Depends(require_permission("svc.call.assign"))]` with real `core.permission` codes (new codes come with a migration). The rare endpoint that every signed-in user may call (e.g. `/me`, dropdown values) is marked `openapi_extra=SIGNED_IN_USERS` instead.
2. **Branch / brand scope:** take `scope: ScopeDep` and filter by it.
3. **Object-level check** on `{id}` endpoints: confirm the record is in the user's branches and brands, and answer **404** (not 403) when it isn't, so the response doesn't confirm the record exists. Row-level security in SQL Server is the backstop, not the only check.
4. **SQL:** ORM or `text()` with bound parameters only; never build SQL from strings.

## 7. Code layout per endpoint

```
modules/<module>/schemas.py      XQuery(PageQuery), XListItem(ApiModel), XCreate(InputModel), XDetail(ApiModel)
modules/<module>/repository.py   queries; read endpoints may return response models directly; no commits
modules/<module>/service.py      writes: business rules, numbering, other modules, db.commit()
modules/<module>/router.py       URL, permission, dependencies, status code; no SQL, no rules
main.py                          add a new module's router to V1_ROUTERS
```

Endpoints are sync `def` (the SQL Server driver is synchronous). Value lists come from the generated models' `Literal` types (e.g. `ServiceCallCurrentStatus`), never typed again.

## 8. Calling the API from Angular

There is **one** way to call the API: **`ApiClient` with the generated function**, inside the module's data-access service.

```typescript
@Injectable({ providedIn: 'root' })
export class ServiceCallApi {
  private readonly api = inject(ApiClient);

  list(query: ServiceCallQuery): Observable<PageServiceCallListItem> {
    return this.api.call(listServiceCalls, query);
  }

  close(callId: number, rowVersion: string): Observable<ServiceCallDetail> {
    return this.api.call(closeServiceCall, { callId }, withRowVersion(rowVersion));
  }
}
```

- **Never** inject `HttpClient` or build URLs in feature or data-access code (lint rule `no-restricted-imports`). The generated functions know the paths, parameters and types; `ApiClient` adds the base URL.
- **Types** come from the generated client (`@trishul/core-api`). Write only UI-specific additions, e.g. option lists checked with `allOf<T>()`.
- **Headers** (token, branch, brand) and **error toasts** are added by the interceptors. Use `withRowVersion(...)` for updates, and `withoutErrorToast()` when the screen shows the error itself.
- **Components** call the data-access store or service, never `ApiClient` directly.

## 9. Workflow for a new endpoint

```powershell
# backend
cd backend
#   schemas.py → repository.py (→ service.py for writes) → router.py, then tests in tests/
uv run pytest; uv run ruff check .; uv run mypy
uv run python scripts/export_openapi.py        # frontend/libs/core/api/openapi.json

# frontend
cd ..\frontend
npx nx run core-api:generate                   # new function + types in @trishul/core-api
#   data-access service method → store → page
npx nx run-many -t lint test build
```

## 10. What is checked automatically

| Rule | Checked by |
|---|---|
| URL shape: module prefix, kebab-case, `{camelCase}` parameters | `backend/tests/test_api_conventions.py` |
| Function name matches the action (`list_`, `get_`, `create_`, `update_`, `delete_`); unique; `summary` set | same |
| Success status (200 / 201 / 204) per action | same |
| 401 / 403 / 422 / 500 documented as `ProblemDetails`; 404 on `{id}` paths; 409 / 428 on updates and deletes | same |
| Parameters camelCase, no per-endpoint header parameters; paged lists accept `page` and `pageSize` | same |
| Request bodies reject unknown fields (`InputModel`); no body on GET / DELETE | same |
| **Every endpoint returns 403 to a user without permissions**, unless marked `SIGNED_IN_USERS` | same, by calling each endpoint |
| Frontend calls go through `ApiClient` (no `HttpClient` outside `libs/core`) | ESLint `no-restricted-imports` |
| The Angular client matches the API | `scripts/export_openapi.py --check` in CI |
| Module boundaries (features don't import other modules' internals) | ESLint `@nx/enforce-module-boundaries` |

## 11. Audit of the existing endpoints (2026-10-27)

| Endpoint | Finding | Change |
|---|---|---|
| All | Errors documented with FastAPI's default validation schema; 401 / 403 / 500 undocumented | `ProblemDetails` model; standard error responses on every endpoint |
| `GET /me` | Function `me`; no explicit access rule | Renamed `get_me` (client `getMe`); marked `SIGNED_IN_USERS` |
| `GET /core/lookups/{type_code}` | snake_case path parameter; URL read as "one lookup" but returned a list; function `lookup_values` | Now `GET /core/lookups/{typeCode}/values`, `list_lookup_values` (client `listLookupValues`), 404 documented, marked `SIGNED_IN_USERS` |
| `GET /svc/service-calls` | Conforms | none |
| Frontend | All calls already used `ApiClient`; a hand-written `ProblemDetails` duplicated the generated one | Lint rule added; the duplicate removed |
