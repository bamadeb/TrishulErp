"""Approval comments stay on each status-history row. No database."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from .conftest import make_user
from trishul_api.modules.hr.tada.schemas import TadaDecisionCreate, TadaSettlementCreate, TadaTripDecisionCreate
from trishul_api.modules.hr.tada.service import InvalidDecision, TadaService


def test_approval_comment_is_optional() -> None:
    decision = TadaDecisionCreate(payroll_month="2026-11", employee_ids=[5], decision="Approved")
    assert decision.remarks is None


def test_approval_keeps_a_comment() -> None:
    decision = TadaDecisionCreate(
        payroll_month="2026-11", employee_ids=[5], decision="Approved", remarks="  Checked the trips.  "
    )
    assert decision.remarks == "Checked the trips."


def test_rejection_requires_a_reason() -> None:
    with pytest.raises(ValidationError, match="rejection reason"):
        TadaDecisionCreate(payroll_month="2026-11", employee_ids=[5], decision="Rejected", remarks="  ")


def test_rejection_keeps_the_reason() -> None:
    decision = TadaDecisionCreate(
        payroll_month="2026-11", employee_ids=[5], decision="Rejected", remarks="Distance was adjusted twice."
    )
    assert decision.remarks == "Distance was adjusted twice."


class _History:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []
        self.trip_rows: list[dict[str, object]] = []
        self.committed = 0

    def employee_codes(self, employee_ids: list[int]) -> dict[int, str]:
        return {employee_id: f"EMP{employee_id:04d}" for employee_id in employee_ids}

    def payable_employees(self, employee_ids: list[int], _start: datetime, _end: datetime) -> set[int]:
        return set(employee_ids)

    def current_decisions(self, month: str, employee_ids: list[int]) -> dict[int, str]:
        latest: dict[int, str] = {}
        for row in self.rows:
            if row["month"] == month:
                latest[int(row["employee_id"])] = str(row["to_status"])
        return {employee_id: latest[employee_id] for employee_id in employee_ids if employee_id in latest}

    def record_decision(self, **row: object) -> None:
        self.rows.append(row)

    def approved_trip_ids(self, _employee_ids: list[int], _start: datetime, _end: datetime) -> list[int]:
        return []

    def record_trip_decision(self, **row: object) -> None:
        self.trip_rows.append(row)

    def commit(self) -> None:
        self.committed += 1


def _service() -> tuple[TadaService, _History]:
    service = TadaService.__new__(TadaService)
    history = _History()
    service._trips = history
    return service, history


def test_comments_are_appended_for_each_employee_and_not_overwritten() -> None:
    service, history = _service()
    actor = make_user(id=9, permissions=frozenset({"core.employee.manage"}))
    approved = service.decide(
        TadaDecisionCreate(
            payroll_month="2026-11", employee_ids=[5, 6], decision="Approved", remarks="Ready for payroll."
        ),
        actor,
    )
    assert approved.updated == 2
    assert [row["remarks"] for row in history.rows] == ["Ready for payroll.", "Ready for payroll."]

    again = service.decide(
        TadaDecisionCreate(payroll_month="2026-11", employee_ids=[5], decision="Approved", remarks="Second note"),
        actor,
    )
    assert again.updated == 0
    assert history.rows[0]["remarks"] == "Ready for payroll."

    sent = service.send_to_payroll(TadaSettlementCreate(payroll_month="2026-11", employee_ids=[5]), actor)
    assert sent.updated == 1
    assert history.rows[0]["remarks"] == "Ready for payroll."
    assert history.rows[-1]["to_status"] == "Sent"
    assert len(history.rows) == 3


def test_payment_settlement_pays_approved_trip_ta_and_locks_the_trip() -> None:
    service, history = _service()
    history.review_counts = lambda employee_ids, _start, _end: {employee_id: (0, 1, 0, 0) for employee_id in employee_ids}  # type: ignore[method-assign]
    history.approved_trip_ids = lambda _employee_ids, _start, _end: [10]  # type: ignore[method-assign]
    history.settlement_trips = lambda employee_ids, _start, _end: [  # type: ignore[method-assign]
        {
            "id": 10,
            "employee_id": employee_ids[0],
            "vehicle_type": "Own bike",
            "status": "Completed",
            "is_distance_adjusted": False,
            "adjusted_distance_km": None,
            "map_distance_km": None,
            "gps_distance_km": Decimal("20"),
        }
    ]
    history.latest_trip_decisions = lambda trip_ids: {trip_id: "Approved" for trip_id in trip_ids}  # type: ignore[method-assign]
    service.rates = lambda: type("Rates", (), {"bike_per_km": Decimal("2.50"), "car_per_km": Decimal("5.00")})()  # type: ignore[method-assign]
    actor = make_user(id=9, permissions=frozenset({"core.employee.manage"}))
    paid = service.settle_payment(
        TadaSettlementCreate(
            payroll_month="2026-11",
            employee_ids=[5],
            payment_date=date(2026, 11, 7),
            payment_mode="Bank transfer",
            payment_reference="UTR123",
            remarks="November TA",
        ),
        actor,
    )
    assert paid.updated == 1
    assert paid.skipped == []
    assert history.trip_rows[-1]["to_status"] == "Sent"
    assert history.rows[-1]["to_status"] == "Paid"
    assert history.rows[-1]["remarks"] == (
        "Paid amount: ₹50.00 | Payment date: 2026-11-07 | Payment mode: Bank transfer | "
        "Payment reference: UTR123 | November TA"
    )


def test_pending_trips_block_payment_settlement() -> None:
    service, history = _service()
    history.review_counts = lambda employee_ids, _start, _end: {employee_id: (1, 1, 0, 0) for employee_id in employee_ids}  # type: ignore[method-assign]
    result = service.settle_payment(
        TadaSettlementCreate(
            payroll_month="2026-11",
            employee_ids=[5],
            payment_date=date(2026, 11, 7),
            payment_mode="Cash",
        ),
        make_user(),
    )
    assert result.updated == 0
    assert "pending" in result.skipped[0].reason.lower()
    assert history.rows == []


def test_bank_payment_requires_a_reference() -> None:
    with pytest.raises(ValidationError, match="payment reference"):
        TadaSettlementCreate(
            payroll_month="2026-11",
            employee_ids=[5],
            payment_date=date(2026, 11, 7),
            payment_mode="Bank transfer",
        )


def test_service_rejects_a_blank_reason() -> None:
    service, history = _service()
    with pytest.raises(InvalidDecision):
        service.decide(
            TadaDecisionCreate.model_construct(
                payroll_month="2026-11", employee_ids=[5], decision="Rejected", remarks=None
            ),
            make_user(),
        )
    assert history.rows == []


def test_unsigned_user_cannot_decide(client: TestClient) -> None:
    response = client.post(
        "/api/v1/hr/tada/decisions",
        json={"payrollMonth": "2026-11", "employeeIds": [5], "decision": "Approved", "remarks": "ok"},
    )
    assert response.status_code == 401


def test_user_without_hr_permission_cannot_decide(api: FastAPI, client: TestClient) -> None:
    from trishul_api.auth import get_current_user

    api.dependency_overrides[get_current_user] = lambda: make_user(permissions=frozenset({"core.employee.view"}))
    response = client.post(
        "/api/v1/hr/tada/decisions",
        headers={"Authorization": "Bearer x"},
        json={"payrollMonth": "2026-11", "employeeIds": [5], "decision": "Rejected", "remarks": "No trips"},
    )
    assert response.status_code == 403


class _OneTrip:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = row
        self.recorded: list[dict[str, object]] = []
        self.status = "Pending"

    def get_row(self, trip_id: int) -> dict[str, object] | None:
        return self.row if trip_id == int(self.row["id"]) else None

    def latest_trip_decisions(self, trip_ids: list[int]) -> dict[int, str]:
        return {trip_id: self.status for trip_id in trip_ids if trip_id == int(self.row["id"])}

    def trip_documents(self, _row: dict[str, object]) -> list[dict[str, object]]:
        return []

    def record_trip_decision(self, **row: object) -> None:
        self.recorded.append(row)
        self.status = str(row["to_status"])

    def commit(self) -> None:
        return None


def test_one_trip_approval_does_not_record_another_trip() -> None:
    repo = _OneTrip({"id": 10, "status": "Completed", "vehicle_type": "Own bike"})
    service = TadaService.__new__(TadaService)
    service._trips = repo
    service.trip = lambda trip_id: trip_id  # type: ignore[method-assign]
    service.decide_trip(10, TadaTripDecisionCreate(decision="Approved", remarks="GPS checked"), make_user(id=9))
    assert repo.recorded[0]["trip_id"] == 10
    assert all(row["trip_id"] != 11 for row in repo.recorded)


def test_public_transport_without_a_ticket_cannot_be_approved() -> None:
    repo = _OneTrip({"id": 20, "status": "Completed", "vehicle_type": "Public transport"})
    service = TadaService.__new__(TadaService)
    service._trips = repo
    with pytest.raises(InvalidDecision, match="uploaded ticket"):
        service.decide_trip(20, TadaTripDecisionCreate(decision="Approved"), make_user(id=9))
    assert repo.recorded == []


def test_public_transport_without_a_ticket_can_be_approved_with_a_document_exception() -> None:
    repo = _OneTrip({"id": 20, "status": "Completed", "vehicle_type": "Public transport"})
    service = TadaService.__new__(TadaService)
    service._trips = repo
    service.trip = lambda trip_id: trip_id  # type: ignore[method-assign]
    remarks = "Approved amount: ₹50.00. Document: Employee unable to provide ticket/receipt"
    service.decide_trip(20, TadaTripDecisionCreate(decision="Approved", remarks=remarks), make_user(id=9))
    assert repo.recorded[0]["to_status"] == "Approved"
    assert repo.recorded[0]["remarks"] == remarks


def test_an_approved_trip_cannot_be_rejected_again() -> None:
    repo = _OneTrip({"id": 10, "status": "Completed", "vehicle_type": "Own bike"})
    repo.status = "Approved"
    service = TadaService.__new__(TadaService)
    service._trips = repo
    with pytest.raises(InvalidDecision, match="Already approved"):
        service.decide_trip(10, TadaTripDecisionCreate(decision="Rejected", remarks="Too late"), make_user(id=9))
    assert repo.recorded == []


def test_history_names_the_actor() -> None:
    from trishul_api.modules.hr.tada.service import _person_name

    assert _person_name("Satyajit", "Tung", "satyajit") == "Satyajit Tung"
    assert _person_name(None, None, "hr.admin") == "hr.admin"
    changed = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
    assert changed.tzinfo is UTC
