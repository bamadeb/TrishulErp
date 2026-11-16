"""Holiday master reads and writes stay on hr.holiday."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.main import create_app

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = ["core.company", "core.state", "core.branch", "hr.holiday"]
ROOT = "/api/v1/hr/leave/holidays"


def test_holiday_list_keeps_national_and_state_scope(settings: Settings) -> None:
    db = sqlite_engine(TABLES)
    insert_row(db, "core.company", id=1, code="TT", legal_name="Trishul")
    insert_row(db, "core.state", id=1, gst_state_code="21", name="Odisha", is_active=True)
    insert_row(db, "core.state", id=2, gst_state_code="29", name="Karnataka", is_active=True)
    insert_row(db, "core.branch", id=1, company_id=1, code="BHK", name="Bhadrak", state_id=1, is_active=True)
    insert_row(db, "core.branch", id=2, company_id=1, code="BLR", name="Bengaluru", state_id=2, is_active=True)
    insert_row(
        db, "hr.holiday", holiday_date=date(2026, 10, 2), name="Gandhi Jayanti", holiday_type="National",
        is_active=True,
    )
    insert_row(
        db, "hr.holiday", holiday_date=date(2026, 9, 15), name="Nuakhai", holiday_type="Festival",
        state_id=1, is_active=True,
    )
    insert_row(
        db, "hr.holiday", holiday_date=date(2026, 11, 18), name="Anla Navami", holiday_type="Optional",
        state_id=1, is_active=True,
    )
    with _client(settings, db) as client:
        summary = client.get(f"{ROOT}/summary", params={"financialYear": 2026})
        assert summary.status_code == 200, summary.text
        body = summary.json()
        assert body["total"] == 3
        assert body["national"] == 1
        assert body["regional"] == 1
        assert body["optional"] == 1
        odisha = client.get(ROOT, params={"financialYear": 2026, "stateId": 1, "pageSize": 20})
        assert odisha.status_code == 200, odisha.text
        names = {item["name"] for item in odisha.json()["items"]}
        assert names == {"Gandhi Jayanti", "Nuakhai", "Anla Navami"}
        other = client.get(ROOT, params={"financialYear": 2026, "locationId": 2, "pageSize": 20})
        assert {item["name"] for item in other.json()["items"]} == {"Gandhi Jayanti"}
        calendar = client.get(
            f"{ROOT}/calendar",
            params={"startDate": "2026-11-01", "endDate": "2026-11-30", "stateId": 1},
        )
        assert [item["name"] for item in calendar.json()] == ["Anla Navami"]
        created = client.post(
            ROOT,
            json={"name": "Nuakhai", "holidayDate": "2026-09-15", "category": "Regional", "stateId": 1},
        )
        assert created.status_code == 409, created.text
        saved = client.post(
            ROOT,
            json={
                "name": "Local observance",
                "holidayDate": "2026-12-01",
                "category": "Regional",
                "stateId": 1,
                "locationId": 1,
                "description": "Bhadrak only",
            },
        )
        assert saved.status_code == 201, saved.text
        assert saved.json()["locationName"] == "Bhadrak"
        assert saved.json()["category"] == "Regional"


@contextmanager
def _client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    api.dependency_overrides[get_current_user] = lambda: make_user(
        id=2, employee_id=12, permissions=frozenset({"hr.leave.manage"})
    )

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as current:
            set_audit_context(current, user_id=2, source="Web", ip_address="127.0.0.1")
            yield current

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
