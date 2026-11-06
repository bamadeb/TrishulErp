"""Warehouses and which branch each one supplies, on core.branch.

A warehouse is a branch of type Warehouse; a branch points at its supplying warehouse through
parent_warehouse_id. A warehouse can itself be a branch. Warehouses and the head office have no supplier.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import Branch
from trishul_api.modules.core.warehouses.schemas import (
    BranchWarehouseUpdate,
    WarehouseBranch,
    WarehouseCreate,
    WarehouseMap,
    WarehouseOut,
    WarehouseUpdate,
)

SUPPLIED_TYPES = ("Branch", "Service point")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class WarehouseService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    def overview(self) -> WarehouseMap:
        # Fully fetch each result before the next query: SQL Server allows one open result per connection.
        warehouses = self._db.scalars(
            select(Branch).where(Branch.branch_type == "Warehouse").order_by(Branch.name)
        ).all()
        branches = self._db.scalars(
            select(Branch).where(Branch.branch_type.in_(SUPPLIED_TYPES)).order_by(Branch.name)
        ).all()
        counts = dict(
            self._db.execute(
                select(Branch.parent_warehouse_id, func.count(Branch.id))
                .where(Branch.parent_warehouse_id.is_not(None), Branch.is_active)
                .group_by(Branch.parent_warehouse_id)
            )
            .all()
        )
        return WarehouseMap(
            warehouses=[self._out(w, counts.get(w.id, 0)) for w in warehouses],
            branches=[self._branch(b) for b in branches],
        )

    def create(self, data: WarehouseCreate) -> WarehouseOut:
        code = data.code.strip()
        self._check_code(code, None)
        owner = (
            self._db.scalars(
                select(Branch).where(Branch.branch_type == "Head office").order_by(Branch.id).limit(1)
            ).first()
            or self._db.scalars(select(Branch).order_by(Branch.id).limit(1)).first()
        )
        if owner is None:
            raise ApiError("There is no head office or branch to take the company and state from.")
        row = Branch(
            company_id=owner.company_id,
            state_id=owner.state_id,
            code=code,
            name=data.name.strip(),
            branch_type="Warehouse",
            created_by_user_id=self._actor.id,
        )
        self._save(row)
        return self._out(row, self._supplied(row.id))

    def update(self, warehouse_id: int, expected: bytes, data: WarehouseUpdate) -> WarehouseOut:
        row = self._warehouse(warehouse_id)
        check_row_version(row.row_version, expected)
        if data.code is not None and data.code.strip() != row.code:
            self._check_code(data.code.strip(), row.id)
            row.code = data.code.strip()
        if data.name is not None:
            row.name = data.name.strip()
        if data.is_active is not None:
            if not data.is_active and self._supplied(row.id):
                raise ApiError(
                    "This warehouse still supplies active branches. Move them to another warehouse first.",
                    errors={"isActive": ["Move its branches first."]},
                )
            row.is_active = data.is_active
        self._touch(row)
        self._save(row)
        return self._out(row, self._supplied(row.id))

    def assign_branch(self, branch_id: int, expected: bytes, data: BranchWarehouseUpdate) -> WarehouseBranch:
        row = self._db.get(Branch, branch_id)
        if row is None or row.branch_type not in SUPPLIED_TYPES:
            raise NotFound("Branch not found.")
        check_row_version(row.row_version, expected)
        if data.warehouse_id is not None:
            target = self._db.get(Branch, data.warehouse_id)
            if target is None or target.branch_type != "Warehouse" or not target.is_active:
                raise ApiError(
                    "Choose an active warehouse.",
                    errors={"warehouseId": [f"Location {data.warehouse_id} is not an active warehouse."]},
                )
        row.parent_warehouse_id = data.warehouse_id
        row.region_id = None  # regions are not used: the warehouse is the only grouping
        self._touch(row)
        self._save(row)
        return self._branch(row)

    def _warehouse(self, warehouse_id: int) -> Branch:
        row = self._db.get(Branch, warehouse_id)
        if row is None or row.branch_type != "Warehouse":
            raise NotFound("Warehouse not found.")
        return row

    def _check_code(self, code: str, own_id: int | None) -> None:
        query = select(Branch.id).where(Branch.code == code)
        if own_id is not None:
            query = query.where(Branch.id != own_id)
        if self._db.scalar(query.limit(1)) is not None:
            raise AlreadyExists(f"Code '{code}' is already used by a branch or warehouse.")

    def _supplied(self, warehouse_id: int) -> int:
        return int(
            self._db.scalar(
                select(func.count(Branch.id)).where(Branch.parent_warehouse_id == warehouse_id, Branch.is_active)
            )
            or 0
        )

    def _touch(self, row: Branch) -> None:
        row.updated_at = _now()
        row.updated_by_user_id = self._actor.id

    def _save(self, row: Branch) -> None:
        self._db.add(row)
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("The change could not be saved. The code may already be in use.") from error
        self._db.refresh(row)

    @staticmethod
    def _out(row: Branch, branch_count: int) -> WarehouseOut:
        return WarehouseOut(
            id=row.id,
            code=row.code,
            name=row.name,
            is_active=row.is_active,
            branch_count=branch_count,
            row_version=row.row_version,
        )

    @staticmethod
    def _branch(row: Branch) -> WarehouseBranch:
        return WarehouseBranch(
            id=row.id,
            code=row.code,
            name=row.name,
            branch_type=row.branch_type,
            warehouse_id=row.parent_warehouse_id,
            is_active=row.is_active,
            row_version=row.row_version,
        )
