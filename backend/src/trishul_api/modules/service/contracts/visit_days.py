"""ASC visits counted by day: one day uses one visit of the ASC, however many engineers went, how many
times, or for how many of its service calls.

An engineer "reaches the site" when their trip to the call ends (trk.handlers sets
svc.service_visit.service_started_at); that moment calls count_visit_day. The day is the India date.
Each call's day is a svc.contract_visit_day row, the history the ASC page shows. Only the ASC's first row
of a day uses a visit: that call's total in svc.contract_visit and the contract's visits_used go up by one,
and the ASC Manager can still correct a call's count by hand afterwards. Other calls of the ASC on that
day are listed as "same day" and use nothing. Counting never refuses a visit: the engineer already went,
so an ASC can go past its visits_included (the remaining count shows 0).
"""

import datetime as dt
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.db.models import (
    ContractVisit,
    ContractVisitDay,
    Employee,
    ServiceCall,
    ServiceContract,
    ServiceVisit,
)
from trishul_api.modules.service.contracts.repository import ASC, ContractRepository
from trishul_api.modules.service.contracts.schemas import AscVisitDay, AscVisitEngineer

IST_OFFSET = dt.timedelta(hours=5, minutes=30)
"""India has no daylight saving: its date is UTC + 5:30."""


def india_date(utc: dt.datetime) -> dt.date:
    """The India date of a naive UTC time (as the database stores them)."""
    return (utc + IST_OFFSET).date()


def count_visit_day(db: Session, visit: ServiceVisit, user_id: int | None) -> None:
    """Count the day of this site visit on the call's ASC, unless that day is already counted or the call
    has no ASC on that day. Never raises: reaching site must not fail over ASC bookkeeping."""
    if visit.service_started_at is None:
        return
    call = db.get(ServiceCall, visit.service_call_id)
    if call is None or not call.is_active:
        return
    day = india_date(visit.service_started_at)
    counted = db.scalar(
        select(ContractVisitDay.id).where(
            ContractVisitDay.service_call_id == call.id, ContractVisitDay.visit_date == day
        )
    )
    if counted is not None:
        return
    record = db.scalar(select(ContractVisit).where(ContractVisit.service_call_id == call.id))
    contract_id = record.service_contract_id if record is not None else _contract_on(db, call, day)
    if contract_id is None or not _live(db, contract_id):
        return

    # Held until commit, so two calls of the ASC reaching site together can't both take the day's visit.
    ContractRepository(db).lock(contract_id)
    day_used = (
        db.scalar(
            select(ContractVisitDay.id).where(
                ContractVisitDay.service_contract_id == contract_id, ContractVisitDay.visit_date == day
            )
        )
        is not None
    )

    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        with db.begin_nested():
            db.add(
                ContractVisitDay(
                    service_contract_id=contract_id,
                    service_call_id=call.id,
                    visit_date=day,
                    created_at=now,
                    created_by_user_id=user_id,
                )
            )
            db.flush()
    except IntegrityError:
        return  # another engineer on the call counted this day at the same moment
    if day_used:
        return  # another call of this ASC already used the day's visit

    if record is None:
        db.add(
            ContractVisit(
                service_contract_id=contract_id,
                service_call_id=call.id,
                visits=1,
                created_at=now,
                created_by_user_id=user_id,
            )
        )
    else:
        record.visits += 1
        record.updated_at = now
        record.updated_by_user_id = user_id
    db.execute(
        update(ServiceContract)
        .where(ServiceContract.id == contract_id)
        .values(visits_used=ServiceContract.visits_used + 1, updated_at=now, updated_by_user_id=user_id)
        .execution_options(synchronize_session=False)
    )


def _contract_on(db: Session, call: ServiceCall, day: dt.date) -> int | None:
    """The call's own ASC if it runs on that day. A call not linked to an ASC uses the ASC that covered its
    machine when the call was logged (it came in before the ASC reached Trishul), as the ASC's call list
    does; a call logged before the ASC started isn't an ASC call."""
    if call.service_contract_id is not None:
        contract = db.get(ServiceContract, call.service_contract_id)
        if contract is not None and contract.contract_type == ASC and contract.start_date <= day <= contract.end_date:
            return contract.id
        return None
    if call.machine_unit_id is None:
        return None
    contract_id = ContractRepository(db).active_contract_id(call.machine_unit_id, call.received_at.date())
    contract = db.get(ServiceContract, contract_id) if contract_id is not None else None
    return contract.id if contract is not None and contract.start_date <= day <= contract.end_date else None


def _live(db: Session, contract_id: int) -> bool:
    contract = db.get(ServiceContract, contract_id)
    return contract is not None and contract.is_active and contract.status != "Cancelled"


def visit_days(db: Session, contract_id: int) -> list[AscVisitDay]:
    """The ASC's visit days, newest first, each with the engineers who reached the site that day. The day's
    first call uses the visit; any other call of the ASC that day is marked as the same day."""
    rows = db.execute(
        select(
            ContractVisitDay.id,
            ContractVisitDay.visit_date,
            ContractVisitDay.service_call_id,
            ServiceCall.call_no,
            ServiceCall.current_status,
            ServiceCall.complaint_description,
            ContractVisitDay.created_at,
        )
        .join(ServiceCall, ServiceCall.id == ContractVisitDay.service_call_id)
        .where(ContractVisitDay.service_contract_id == contract_id)
        .order_by(ContractVisitDay.visit_date.desc(), ContractVisitDay.id.desc())
    ).all()
    if not rows:
        return []
    first_of_day: dict[dt.date, int] = {}
    for row in rows:
        first_of_day[row.visit_date] = min(row.id, first_of_day.get(row.visit_date, row.id))

    # Who was on site, per call and India day. The visits of those calls are few, so they are read
    # whole and grouped here rather than converting time zones in SQL.
    call_ids = sorted({row.service_call_id for row in rows})
    name = func.concat_ws(" ", Employee.first_name, Employee.last_name)
    on_site: dict[tuple[int, dt.date], dict[int, AscVisitEngineer]] = defaultdict(dict)
    for visit in db.execute(
        select(
            ServiceVisit.service_call_id,
            ServiceVisit.engineer_employee_id,
            name.label("name"),
            Employee.employee_code,
            ServiceVisit.service_started_at,
            ServiceVisit.service_ended_at,
        )
        .join(Employee, Employee.id == ServiceVisit.engineer_employee_id)
        .where(
            ServiceVisit.service_call_id.in_(call_ids),
            ServiceVisit.is_active,
            ServiceVisit.service_started_at.is_not(None),
        )
        .order_by(ServiceVisit.service_started_at)
    ):
        key = (visit.service_call_id, india_date(visit.service_started_at))
        # An engineer who reached the site twice that day is listed once, at the first arrival.
        on_site[key].setdefault(
            visit.engineer_employee_id,
            AscVisitEngineer(
                employee_id=visit.engineer_employee_id,
                name=visit.name,
                employee_code=visit.employee_code,
                reached_at=visit.service_started_at,
                left_at=visit.service_ended_at,
            ),
        )
    return [
        AscVisitDay(
            visit_date=row.visit_date,
            service_call_id=row.service_call_id,
            call_no=row.call_no,
            call_status=row.current_status,
            complaint_description=row.complaint_description,
            counted_at=row.created_at,
            uses_visit=first_of_day[row.visit_date] == row.id,
            engineers=list(on_site.get((row.service_call_id, row.visit_date), {}).values()),
        )
        for row in rows
    ]
