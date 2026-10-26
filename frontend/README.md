# Trishul ERP – frontend

Nx monorepo (Angular 22, standalone components, signals, zoneless) for the Trishul ERP web apps.

## Run

```sh
npm install
npm start                 # http://localhost:4200, mock API; sign in with any username, e.g. demo.admin
npx nx build erp-web      # production build -> dist/apps/erp-web
npx nx run-many -t lint test
npx nx e2e erp-web-e2e -- --project=chromium
npx nx graph              # dependency graph
```

## Runtime configuration

`apps/erp-web/public/config.json` is read before the app starts, so one build serves every
environment. Replace it per environment at deploy time.

| Key | Meaning |
|---|---|
| `apiBaseUrl` | REST API base, e.g. `https://api.example.com/api/v1` |
| `useMockApi` | `true`: answer API calls from `apps/erp-web/src/app/mocks`; `false`: the real API (the dev server proxies `/api` to `127.0.0.1:8000`) |
| `auth.mode` | `cognito`: username + password against the Cognito user pool. `dev`: username only, sent to the API as `dev:<username>`; needs the API in `TRISHUL_AUTH_MODE=dev` (refused in UAT / production) |
| `auth.userPoolId` | Cognito user pool id, e.g. `ap-south-1_AbCdEf123` (cognito mode) |
| `auth.userPoolClientId` | Cognito app client id: public client, no secret, `ALLOW_USER_SRP_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH` (cognito mode) |

No secrets belong in this file; it is downloaded by every browser.

**Common setups:** mock API + `dev` (UI work, no backend) · real API + `dev` (local backend and
database, sign in as any `core.app_user` username) · real API + `cognito` (UAT, production).

## Sign-in

`/login` (`libs/core/auth/src/lib/login`) handles sign-in, first-login password change, MFA code
and forgot password. Cognito checks the password with SRP through AWS Amplify; tokens are kept in
`sessionStorage`, so closing the tab signs the user out. `authGuard` sends signed-out users to
`/login?returnUrl=…`, and an API 401 (expired or revoked session) does the same.

## Layout

```
apps/
  erp-web/                  back-office app: routes, menu, theme, mock API
  erp-web-e2e/              Playwright tests
libs/
  core/
    config/                 AppConfig + loader
    auth/                   Cognito session, AuthStore (user, permissions, branch, brand), guards, *trishulHasPermission
    http/                   interceptors: token, X-Branch-Id / X-Principal-Id, If-Match row_version, error toasts; mock API
    api/                    shared API contracts (Page, PageQuery, ProblemDetails); generated client goes in src/generated
    layout/                 shell (top bar, side menu), forbidden / not-found pages
  shared/
    ui/                     page header, status badge, ...
    util/                   INR formatting, GSTIN / PAN / pincode / mobile validators
    data-access/            lookup cache (core.lookup_value)
  domains/<module>/         one folder per DB schema (service = svc, sales = sal, ...)
    data-access/            API service, models, SignalStores
    feature-<area>/         routed pages, lazy-loaded from the app
```

Module boundaries are enforced by ESLint (`eslint.config.mjs`) from the project tags:
`type:feature` → `type:data-access` / `type:ui` → `type:core` → `type:api` / `type:util`, and a domain
(`scope:service`, ...) may use only `scope:core` and `scope:shared`, never another domain.

## Adding a module

```sh
npx nx g @nx/angular:library libs/domains/sales/data-access --name=sales-data-access \
  --tags=scope:sales,type:data-access --prefix=trishul --unitTestRunner=vitest-analog
npx nx g @nx/angular:library libs/domains/sales/feature-quotations --name=sales-feature-quotations \
  --tags=scope:sales,type:feature --prefix=trishul --unitTestRunner=vitest-analog
```

Then add a `scope:sales` constraint in `eslint.config.mjs`, a lazy route in
`apps/erp-web/src/app/app.routes.ts`, and menu entries in `nav-items.ts`.

## API client

Once the backend publishes its OpenAPI document, save it as `libs/core/api/openapi.json` and run
`npx nx run core-api:generate`. Replace the hand-written models in each `data-access` library with
the generated ones; never edit `src/generated` by hand.
