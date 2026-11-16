"""Idempotent official holidays for TrishulDev.

Inserts the three gazetted national holidays for 2026 and the Odisha list from Revenue and
Disaster Management notification 42428 dated 11 November 2025. Annexure-I has 29 public
holidays. Republic Day, Independence Day and Gandhi Jayanti are stored once as National,
so they are not repeated as Odisha-only rows. The other 26 Annexure-I days are Festival
rows for Odisha. Annexure-II has 9 optional holidays. Annexure-III days are not inserted:
the notification says they were not declared because they fall on a Sunday or a second or
fourth Saturday.

Existing rows with the same date and name are left unchanged. A second run inserts nothing.
The script refuses every database except TrishulDev and does not change leave balances.

    uv run --no-sync python scripts/seed_official_holidays.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from trishul_api.config import get_settings  # noqa: E402
from trishul_api.db.engine import create_db_engine  # noqa: E402
from trishul_api.db.models import Holiday, State  # noqa: E402
from trishul_api.secrets import create_secret_provider  # noqa: E402

NOTICE = "42428"
NOTICE_ON = date(2025, 11, 11)
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# Annexure-I. The three national days are flagged so they are stored once, for every location.
PUBLIC: tuple[tuple[str, str, str, bool], ...] = (
    ("Makar Sankranti", "2026-01-14", "Wednesday", False),
    ("Subash Chandra Bose Jayanti/Vir Surendrasai Jayanti/ Basanta Panchami", "2026-01-23", "Friday", False),
    ("Republic Day", "2026-01-26", "Monday", True),
    ("Dola Purnima", "2026-03-03", "Tuesday", False),
    ("Holi", "2026-03-04", "Wednesday", False),
    ("Id-ul-Fitre", "2026-03-21", "Saturday", False),
    ("Shree Rama Navami", "2026-03-27", "Friday", False),
    ("Utkal Divas", "2026-04-01", "Wednesday", False),
    ("Good Friday", "2026-04-03", "Friday", False),
    ("Dr. B.R.Ambedkar Jayanti/ Maha Visuva Sankranti", "2026-04-14", "Tuesday", False),
    ("Buddha Purnima/ Pandit Raghunath Murumu's Birthday", "2026-05-01", "Friday", False),
    ("Sabitri Amabasya", "2026-05-16", "Saturday", False),
    ("Id-ul-Zuha", "2026-05-27", "Wednesday", False),
    ("Raja Sankranti", "2026-06-15", "Monday", False),
    ("Muharram", "2026-06-26", "Friday", False),
    ("Rath Yatra", "2026-07-16", "Thursday", False),
    ("Independence Day", "2026-08-15", "Saturday", True),
    ("Birthday of Prophet Muhammad", "2026-08-26", "Wednesday", False),
    ("Jhulana Purnima", "2026-08-27", "Thursday", False),
    ("Janmashtami", "2026-09-04", "Friday", False),
    ("Ganesh Puja", "2026-09-14", "Monday", False),
    ("Nuakhai", "2026-09-15", "Tuesday", False),
    ("Day following Nuakhai", "2026-09-16", "Wednesday", False),
    ("Gandhi Jayanti", "2026-10-02", "Friday", True),
    ("Mahasaptami", "2026-10-17", "Saturday", False),
    ("Mahanavami", "2026-10-19", "Monday", False),
    ("Vijaya Dasami", "2026-10-20", "Tuesday", False),
    ("Rahas Purnima", "2026-11-24", "Tuesday", False),
    ("X-Mas Day", "2026-12-25", "Friday", False),
)
OPTIONAL: tuple[tuple[str, str, str], ...] = (
    ("Guru Gobind Singh's Birthday", "2026-01-06", "Tuesday"),
    ("Sab-e-Quadar", "2026-03-17", "Tuesday"),
    ("Easter Saturday", "2026-04-04", "Saturday"),
    ("Birthday of Raja Ram Mohan Roy", "2026-05-22", "Friday"),
    ("Bahuda Yatra", "2026-07-24", "Friday"),
    ("Foundation Day of Bramho Samaj", "2026-08-20", "Thursday"),
    ("Anla Navami", "2026-11-18", "Wednesday"),
    ("Prathamasthami", "2026-12-01", "Tuesday"),
    ("Christmas Eve", "2026-12-24", "Thursday"),
)


def main() -> None:
    _check_dates()
    engine = _engine()
    with Session(engine) as db:
        _require_dev(db)
        _ensure_columns(db)
        db.commit()
        inserted = _seed(db)
        db.commit()
        _verify(db)
        print("inserted", inserted)
    engine.dispose()


def _check_dates() -> None:
    if len(PUBLIC) != 29 or sum(1 for row in PUBLIC if row[3]) != 3:
        raise SystemExit("Annexure-I must contain 29 public holidays, including the 3 national days.")
    if len(OPTIONAL) != 9:
        raise SystemExit("Annexure-II must contain 9 optional holidays.")
    seen: set[tuple[str, str]] = set()
    for name, iso, weekday, _national in PUBLIC:
        _expect(name, iso, weekday, seen)
    for name, iso, weekday in OPTIONAL:
        _expect(name, iso, weekday, seen)


def _expect(name: str, iso: str, weekday: str, seen: set[tuple[str, str]]) -> None:
    if len(name) > 80:
        raise SystemExit(f"{name} is longer than 80 characters.")
    key = (iso, name.lower())
    if key in seen:
        raise SystemExit(f"Duplicate holiday in the source list: {name} {iso}")
    seen.add(key)
    value = date.fromisoformat(iso)
    actual = WEEKDAYS[value.weekday()]
    if not weekday.endswith(actual) and weekday != actual:
        raise SystemExit(f"{name} {iso} is {actual}, not {weekday}.")


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


def _require_dev(db: Session) -> None:
    name = db.execute(text("SELECT DB_NAME()")).scalar()
    print(f"database {name}", flush=True)
    if name != "TrishulDev":
        raise SystemExit("Refusing to change holidays because this is not TrishulDev.")


def _ensure_columns(db: Session) -> None:
    statements = (
        "IF COL_LENGTH(N'hr.holiday', N'state_id') IS NULL ALTER TABLE hr.holiday ADD state_id BIGINT NULL",
        """
        IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_hr_holiday_state_id')
            ALTER TABLE hr.holiday ADD CONSTRAINT FK_hr_holiday_state_id
                FOREIGN KEY (state_id) REFERENCES core.state(id)
        """,
        """
        IF COL_LENGTH(N'hr.holiday', N'source_notification_no') IS NULL
            ALTER TABLE hr.holiday ADD source_notification_no NVARCHAR(40) NULL
        """,
        """
        IF COL_LENGTH(N'hr.holiday', N'source_notification_date') IS NULL
            ALTER TABLE hr.holiday ADD source_notification_date DATE NULL
        """,
        """
        IF COL_LENGTH(N'hr.holiday', N'description') IS NULL
            ALTER TABLE hr.holiday ADD description NVARCHAR(400) NULL
        """,
        """
        IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = N'0036_holiday_scope')
            INSERT INTO alembic_version (version_num) VALUES (N'0036_holiday_scope')
        """,
    )
    for statement in statements:
        db.execute(text(statement))


def _seed(db: Session) -> int:
    state_id = db.scalar(select(State.id).where(State.name == "Odisha", State.is_active == True))  # noqa: E712
    if state_id is None:
        raise SystemExit("Odisha is not in core.state.")
    user_id = db.execute(text("SELECT TOP 1 id FROM core.app_user WHERE is_active = 1 ORDER BY id")).scalar()
    inserted = 0
    for name, iso, _weekday, national in PUBLIC:
        holiday_type = "National" if national else "Festival"
        description = (
            "Gazetted national holiday. The 2026 date is also listed in Odisha notification 42428, Annexure-I."
            if national
            else "Odisha Government notification 42428 dated 11 November 2025, Annexure-I."
        )
        inserted += _insert(
            db, name, date.fromisoformat(iso), holiday_type, None if national else state_id, description, user_id
        )
    for name, iso, _weekday in OPTIONAL:
        inserted += _insert(
            db,
            name,
            date.fromisoformat(iso),
            "Optional",
            state_id,
            "Odisha Government notification 42428 dated 11 November 2025, Annexure-II. Optional holiday.",
            user_id,
        )
    return inserted


def _insert(
    db: Session,
    name: str,
    holiday_date: date,
    holiday_type: str,
    state_id: int | None,
    description: str,
    user_id: int | None,
) -> int:
    existing = db.scalar(
        select(Holiday.id).where(Holiday.holiday_date == holiday_date, func.lower(Holiday.name) == name.lower())
    )
    if existing is not None:
        print(f"kept existing {name} {holiday_date.isoformat()}", flush=True)
        return 0
    db.execute(
        Holiday.__table__.insert().values(
            name=name,
            holiday_date=holiday_date,
            holiday_type=holiday_type,
            state_id=state_id,
            branch_id=None,
            description=description,
            source_notification_no=None if holiday_type == "National" else NOTICE,
            source_notification_date=None if holiday_type == "National" else NOTICE_ON,
            is_active=True,
            created_by_user_id=user_id,
        )
    )
    return 1


def _verify(db: Session) -> None:
    rows = db.execute(
        text(
            """
            SELECT holiday_type, COUNT(*)
            FROM hr.holiday
            WHERE holiday_date >= '2026-01-01' AND holiday_date <= '2026-12-31'
              AND (source_notification_no = N'42428' OR holiday_type = N'National')
            GROUP BY holiday_type
            """
        )
    ).all()
    counts = {row[0]: row[1] for row in rows}
    print("stored", counts, flush=True)
    if counts.get("National", 0) < 3 or counts.get("Festival", 0) != 26 or counts.get("Optional", 0) != 9:
        raise SystemExit(f"Unexpected holiday counts: {counts}")
    gandhi = db.scalar(select(func.count()).select_from(Holiday).where(func.lower(Holiday.name) == "gandhi jayanti"))
    if gandhi != 1:
        raise SystemExit(f"Gandhi Jayanti count is {gandhi}, expected 1.")


if __name__ == "__main__":
    main()
