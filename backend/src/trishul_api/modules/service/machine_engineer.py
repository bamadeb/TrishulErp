"""The service engineer attached to a machine (svc.machine_engineer), and the default assignment it gives.

A new service call on a machine with an engineer attached goes to that engineer as the lead, whether the
office logs it or it comes from the BYD import (when BYD names no engineer Trishul knows). An engineer who
is no longer active is ignored, so the call stays unassigned for the team lead. Changing the machine's
engineer later doesn't move calls already logged.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.db.models import Employee, MachineEngineer, ServiceCall
from trishul_api.modules.service.assignment import set_engineers


def machine_engineer_id(db: Session, machine_id: int | None) -> int | None:
    """The active engineer attached to the machine, or None."""
    if machine_id is None:
        return None
    return db.scalar(
        select(MachineEngineer.engineer_employee_id)
        .join(Employee, Employee.id == MachineEngineer.engineer_employee_id)
        .where(MachineEngineer.machine_unit_id == machine_id, Employee.is_active)
    )


def set_machine_engineer(db: Session, machine_id: int, engineer_id: int | None, user_id: int, now: datetime) -> None:
    """Attach the engineer to the machine, replacing any other; None takes the engineer off."""
    row = db.scalar(select(MachineEngineer).where(MachineEngineer.machine_unit_id == machine_id))
    if engineer_id is None:
        if row is not None:
            db.delete(row)
        return
    if row is None:
        db.add(
            MachineEngineer(
                machine_unit_id=machine_id, engineer_employee_id=engineer_id, created_at=now, created_by_user_id=user_id
            )
        )
    elif row.engineer_employee_id != engineer_id:
        row.engineer_employee_id = engineer_id
        row.updated_at = now
        row.updated_by_user_id = user_id


def assign_machine_engineer(db: Session, call: ServiceCall, user_id: int, now: datetime) -> bool:
    """Make the machine's engineer the lead of a call that has none yet (a Logged call becomes Assigned).
    True when it did. The call must be flushed (it needs its id)."""
    if call.assigned_engineer_id is not None:
        return False
    engineer_id = machine_engineer_id(db, call.machine_unit_id)
    if engineer_id is None:
        return False
    set_engineers(db, call, engineer_id, (), user_id, now)
    if call.current_status == "Logged":
        call.current_status = "Assigned"
    return True
