"""Comp Off authorization, credit, FEFO consumption, cancellation, expiry, and duplicates."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.common.errors import AlreadyExists, ApiError, Forbidden
from trishul_api.db.models import (
    Attendance,
    CompOffCredit,
    CompOffLedger,
    LeaveBalance,
    Notification,
)
from trishul_api.modules.hr.leave.comp_off_ops import (
    EXPIRY_DAYS,
    assert_available,
    authorize,
    available_on,
    certify_holiday_work,
    consume,
    credit_days_for,
    expire_due,
    reject_holiday_pay,
    restore,
)
from trishul_api.modules.hr.leave.mine_repository import LeaveRuleError

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = [
    "core.company",
    "core.branch",
    "core.employee",
    "core.app_user",
    "core.notification",
    "hr.leave_type",
    "hr.leave_balance",
    "hr.leave_balance_transaction",
    "hr.holiday",
    "hr.shift",
    "hr.employee_shift",
    "hr.attendance",
    "hr.comp_off_authorization",
    "hr.comp_off_credit",
    "hr.comp_off_ledger",
]

MANAGER = make_user(
    id=7,
    employee_id=7,
    permissions=frozenset({"hr.attendance.view.team", "hr.leave.approve"}),
)
EMPLOYEE = make_user(id=10, employee_id=10, permissions=frozenset({"hr.attendance.mark", "hr.leave.view"}))
SUNDAY = date(2026, 11, 22)
EARLIER_SUNDAY = date(2026, 11, 15)
WEDNESDAY = date(2026, 11, 25)


def test_rejection_does_not_touch_comp_off_credits() -> None:
    import inspect

    from trishul_api.modules.hr.leave.request_ops import LeaveRequestRepository

    source = inspect.getsource(LeaveRequestRepository.reject)
    assert "consume" not in source
    assert "_deduct" not in source


def test_hours_decide_a_full_day_or_a_half_day() -> None:
    assert credit_days_for(Decimal("8"), Decimal("4")) == Decimal("1.0")
    assert credit_days_for(Decimal("4"), Decimal("4")) == Decimal("0.5")
    with pytest.raises(LeaveRuleError):
        credit_days_for(Decimal("3.5"), Decimal("4"))


def test_missing_punches_are_not_credited() -> None:
    attendance = Attendance(employee_id=10, attendance_date=SUNDAY, source="Manual", status="Present")
    with pytest.raises(LeaveRuleError, match="punches"):
        from trishul_api.modules.hr.leave.comp_off_ops import worked_hours_of

        worked_hours_of(attendance)


def test_holiday_pay_is_rejected() -> None:
    with pytest.raises(ApiError, match="Holiday Pay"):
        reject_holiday_pay("Please pay Holiday Pay for this shift.")


def test_authorize_certify_consume_cancel_and_expire() -> None:
    engine = sqlite_engine(TABLES)
    _seed(engine)
    with Session(engine) as db:
        with pytest.raises(ApiError, match="weekly off"):
            authorize(db, MANAGER, employee_id=10, employee_code=None, work_date=WEDNESDAY, remarks=None)
        with pytest.raises(Forbidden):
            authorize(db, EMPLOYEE, employee_id=10, employee_code=None, work_date=SUNDAY, remarks=None)

        first = authorize(db, MANAGER, employee_id=10, employee_code=None, work_date=SUNDAY, remarks="Client support")
        assert first.day_kind == "WEEKLY_OFF" and first.status == "Authorized"
        with pytest.raises(AlreadyExists):
            authorize(db, MANAGER, employee_id=10, employee_code=None, work_date=SUNDAY, remarks=None)

        company = authorize(
            db, MANAGER, employee_id=10, employee_code=None, work_date=date(2026, 12, 25), remarks=None
        )
        assert company.day_kind == "COMPANY_HOLIDAY"
        declared = authorize(
            db, MANAGER, employee_id=10, employee_code=None, work_date=date(2026, 1, 26), remarks=None
        )
        assert declared.day_kind == "NON_WORKING"
        with pytest.raises(ApiError, match="weekly off"):
            authorize(db, MANAGER, employee_id=10, employee_code=None, work_date=date(2026, 11, 4), remarks=None)

        worked = Attendance(
            employee_id=10,
            attendance_date=SUNDAY,
            source="Manual",
            status="Present",
            check_in_at=datetime(2026, 11, 22, 9, 0),
            check_out_at=datetime(2026, 11, 22, 18, 0),
            worked_hours=Decimal("9.00"),
            is_active=True,
        )
        db.add(worked)
        db.flush()
        credit = certify_holiday_work(
            db, MANAGER, employee_id=10, work_date=SUNDAY, attendance=worked,
            regularization_id=41, half_day_hours=Decimal("4"),
        )
        assert credit.days == Decimal("1.0")
        assert credit.expires_on == credit.credited_on + timedelta(days=EXPIRY_DAYS)
        with pytest.raises(AlreadyExists):
            certify_holiday_work(
                db, MANAGER, employee_id=10, work_date=SUNDAY, attendance=worked,
                regularization_id=41, half_day_hours=Decimal("4"),
            )

        second_auth = authorize(
            db, MANAGER, employee_id=10, employee_code=None, work_date=EARLIER_SUNDAY, remarks=None
        )
        short = Attendance(
            employee_id=10,
            attendance_date=EARLIER_SUNDAY,
            source="Manual",
            status="Half day",
            worked_hours=Decimal("5.00"),
            check_in_at=datetime(2026, 11, 15, 9, 0),
            check_out_at=datetime(2026, 11, 15, 14, 0),
            is_active=True,
        )
        db.add(short)
        db.flush()
        half = certify_holiday_work(
            db, MANAGER, employee_id=10, work_date=EARLIER_SUNDAY, attendance=short,
            regularization_id=42, half_day_hours=Decimal("4"),
        )
        assert half.days == Decimal("0.5")
        assert second_auth.status == "Certified"
        credit.expires_on = date.today() + timedelta(days=10)
        half.expires_on = date.today() + timedelta(days=40)
        db.commit()

        assert available_on(db, 10, date.today()) == Decimal("1.5")
        with pytest.raises(LeaveRuleError, match="Insufficient"):
            assert_available(db, 10, 3, date.today(), Decimal("2.0"), Decimal("0"))
        with pytest.raises(LeaveRuleError, match="Insufficient"):
            assert_available(db, 10, 3, date.today(), Decimal("0.6"), Decimal("1.0"))

        consume(db, employee_id=10, leave_type_id=3, leave_request_id=90, start=date.today(), days=Decimal("1.2"), user_id=7)
        db.commit()
        soon = db.get(CompOffCredit, credit.id)
        later = db.get(CompOffCredit, half.id)
        assert soon is not None and later is not None
        assert soon.consumed_days == Decimal("1.0") and soon.status == "Exhausted"
        assert later.consumed_days == Decimal("0.2") and remaining_of(later) == Decimal("0.3")
        balance = _closing(db)
        assert balance == Decimal("0.3")

        restore(db, employee_id=10, leave_type_id=3, leave_request_id=90, user_id=7)
        db.commit()
        assert available_on(db, 10, date.today()) == Decimal("1.5")
        restore(db, employee_id=10, leave_type_id=3, leave_request_id=90, user_id=7)
        db.commit()
        assert available_on(db, 10, date.today()) == Decimal("1.5")

        soon = db.get(CompOffCredit, credit.id)
        later = db.get(CompOffCredit, half.id)
        assert soon is not None and later is not None
        soon.expires_on = date.today() - timedelta(days=1)
        later.expires_on = date.today()
        soon.status = "Open"
        later.status = "Open"
        db.commit()
        assert expire_due(db, employee_id=10, as_of=date.today()) == 2
        assert available_on(db, 10, date.today()) == Decimal("0.0")
        with pytest.raises(LeaveRuleError, match="Insufficient"):
            assert_available(db, 10, 3, date.today(), Decimal("0.5"), Decimal("0"))
        note = db.scalars(select(Notification)).one()
        assert "Comp Off expired" in (note.payload or "")
        kinds = [row.kind for row in db.scalars(select(CompOffLedger).order_by(CompOffLedger.id)).all()]
        assert kinds.count("Credit") == 2
        assert kinds.count("Consumption") == 2
        assert kinds.count("Reversal") == 2
        assert kinds.count("Expiry") == 2


def remaining_of(credit: CompOffCredit) -> Decimal:
    return (credit.days - credit.consumed_days - credit.expired_days).quantize(Decimal("0.1"))


def _closing(db: Session) -> Decimal:
    row = db.scalars(select(LeaveBalance).where(LeaveBalance.employee_id == 10, LeaveBalance.leave_type_id == 3)).one()
    return Decimal(row.closing).quantize(Decimal("0.1"))


def _seed(engine) -> None:
    insert_row(engine, "core.company", id=1, code="TRI", legal_name="Trishul")
    insert_row(engine, "core.branch", id=1, company_id=1, code="HO", name="Head Office", branch_type="Head office", state_id=1)
    insert_row(
        engine, "core.employee", id=7, company_id=1, branch_id=1, employee_code="EMP007",
        first_name="Rahul", last_name="Patil", employee_type="Permanent", status="Active",
    )
    insert_row(
        engine, "core.employee", id=10, company_id=1, branch_id=1, employee_code="EMP017",
        first_name="Prajna", last_name="Ghadei", employee_type="Permanent", status="Active",
        reporting_manager_id=7,
    )
    insert_row(engine, "core.app_user", id=10, employee_id=10, username="prajna", cognito_sub="sub-prajna")
    insert_row(engine, "hr.leave_type", id=3, code="CO", name="Compensatory Off", is_paid=True, is_active=True)
    insert_row(
        engine, "hr.holiday", id=1, holiday_date=date(2026, 12, 25), name="Company Foundation Day",
        holiday_type="Festival", is_active=True,
    )
    insert_row(
        engine, "hr.holiday", id=2, holiday_date=date(2026, 1, 26), name="Republic Day",
        holiday_type="National", is_active=True,
    )
    insert_row(
        engine, "hr.holiday", id=3, holiday_date=date(2026, 11, 4), name="Optional Festival",
        holiday_type="Optional", is_active=True,
    )
