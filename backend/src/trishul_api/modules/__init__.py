"""One package per ERP module, matching the database schemas (core, svc, inv, pur, sal, pre, hr, acc, int, rpt).

Each module has schemas.py (API models), repository.py (queries) and router.py (endpoints).
Modules may import trishul_api.auth, common and db, but not each other's internals.
"""
