# Trishul ERP security review (VAPT preparation), 2026-11-26

This review covered the FastAPI backend, the Angular web app, the IIS configuration on the Mumbai server, and the AWS
settings (EC2, RDS, Cognito, Secrets Manager). It recorded:

- what was checked;
- what was fixed in code;
- what still needs a decision or an infrastructure change.

It does **not** certify the system as penetration-test proof. A tester will still report the open items in section 4.

## 1. What was checked and found sound

| Area | Finding |
|---|---|
| Authentication | Cognito access tokens are verified with RS256 against the pool's JWKS. The issuer, expiry, `token_use=access` and `client_id` are all checked. Dev sign-in is refused in uat/prod. A disabled or unknown ERP user gets 403. |
| Authorization | Every route either needs a permission code or is explicitly marked "any signed-in user". `tests/test_api_conventions.py` enforces this. Branch and brand come from headers checked against the user's grants. Document access follows the record it is attached to. A record the user may not see returns 404, not 403. |
| Mass assignment | Request bodies use `InputModel` (`extra="forbid"`), so unknown fields are rejected. |
| SQL injection | All queries go through SQLAlchemy with bound parameters. No SQL is built from strings anywhere in the app. |
| XSS (web) | Angular escapes all bindings. There is no `innerHTML`, `eval` or `document.write`. The two `bypassSecurityTrustUrl` calls wrap `blob:` URLs the page creates itself. |
| CSRF | Not applicable: the API uses bearer tokens in a header, never cookies. CORS allows only the app's own origin. |
| File uploads | Uploads are checked against an extension allow-list, with magic bytes matching the extension. Office macros and zip bombs are refused. Size is limited. Files are stored under generated names outside the web root, and stored paths are checked to stay under the storage root. |
| Signed download links | The token is an HMAC-SHA256, compared in constant time, and expires. An invalid link gets the same 404 whatever the reason. |
| Error handling | RFC 7807 bodies. A 500 returns only a trace id; the details go to the server log. Validation errors don't echo the input. |
| Secrets | Database credentials, the Cognito ids and the face-data key are read from Secrets Manager; none are in the repo. The key and credential files at the repo root are gitignored and were never committed. |
| Data at rest | The RDS storage and the EC2 EBS volume are encrypted. Face vectors and face photos are additionally AES-encrypted. |
| Database login | The API's login has only `db_datareader` and `db_datawriter`. Migrations use a separate login. |
| Network | uvicorn listens on 127.0.0.1 only. The security group opens 80/443 to the world and RDP to three office IPs; WinRM is not reachable from outside. IMDSv2 is required. |
| Cognito | 12-character minimum passwords, admin-only sign-up, user-existence errors hidden, token revocation on, 30–60 minute access tokens. |

## 2. Fixed in this change

| # | Issue | Fix |
|---|---|---|
| 1 | No request rate limiting (OWASP API4). | `common/rate_limit.py` limits each session to 300/min, callers without a token to 60/min, and each IP to 3000/min overall. Own password changes are limited to 5 per 15 min and public quotation links to 30/min. Over a limit the answer is 429 with Retry-After. `TRISHUL_RATE_LIMIT_ENABLED` switches it. |
| 2 | Swagger UI and the full OpenAPI schema were public on the live server (`TRISHUL_ENVIRONMENT=dev`). | `web.config` returns 404 for `/api/v*/docs` and `openapi.json`. The server `.env` should also say `prod` (section 3). |
| 3 | The web app had no security headers: no CSP and no clickjacking protection. | The new `frontend/apps/erp-web/public/web.config` adds a strict CSP (no inline or third-party scripts), X-Frame-Options DENY, nosniff, Referrer-Policy, COOP and a Permissions-Policy that allows only the camera. Critical-CSS inlining is off so index.html has no inline script. |
| 4 | Version disclosure: `Server: Microsoft-IIS/10.0` and `X-Powered-By: ARR/3.0`. | Both are removed in `web.config` (`removeServerHeader` and an outbound rule). TRACE/TRACK are disabled. A 30 MB request limit is set. `.git` and `.env` path segments are hidden. |
| 5 | A download whose file name was not Latin-1 (e.g. Hindi or Odia) failed with 500. The TADA preview served any stored type inline. | `common/downloads.py`: names are sent with an ASCII fallback plus RFC 5987 `filename*`. Quotes, `;` and line breaks are neutralised. Only PDFs and raster images are ever shown inline; everything else downloads. It is used by documents, TADA and quotation PDFs. |
| 6 | The three Excel imports (BYD, ASC register, item prices) read the whole upload before checking its size, and had no zip-bomb or macro check. openpyxl parsed XML without defusedxml. | `common/uploads.py` does bounded reads and the archive check. `defusedxml` was added, so openpyxl uses hardened XML parsing. |
| 7 | Known CVEs in runtime packages: dnspython 2.9.0 (CVE-2026-128089), opentelemetry-api 1.45.1 (CVE-2026-126360) and fast-xml-parser (web). | Upgraded to dnspython 2.9.2 and opentelemetry-api 1.45.2, plus `npm audit fix`. `pip-audit` and `npm audit --omit=dev` now report none. |
| 8 | `httpx2` (needed at startup by the biometric client) was only a dev dependency. A `uv sync --no-dev` deploy removed it and took the API down on 2026-11-23. | It is now a runtime dependency. |
| 9 | In uat/prod a blank download-signing key silently meant a per-process random key. | uat/prod now refuse to start without a key of at least 32 characters. |
| 10 | The API sent no CORP header. | `Cross-Origin-Resource-Policy: same-origin` and `X-Permitted-Cross-Domain-Policies: none` are now sent. |

The tests are in `backend/tests/test_security_hardening.py`. They cover the limiter, the headers, download headers,
upload limits, the zip-bomb and macro checks, defusedxml and the settings checks.

## 3. Deployment and verification

The fixes went live on 2026-11-27: backend and web as deploy38, from commit 86eb0a4, then web-only as deploy39. The deploy now installs the `web.config` from the build and restores the previous one automatically if the IIS checks fail.

Checked from outside against `http://13.204.203.158`:

| Check | Result |
|---|---|
| Site and app routes (`/`, `/hr/leave/mine`) | 200 |
| `/api/v1/me` without a token | 401 |
| `/api/v1/docs` and `/api/v1/openapi.json` | 404 (were 200) |
| `TRACE /` | 404 |
| Web app headers | CSP, X-Frame-Options DENY, Referrer-Policy and Permissions-Policy all sent |
| API headers | Strict CSP, X-Frame-Options, CORP same-origin |
| `Server` header | Removed (was `Microsoft-IIS/10.0`) |
| `X-Powered-By` header | Still sent, but empty (was `ARR/3.0`) |
| Runtime packages | defusedxml installed, dnspython 2.9.2 and opentelemetry-api 1.45.2, httpx2 kept |

Before release, the production web build was also loaded in headless Chrome under the exact CSP from `web.config`. It reported no CSP violations.

Testing:

- The 23 new security tests pass.
- The 274 tests for the touched modules pass: documents, sales, TADA, the BYD, ASC, item and price imports, service reports and complaints.
- The full backend suite was not run to completion on the merged code. Up to the point it was stopped, every failure was in API-convention and model checks that were already failing before this change.

**Not done, by decision:** the server `.env` still says `TRISHUL_ENVIRONMENT=dev`.

- Swagger is blocked from outside by IIS, but the API itself would still serve it locally.
- Dev sign-in is not blocked by configuration. It is only off because `AUTH_MODE=cognito`.
- Setting `prod` closes both. The existing 64-character signing key already meets the new prod check.

## 4. Remaining risks (need a decision or infrastructure work)

| Severity | Risk | What closes it |
|---|---|---|
| **High** | **The site and the mobile app use plain HTTP** (`http://13.204.203.158`). Access tokens, passwords for own-password change, face photos and personal data cross the internet unencrypted. Every VAPT report will list this first. HSTS has no effect over HTTP. The web camera also needs HTTPS. | A domain name plus a TLS certificate: either ACM on an ALB in front of the EC2, or win-acme / Let's Encrypt on IIS. Then add a port 80 → 443 redirect and HSTS, switch the mobile app to `https://` and remove `usesCleartextTraffic`. |
| High | **MFA is off** in the Cognito user pool, including for Admin and HR accounts. | Turn on optional TOTP MFA and require it for privileged roles. |
| Medium | **RDS is publicly accessible.** Port 1433 is limited to the app server and five developer IPs, but the list keeps growing and the endpoint is on the internet. | Make RDS private and reach it through SSM port forwarding or a VPN. At least prune the developer IPs regularly. |
| Medium | **Database TLS is not verified.** `TRISHUL_DB_TRUST_SERVER_CERTIFICATE=true`, and RDS does not force TLS (`rds.force_ssl=0`, default parameter group). | Import the RDS CA (`rds-ca-rsa2048-g1`) into the server's machine store, set trust to false, and use a custom parameter group with `rds.force_ssl=1`. The force_ssl change needs a reboot. |
| Medium | **Row-level security is not installed on RDS.** Branch and brand isolation relies only on the API's checks. `database/10_row_level_security.sql` exists but has not been applied. | Apply it in UAT first. It filters every query, so the jobs and imports need testing. |
| Medium | The API service runs as **LocalSystem**, and the backend folder (including `.env`) is readable by `BUILTIN\Users`. | Run TrishulApi as a dedicated low-rights service account. Limit the ACL to that account and Administrators. |
| Low | Web tokens are kept in `localStorage` (Amplify default), so an XSS could read them. | Mitigated by the strict CSP and Angular escaping. Moving to cookie storage would need a backend-for-frontend. |
| Low | The server runs with `TRISHUL_ENVIRONMENT=dev`. Swagger is blocked only at IIS, and dev sign-in is off only because of `AUTH_MODE`. | Set `TRISHUL_ENVIRONMENT=prod` in the server `.env`. |
| Low | RDS deletion protection is off, and there is one AZ. | Turn on deletion protection. |
| Low | Old `src.bak-*`, `.env.bak-*` and `uv.lock.bak-*` copies pile up in `C:\trishul\app\backend`. | Keep the last few and delete the rest. The `.env` backups hold secret ids, not secrets. |
| Low | Dev-only npm packages (vite dev server, nx / undici) have advisories. They are not shipped to browsers. | Upgrade Nx to 24 and Angular build tooling in a planned upgrade. |
| Info | The rate limiter's state is per process. | Fine for the current single uvicorn process. Use a shared store (Redis) if the API is ever scaled out. |
| Info | Object-level authorization was reviewed by design and by sampling (documents, complaints, calls, travel), not by exhaustively testing every endpoint. | Include authenticated, role-by-role IDOR testing in the VAPT scope. |
