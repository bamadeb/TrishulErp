"""Seed realistic demo biometric data into TrishulDev.

Uses existing core.employee rows only. Idempotent: skips devices/mappings/punches/
sync rows that already exist (identified by DEMO-prefixed codes / external ids).

    uv run --no-sync python scripts/seed_biometric_demo_data.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from trishul_api.config import get_settings  # noqa: E402
from trishul_api.db.engine import create_db_engine  # noqa: E402
from trishul_api.secrets import create_secret_provider  # noqa: E402

DEMO_PREFIX = "DEMO-"
SOURCE = "Demo"
EMPLOYEE_LIMIT = 12
WORKING_DAYS = 10


def _engine():
    settings = get_settings()
    if settings.migration_db_secret_id:
        settings = settings.model_copy(update={"db_secret_id": settings.migration_db_secret_id})
        return create_db_engine(settings, create_secret_provider(settings))
    if settings.migration_db_user:
        settings = settings.model_copy(
            update={
                "db_user": settings.migration_db_user,
                "db_password": settings.migration_db_password,
                "db_secret_id": None,
            }
        )
        return create_db_engine(settings, None)
    secrets = create_secret_provider(settings) if settings.db_secret_id else None
    return create_db_engine(settings, secrets)


def _recent_working_days(count: int, *, today: dt.date | None = None) -> list[dt.date]:
    """Return the last `count` weekdays ending at today (or yesterday if weekend)."""
    cursor = today or dt.date.today()
    while cursor.weekday() >= 5:
        cursor -= dt.timedelta(days=1)
    days: list[dt.date] = []
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= dt.timedelta(days=1)
    days.reverse()
    return days


def _pick_employees(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                e.id,
                e.employee_code,
                e.first_name,
                e.last_name,
                e.branch_id,
                b.name AS branch_name,
                e.department_id,
                d.name AS department_name
            FROM core.employee e
            LEFT JOIN core.branch b ON b.id = e.branch_id
            LEFT JOIN hr.department d ON d.id = e.department_id
            WHERE e.is_active = 1
              AND (e.status = N'Active' OR e.status IS NULL)
            ORDER BY
                CASE WHEN e.department_id IS NULL THEN 1 ELSE 0 END,
                e.department_id,
                CASE WHEN e.branch_id IS NULL THEN 1 ELSE 0 END,
                e.branch_id,
                e.id
            """
        )
    ).mappings().all()
    if not rows:
        raise SystemExit("No active employees found in core.employee.")

    # Prefer diverse departments/branches while capping at EMPLOYEE_LIMIT.
    picked: list[dict] = []
    seen_dept: set[int | None] = set()
    seen_branch: set[int | None] = set()
    for row in rows:
        item = dict(row)
        if len(picked) >= EMPLOYEE_LIMIT:
            break
        dept = item["department_id"]
        branch = item["branch_id"]
        if dept not in seen_dept or branch not in seen_branch or len(picked) < 6:
            picked.append(item)
            seen_dept.add(dept)
            seen_branch.add(branch)
    if len(picked) < min(EMPLOYEE_LIMIT, len(rows)):
        for row in rows:
            item = dict(row)
            if item["id"] in {p["id"] for p in picked}:
                continue
            picked.append(item)
            if len(picked) >= EMPLOYEE_LIMIT:
                break
    return picked


def _ensure_devices(db: Session, branch_ids: list[int | None]) -> list[dict]:
    device_specs = [
        {
            "code": f"{DEMO_PREFIX}BIO-HQ-01",
            "name": "HQ Main Entrance (Demo)",
            "serial_number": "DEMO-SN-HQ-1001",
            "location_name": "Head Office — Main Gate",
            "external_device_id": "DEMO-ESSL-HQ-01",
            "branch_id": next((b for b in branch_ids if b is not None), None),
        },
        {
            "code": f"{DEMO_PREFIX}BIO-PLANT-01",
            "name": "Plant Floor Terminal (Demo)",
            "serial_number": "DEMO-SN-PL-2002",
            "location_name": "Plant — Shop Floor",
            "external_device_id": "DEMO-ESSL-PL-01",
            "branch_id": next((b for b in branch_ids if b is not None and b != branch_ids[0]), branch_ids[0] if branch_ids else None),
        },
        {
            "code": f"{DEMO_PREFIX}BIO-WH-01",
            "name": "Warehouse Exit Reader (Demo)",
            "serial_number": "DEMO-SN-WH-3003",
            "location_name": "Warehouse — Exit",
            "external_device_id": "DEMO-ESSL-WH-01",
            "branch_id": next((b for b in reversed(branch_ids) if b is not None), None),
        },
    ]

    inserted = 0
    for spec in device_specs:
        exists = db.execute(
            text("SELECT id FROM hr.biometric_device WHERE code = :code"),
            {"code": spec["code"]},
        ).scalar()
        if exists:
            continue
        db.execute(
            text(
                """
                INSERT INTO hr.biometric_device (
                    code, name, vendor, serial_number, location_name, branch_id,
                    external_device_id, credential_secret_name, base_url,
                    is_sync_enabled, last_synced_at, is_active
                )
                VALUES (
                    :code, :name, N'ESSL', :serial_number, :location_name, :branch_id,
                    :external_device_id, N'trishul/demo/biometric-essl', NULL,
                    0, SYSUTCDATETIME(), 1
                )
                """
            ),
            spec,
        )
        inserted += 1

    devices = db.execute(
        text(
            """
            SELECT id, code, name, location_name, branch_id, external_device_id
            FROM hr.biometric_device
            WHERE code LIKE :pfx
            ORDER BY id
            """
        ),
        {"pfx": f"{DEMO_PREFIX}%"},
    ).mappings().all()
    return [dict(d) for d in devices], inserted


def _ensure_mappings(db: Session, employees: list[dict], devices: list[dict]) -> tuple[list[dict], int]:
    inserted = 0
    effective_from = dt.date.today() - dt.timedelta(days=90)
    for idx, emp in enumerate(employees):
        device = devices[idx % len(devices)]
        bio_user = f"{DEMO_PREFIX}UID-{emp['employee_code'] or emp['id']}"
        exists = db.execute(
            text(
                """
                SELECT id FROM hr.biometric_employee_mapping
                WHERE employee_id = :employee_id
                  AND biometric_user_id = :biometric_user_id
                  AND device_id = :device_id
                  AND is_active = 1
                """
            ),
            {
                "employee_id": emp["id"],
                "biometric_user_id": bio_user,
                "device_id": device["id"],
            },
        ).scalar()
        if exists:
            continue
        db.execute(
            text(
                """
                INSERT INTO hr.biometric_employee_mapping (
                    employee_id, biometric_user_id, device_id,
                    effective_from, effective_to, is_active
                )
                VALUES (
                    :employee_id, :biometric_user_id, :device_id,
                    :effective_from, NULL, 1
                )
                """
            ),
            {
                "employee_id": emp["id"],
                "biometric_user_id": bio_user,
                "device_id": device["id"],
                "effective_from": effective_from,
            },
        )
        inserted += 1

    mappings = db.execute(
        text(
            """
            SELECT
                m.id, m.employee_id, m.biometric_user_id, m.device_id,
                e.employee_code, e.first_name, e.last_name
            FROM hr.biometric_employee_mapping m
            JOIN core.employee e ON e.id = m.employee_id
            WHERE m.biometric_user_id LIKE :pfx AND m.is_active = 1
            ORDER BY m.id
            """
        ),
        {"pfx": f"{DEMO_PREFIX}%"},
    ).mappings().all()
    return [dict(m) for m in mappings], inserted


def _punch_plan(day_index: int, emp_index: int) -> list[tuple[str, dt.time]]:
    """Return punch_type + local time patterns including late/early/missing scenarios."""
    pattern = (day_index + emp_index) % 7
    if pattern == 0:
        # Normal day: IN + OUT + mid-day OUT/IN
        return [
            ("IN", dt.time(9, 2 + (emp_index % 8))),
            ("OUT", dt.time(13, 0 + (emp_index % 5))),
            ("IN", dt.time(13, 45 + (emp_index % 4))),
            ("OUT", dt.time(18, 5 + (emp_index % 10))),
        ]
    if pattern == 1:
        # Late arrival
        return [
            ("IN", dt.time(9, 35 + (emp_index % 15))),
            ("OUT", dt.time(18, 20 + (emp_index % 8))),
        ]
    if pattern == 2:
        # Early departure
        return [
            ("IN", dt.time(8, 55 + (emp_index % 5))),
            ("OUT", dt.time(16, 10 + (emp_index % 20))),
        ]
    if pattern == 3:
        # Missing OUT
        return [("IN", dt.time(9, 5 + (emp_index % 10)))]
    if pattern == 4:
        # Missing IN (only OUT recorded)
        return [("OUT", dt.time(18, 0 + (emp_index % 12)))]
    if pattern == 5:
        # Short day / half-day style
        return [
            ("IN", dt.time(9, 0 + (emp_index % 6))),
            ("OUT", dt.time(13, 30 + (emp_index % 10))),
        ]
    # Weekend-adjacent busy day with multiple punches
    return [
        ("IN", dt.time(8, 50)),
        ("OUT", dt.time(12, 15)),
        ("IN", dt.time(12, 55)),
        ("OUT", dt.time(17, 40 + (emp_index % 15))),
    ]


def _ensure_sync_logs(db: Session, devices: list[dict], working_days: list[dt.date]) -> tuple[dict[int, int], int]:
    """Insert success + failed demo sync logs; return device_id -> latest success sync_log_id."""
    inserted = 0
    success_ids: dict[int, int] = {}

    for device in devices:
        # One failed sync (network/timeout style) — identify via DEMO error message prefix.
        fail_marker = f"{DEMO_PREFIX}FAIL-{device['code']}"
        exists_fail = db.execute(
            text(
                """
                SELECT id FROM hr.biometric_sync_log
                WHERE device_id = :device_id
                  AND error_message LIKE :marker
                """
            ),
            {"device_id": device["id"], "marker": f"{fail_marker}%"},
        ).scalar()
        if not exists_fail:
            started = dt.datetime.combine(working_days[0], dt.time(6, 5))
            finished = started + dt.timedelta(minutes=2)
            db.execute(
                text(
                    """
                    INSERT INTO hr.biometric_sync_log (
                        device_id, started_at, finished_at, status, [trigger],
                        records_fetched, records_inserted, records_duplicate, error_message
                    )
                    VALUES (
                        :device_id, :started_at, :finished_at, N'Failed', N'Manual',
                        0, 0, 0, :error_message
                    )
                    """
                ),
                {
                    "device_id": device["id"],
                    "started_at": started,
                    "finished_at": finished,
                    "error_message": f"{fail_marker}: device unreachable (demo — connection timeout)",
                },
            )
            inserted += 1

        # One successful sync covering the demo window.
        ok_marker = f"{DEMO_PREFIX}OK-{device['code']}"
        existing_ok = db.execute(
            text(
                """
                SELECT id FROM hr.biometric_sync_log
                WHERE device_id = :device_id
                  AND status = N'Success'
                  AND error_message = :marker
                """
            ),
            {"device_id": device["id"], "marker": ok_marker},
        ).scalar()
        if existing_ok:
            success_ids[device["id"]] = int(existing_ok)
            continue

        started = dt.datetime.combine(working_days[-1], dt.time(19, 15))
        finished = started + dt.timedelta(minutes=4)
        result = db.execute(
            text(
                """
                INSERT INTO hr.biometric_sync_log (
                    device_id, started_at, finished_at, status, [trigger],
                    records_fetched, records_inserted, records_duplicate, error_message
                )
                OUTPUT INSERTED.id
                VALUES (
                    :device_id, :started_at, :finished_at, N'Success', N'Manual',
                    0, 0, 0, :error_message
                )
                """
            ),
            {
                "device_id": device["id"],
                "started_at": started,
                "finished_at": finished,
                "error_message": ok_marker,
            },
        )
        sync_id = int(result.scalar())
        success_ids[device["id"]] = sync_id
        inserted += 1

    # One scheduled success with no device (all-devices style) if supported (device_id nullable).
    global_marker = f"{DEMO_PREFIX}OK-ALL"
    exists_global = db.execute(
        text(
            """
            SELECT id FROM hr.biometric_sync_log
            WHERE device_id IS NULL AND error_message = :marker
            """
        ),
        {"marker": global_marker},
    ).scalar()
    if not exists_global:
        started = dt.datetime.combine(working_days[-1], dt.time(20, 0))
        finished = started + dt.timedelta(minutes=6)
        db.execute(
            text(
                """
                INSERT INTO hr.biometric_sync_log (
                    device_id, started_at, finished_at, status, [trigger],
                    records_fetched, records_inserted, records_duplicate, error_message
                )
                VALUES (
                    NULL, :started_at, :finished_at, N'Success', N'Scheduled',
                    0, 0, 0, :error_message
                )
                """
            ),
            {
                "started_at": started,
                "finished_at": finished,
                "error_message": global_marker,
            },
        )
        inserted += 1

    return success_ids, inserted


def _ensure_punches(
    db: Session,
    mappings: list[dict],
    devices_by_id: dict[int, dict],
    sync_ids: dict[int, int],
    working_days: list[dt.date],
) -> int:
    inserted = 0
    for emp_index, mapping in enumerate(mappings):
        device_id = mapping["device_id"]
        sync_log_id = sync_ids.get(device_id)
        bio_user = mapping["biometric_user_id"]
        for day_index, day in enumerate(working_days):
            for punch_type, punch_time in _punch_plan(day_index, emp_index):
                punched_at = dt.datetime.combine(day, punch_time)
                external_punch_id = (
                    f"{DEMO_PREFIX}PUNCH-{mapping['employee_id']}-{day.isoformat()}-"
                    f"{punch_type}-{punch_time.strftime('%H%M%S')}"
                )
                exists = db.execute(
                    text(
                        """
                        SELECT id FROM hr.biometric_punch_log
                        WHERE device_id = :device_id
                          AND external_punch_id = :external_punch_id
                          AND is_active = 1
                        """
                    ),
                    {"device_id": device_id, "external_punch_id": external_punch_id},
                ).scalar()
                if exists:
                    continue
                db.execute(
                    text(
                        """
                        INSERT INTO hr.biometric_punch_log (
                            device_id, employee_id, biometric_user_id, punched_at,
                            punch_type, external_punch_id, source, sync_log_id, is_active
                        )
                        VALUES (
                            :device_id, :employee_id, :biometric_user_id, :punched_at,
                            :punch_type, :external_punch_id, :source, :sync_log_id, 1
                        )
                        """
                    ),
                    {
                        "device_id": device_id,
                        "employee_id": mapping["employee_id"],
                        "biometric_user_id": bio_user,
                        "punched_at": punched_at,
                        "punch_type": punch_type,
                        "external_punch_id": external_punch_id,
                        "source": SOURCE,
                        "sync_log_id": sync_log_id,
                    },
                )
                inserted += 1
                _ = devices_by_id  # reserved for future location tagging
    return inserted


def _update_sync_counts_safe(db: Session, sync_ids: dict[int, int]) -> None:
    for sync_id in sync_ids.values():
        counts = db.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM hr.biometric_punch_log
                WHERE sync_log_id = :sync_log_id AND is_active = 1
                """
            ),
            {"sync_log_id": sync_id},
        ).scalar()
        cnt = int(counts or 0)
        db.execute(
            text(
                """
                UPDATE hr.biometric_sync_log
                SET records_fetched = :cnt,
                    records_inserted = :cnt,
                    records_duplicate = 0
                WHERE id = :id
                """
            ),
            {"cnt": cnt, "id": sync_id},
        )
    # Touch last_synced_at on demo devices that have a success sync.
    db.execute(
        text(
            """
            UPDATE d
            SET last_synced_at = s.finished_at
            FROM hr.biometric_device d
            JOIN hr.biometric_sync_log s ON s.device_id = d.id
            WHERE d.code LIKE :pfx
              AND s.status = N'Success'
              AND s.error_message LIKE :okpfx
            """
        ),
        {"pfx": f"{DEMO_PREFIX}%", "okpfx": f"{DEMO_PREFIX}OK-%"},
    )


def _validate(db: Session) -> None:
    print("\n=== Validation ===")
    for table, where in [
        ("hr.biometric_device", "code LIKE :pfx"),
        ("hr.biometric_employee_mapping", "biometric_user_id LIKE :pfx"),
        ("hr.biometric_punch_log", "external_punch_id LIKE :pfx"),
        ("hr.biometric_sync_log", "error_message LIKE :pfx"),
    ]:
        cnt = db.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {where}"),
            {"pfx": f"{DEMO_PREFIX}%"},
        ).scalar()
        print(f"{table}: {cnt} demo rows")

    orphans = db.execute(
        text(
            """
            SELECT COUNT(*) FROM hr.biometric_punch_log p
            WHERE p.external_punch_id LIKE :pfx
              AND (
                NOT EXISTS (SELECT 1 FROM hr.biometric_device d WHERE d.id = p.device_id)
                OR (
                    p.employee_id IS NOT NULL
                    AND NOT EXISTS (SELECT 1 FROM core.employee e WHERE e.id = p.employee_id)
                )
                OR (
                    p.sync_log_id IS NOT NULL
                    AND NOT EXISTS (SELECT 1 FROM hr.biometric_sync_log s WHERE s.id = p.sync_log_id)
                )
              )
            """
        ),
        {"pfx": f"{DEMO_PREFIX}%"},
    ).scalar()
    print(f"orphan punches: {orphans}")

    sample = db.execute(
        text(
            """
            SELECT TOP 8
                e.employee_code,
                e.first_name + N' ' + e.last_name AS employee_name,
                d.code AS device_code,
                p.punch_type,
                p.punched_at,
                p.source
            FROM hr.biometric_punch_log p
            JOIN core.employee e ON e.id = p.employee_id
            JOIN hr.biometric_device d ON d.id = p.device_id
            WHERE p.external_punch_id LIKE :pfx
            ORDER BY p.punched_at DESC
            """
        ),
        {"pfx": f"{DEMO_PREFIX}%"},
    ).mappings().all()
    print("sample punches:")
    for row in sample:
        print(dict(row))

    syncs = db.execute(
        text(
            """
            SELECT
                ISNULL(d.code, N'(all devices)') AS device_code,
                s.status, s.[trigger], s.records_fetched, s.records_inserted,
                LEFT(s.error_message, 80) AS marker
            FROM hr.biometric_sync_log s
            LEFT JOIN hr.biometric_device d ON d.id = s.device_id
            WHERE s.error_message LIKE :pfx
            ORDER BY s.started_at
            """
        ),
        {"pfx": f"{DEMO_PREFIX}%"},
    ).mappings().all()
    print("sync logs:")
    for row in syncs:
        print(dict(row))


def main() -> None:
    engine = _engine()
    with Session(engine) as db:
        name = db.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to seed because this is not TrishulDev.")

        employees = _pick_employees(db)
        print(f"selected {len(employees)} employees:")
        for emp in employees:
            print(
                f"  id={emp['id']} code={emp['employee_code']} "
                f"{emp['first_name']} {emp['last_name']} "
                f"dept={emp['department_name']} branch={emp['branch_name']}"
            )

        working_days = _recent_working_days(WORKING_DAYS)
        print(f"working days ({len(working_days)}): {working_days[0]} .. {working_days[-1]}")

        try:
            devices, devices_inserted = _ensure_devices(
                db, [e["branch_id"] for e in employees]
            )
            if not devices:
                raise SystemExit("No demo devices available after insert.")
            print(f"devices: +{devices_inserted} inserted, {len(devices)} total demo")

            mappings, mappings_inserted = _ensure_mappings(db, employees, devices)
            print(f"mappings: +{mappings_inserted} inserted, {len(mappings)} total demo")

            sync_ids, sync_inserted = _ensure_sync_logs(db, devices, working_days)
            print(f"sync logs: +{sync_inserted} inserted")

            devices_by_id = {d["id"]: d for d in devices}
            punches_inserted = _ensure_punches(
                db, mappings, devices_by_id, sync_ids, working_days
            )
            print(f"punches: +{punches_inserted} inserted")

            _update_sync_counts_safe(db, sync_ids)
            db.commit()
            print("committed")
        except Exception:
            db.rollback()
            raise

        _validate(db)

        # Final insert summary for this run
        print("\n=== Inserted this run ===")
        print(f"hr.biometric_device: {devices_inserted}")
        print(f"hr.biometric_employee_mapping: {mappings_inserted}")
        print(f"hr.biometric_sync_log: {sync_inserted}")
        print(f"hr.biometric_punch_log: {punches_inserted}")


if __name__ == "__main__":
    main()
