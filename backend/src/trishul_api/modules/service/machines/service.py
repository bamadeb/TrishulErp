"""Machine management (core.machine_unit): list, view, add, update and activate/deactivate.

Every machine is linked to the customer who owns it; a service call may only name a machine of its own
customer (checked in the service-call service). The brand is taken from the machine model. A change of
owner is also kept in core.machine_ownership, so the machine's history of owners is not lost.

Serial number is unique across all machines (UX_core_machine_unit_serial_number); this checks it up front
for a clear error and still catches a concurrent duplicate on commit. A deactivated machine can no longer
be picked for a new call, but the calls already logged against it still show it.
"""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import MachineOwnership, MachineUnit
from trishul_api.modules.service.machines.repository import MachineRepository
from trishul_api.modules.service.machines.schemas import MachineCreate, MachineDetail, MachineUpdate

_DUPLICATE = "Another machine already has this serial number."
# Fields copied straight from the request to the row (serial, model and owner are handled separately).
_PLAIN_FIELDS = (
    "status",
    "engine_number",
    "registration_number",
    "year_of_manufacture",
    "sale_date",
    "commissioning_date",
    "warranty_start_date",
    "warranty_end_date",
    "oem_registered_product_id",
)


class MachineService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor
        self._repo = MachineRepository(db)

    def get(self, machine_id: int) -> MachineDetail:
        self._require(machine_id)
        return self._detail(machine_id)

    def create(self, data: MachineCreate) -> MachineDetail:
        serial = data.serial_number.strip()
        self._check_unique_serial(serial, None)
        principal_id = self._check_model(data.model_id)
        self._check_customer(data.customer_id)

        machine = MachineUnit(
            serial_number=serial,
            model_id=data.model_id,
            principal_id=principal_id,
            customer_id=data.customer_id,
            created_by_user_id=self._actor.id,
            **{field: getattr(data, field) for field in _PLAIN_FIELDS},
        )
        self._repo.add(machine)
        new_id = self._save(machine, owner_changed=True)
        return self._detail(new_id)

    def update(self, machine_id: int, expected_row_version: bytes, data: MachineUpdate) -> MachineDetail:
        machine = self._require(machine_id)
        check_row_version(machine.row_version, expected_row_version)
        changed = data.model_fields_set

        if "serial_number" in changed:
            if not data.serial_number:
                raise ApiError("A serial number is required.", errors={"serialNumber": ["Required."]})
            serial = data.serial_number.strip()
            self._check_unique_serial(serial, machine.id)
            machine.serial_number = serial
        if "model_id" in changed:
            if data.model_id is None:
                raise ApiError("A model is required.", errors={"modelId": ["Required."]})
            machine.principal_id = self._check_model(data.model_id)
            machine.model_id = data.model_id
        owner_changed = False
        if "customer_id" in changed:
            if data.customer_id is None:
                raise ApiError("A machine must stay linked to a customer.", errors={"customerId": ["Required."]})
            if data.customer_id != machine.customer_id:
                self._check_customer(data.customer_id)
                machine.customer_id = data.customer_id
                owner_changed = True
        for field in _PLAIN_FIELDS:
            if field in changed:
                if field == "status" and data.status is None:
                    continue
                setattr(machine, field, getattr(data, field))

        self._touch(machine)
        self._save(machine, owner_changed=owner_changed)
        return self._detail(machine_id)

    def deactivate(self, machine_id: int) -> MachineDetail:
        machine = self._require(machine_id)
        if machine.is_active:
            machine.is_active = False
            self._touch(machine)
            self._db.commit()
        return self._detail(machine_id)

    def activate(self, machine_id: int) -> MachineDetail:
        machine = self._require(machine_id)
        if not machine.is_active:
            machine.is_active = True
            self._touch(machine)
            self._db.commit()
        return self._detail(machine_id)

    # ------------------------------------------------------------------ helpers

    def _require(self, machine_id: int) -> MachineUnit:
        machine = self._repo.get(machine_id)
        if machine is None:
            raise NotFound("Machine not found.")
        return machine

    def _detail(self, machine_id: int) -> MachineDetail:
        return MachineDetail.model_validate(self._repo.detail_row(machine_id))

    def _save(self, machine: MachineUnit, *, owner_changed: bool) -> int:
        try:
            self._repo.flush()
            machine_id = machine.id
            if owner_changed and machine.customer_id is not None:
                self._record_owner(machine_id, machine.customer_id)
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(_DUPLICATE) from error
        return machine_id

    def _record_owner(self, machine_id: int, customer_id: int) -> None:
        """Close the current ownership (if any) and open one for the new owner from today."""
        today = date.today()
        current = self._db.scalars(
            select(MachineOwnership).where(
                MachineOwnership.machine_unit_id == machine_id,
                MachineOwnership.to_date.is_(None),
                MachineOwnership.is_active,
            )
        ).all()
        for row in current:
            row.to_date = today
            row.updated_at = _now()
            row.updated_by_user_id = self._actor.id
        self._repo.add(
            MachineOwnership(
                machine_unit_id=machine_id,
                customer_id=customer_id,
                from_date=today,
                created_by_user_id=self._actor.id,
            )
        )

    def _check_unique_serial(self, serial: str, machine_id: int | None) -> None:
        owner = self._repo.serial_owner(serial)
        if owner is not None and owner != machine_id:
            raise AlreadyExists(f"Serial number '{serial}' is already registered.")

    def _check_model(self, model_id: int) -> int:
        """The model's brand, after checking the model exists and the user may use that brand."""
        model = self._repo.active_model(model_id)
        if model is None:
            raise ApiError("That model doesn't exist.", errors={"modelId": [f"Unknown or inactive model {model_id}"]})
        if not self._actor.can_see_principal(model.principal_id):
            raise ApiError("You do not have access to that brand.", errors={"modelId": ["Not one of your brands."]})
        return model.principal_id

    def _check_customer(self, customer_id: int) -> None:
        if not self._repo.active_customer(customer_id):
            raise ApiError(
                "That customer doesn't exist.", errors={"customerId": [f"Unknown or inactive customer {customer_id}"]}
            )

    def _touch(self, machine: MachineUnit) -> None:
        machine.updated_at = _now()
        machine.updated_by_user_id = self._actor.id


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
