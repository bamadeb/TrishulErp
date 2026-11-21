"""Persistence for biometric devices, mappings, punches and sync logs."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, NamedTuple

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.db.models.biometric import (
    BiometricDevice,
    BiometricEmployeeMapping,
    BiometricPunchLog,
    BiometricSyncLog,
)
from trishul_api.db.models.generated.core import Branch, Employee
from trishul_api.db.models.generated.hr import Department


class MappingRow(NamedTuple):
    mapping: BiometricEmployeeMapping
    employee_code: str | None
    employee_name: str | None
    department_name: str | None
    branch_name: str | None
    device_name: str | None


class PunchRow(NamedTuple):
    punch: BiometricPunchLog
    employee_code: str | None
    employee_name: str | None
    department_name: str | None
    device_name: str | None
    device_location: str | None


class SyncRow(NamedTuple):
    sync: BiometricSyncLog
    device_name: str | None
    device_code: str | None


class BiometricRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, obj: object) -> None:
        self._session.add(obj)

    def flush(self) -> None:
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def get_device(self, device_id: int) -> BiometricDevice | None:
        return self._session.get(BiometricDevice, device_id)

    def get_device_by_code(self, code: str) -> BiometricDevice | None:
        return self._session.scalar(select(BiometricDevice).where(BiometricDevice.code == code))

    def get_mapping(self, mapping_id: int) -> BiometricEmployeeMapping | None:
        return self._session.get(BiometricEmployeeMapping, mapping_id)

    def list_devices(self, *, active_only: bool = False) -> list[BiometricDevice]:
        statement = select(BiometricDevice).order_by(BiometricDevice.code)
        if active_only:
            statement = statement.where(BiometricDevice.is_active == True)  # noqa: E712
        return list(self._session.scalars(statement).all())

    def list_sync_enabled_devices(self, device_id: int | None = None) -> list[BiometricDevice]:
        statement = select(BiometricDevice).where(
            BiometricDevice.is_active == True,  # noqa: E712
            BiometricDevice.is_sync_enabled == True,  # noqa: E712
        )
        if device_id is not None:
            statement = statement.where(BiometricDevice.id == device_id)
        return list(self._session.scalars(statement.order_by(BiometricDevice.code)).all())

    def list_mappings(
        self, *, employee_id: int | None = None, device_id: int | None = None, active_only: bool = True
    ) -> list[MappingRow]:
        emp_name = func.nullif(
            func.ltrim(func.rtrim(func.concat(Employee.first_name, " ", func.coalesce(Employee.last_name, "")))),
            "",
        )
        statement = (
            select(
                BiometricEmployeeMapping,
                Employee.employee_code,
                emp_name,
                Department.name,
                Branch.name,
                BiometricDevice.name,
            )
            .outerjoin(Employee, Employee.id == BiometricEmployeeMapping.employee_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(Branch, Branch.id == Employee.branch_id)
            .outerjoin(BiometricDevice, BiometricDevice.id == BiometricEmployeeMapping.device_id)
            .order_by(BiometricEmployeeMapping.id.desc())
        )
        if employee_id is not None:
            statement = statement.where(BiometricEmployeeMapping.employee_id == employee_id)
        if device_id is not None:
            statement = statement.where(BiometricEmployeeMapping.device_id == device_id)
        if active_only:
            statement = statement.where(BiometricEmployeeMapping.is_active == True)  # noqa: E712
        rows = self._session.execute(statement).all()
        return [
            MappingRow(
                mapping=row[0],
                employee_code=row[1],
                employee_name=row[2],
                department_name=row[3],
                branch_name=row[4],
                device_name=row[5],
            )
            for row in rows
        ]

    def find_employee_id(
        self, biometric_user_id: str, device_id: int, *, on_date: date
    ) -> int | None:
        """Resolve employee for a punch: device-specific mapping wins over a global (null device) mapping."""
        rows = self._session.scalars(
            select(BiometricEmployeeMapping).where(
                BiometricEmployeeMapping.biometric_user_id == biometric_user_id,
                BiometricEmployeeMapping.is_active == True,  # noqa: E712
                BiometricEmployeeMapping.effective_from <= on_date,
                or_(
                    BiometricEmployeeMapping.effective_to.is_(None),
                    BiometricEmployeeMapping.effective_to >= on_date,
                ),
                or_(
                    BiometricEmployeeMapping.device_id == device_id,
                    BiometricEmployeeMapping.device_id.is_(None),
                ),
            )
        ).all()
        for row in rows:
            if row.device_id == device_id:
                return row.employee_id
        for row in rows:
            if row.device_id is None:
                return row.employee_id
        return None

    def punch_exists(
        self,
        *,
        device_id: int,
        biometric_user_id: str,
        punched_at: datetime,
        external_punch_id: str | None,
    ) -> bool:
        """Duplicate when the same external id exists, else same device+user+timestamp."""
        if external_punch_id:
            by_external = self._session.scalar(
                select(BiometricPunchLog.id).where(
                    BiometricPunchLog.device_id == device_id,
                    BiometricPunchLog.external_punch_id == external_punch_id,
                    BiometricPunchLog.is_active == True,  # noqa: E712
                )
            )
            return by_external is not None
        composite = self._session.scalar(
            select(BiometricPunchLog.id).where(
                BiometricPunchLog.device_id == device_id,
                BiometricPunchLog.biometric_user_id == biometric_user_id,
                BiometricPunchLog.punched_at == punched_at,
                BiometricPunchLog.external_punch_id.is_(None),
                BiometricPunchLog.is_active == True,  # noqa: E712
            )
        )
        return composite is not None

    def list_punches(
        self,
        *,
        device_id: int | None,
        employee_id: int | None,
        biometric_user_id: str | None,
        punch_type: str | None,
        search: str | None,
        from_at: datetime | None,
        to_at: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[PunchRow], int]:
        emp_name = func.nullif(
            func.ltrim(func.rtrim(func.concat(Employee.first_name, " ", func.coalesce(Employee.last_name, "")))),
            "",
        )
        statement = (
            select(
                BiometricPunchLog,
                Employee.employee_code,
                emp_name,
                Department.name,
                BiometricDevice.name,
                BiometricDevice.location_name,
            )
            .outerjoin(Employee, Employee.id == BiometricPunchLog.employee_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(BiometricDevice, BiometricDevice.id == BiometricPunchLog.device_id)
            .where(BiometricPunchLog.is_active == True)  # noqa: E712
        )
        statement = self._punch_filters(
            statement,
            device_id=device_id,
            employee_id=employee_id,
            biometric_user_id=biometric_user_id,
            punch_type=punch_type,
            search=search,
            from_at=from_at,
            to_at=to_at,
            emp_name=emp_name,
        )
        total = self._session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self._session.execute(
            statement.order_by(BiometricPunchLog.punched_at.desc(), BiometricPunchLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [
            PunchRow(
                punch=row[0],
                employee_code=row[1],
                employee_name=row[2],
                department_name=row[3],
                device_name=row[4],
                device_location=row[5],
            )
            for row in rows
        ], int(total)

    def list_sync_logs(
        self,
        *,
        device_id: int | None,
        status: str | None,
        trigger: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[SyncRow], int]:
        statement = (
            select(BiometricSyncLog, BiometricDevice.name, BiometricDevice.code)
            .outerjoin(BiometricDevice, BiometricDevice.id == BiometricSyncLog.device_id)
        )
        if device_id is not None:
            statement = statement.where(BiometricSyncLog.device_id == device_id)
        if status is not None:
            statement = statement.where(BiometricSyncLog.status == status)
        if trigger is not None:
            statement = statement.where(BiometricSyncLog.trigger == trigger)
        total = self._session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self._session.execute(
            statement.order_by(BiometricSyncLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [
            SyncRow(sync=row[0], device_name=row[1], device_code=row[2]) for row in rows
        ], int(total)

    def count_mapped_employees(self) -> int:
        return int(
            self._session.scalar(
                select(func.count(func.distinct(BiometricEmployeeMapping.employee_id))).where(
                    BiometricEmployeeMapping.is_active == True  # noqa: E712
                )
            )
            or 0
        )

    def count_punches_between(self, start: datetime, end: datetime) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(BiometricPunchLog)
                .where(
                    BiometricPunchLog.is_active == True,  # noqa: E712
                    BiometricPunchLog.punched_at >= start,
                    BiometricPunchLog.punched_at < end,
                )
            )
            or 0
        )

    def count_sync_failures(self) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(BiometricSyncLog)
                .where(BiometricSyncLog.status == "Failed")
            )
            or 0
        )

    def latest_sync_log(self) -> BiometricSyncLog | None:
        return self._session.scalar(select(BiometricSyncLog).order_by(BiometricSyncLog.id.desc()).limit(1))

    def punches_for_day(self, day: date) -> list[BiometricPunchLog]:
        """Active punches for a calendar day (aggregated in service for dialect portability)."""
        start = datetime.combine(day, time.min)
        end = datetime.combine(day, time.max.replace(microsecond=0))
        return list(
            self._session.scalars(
                select(BiometricPunchLog).where(
                    BiometricPunchLog.is_active == True,  # noqa: E712
                    BiometricPunchLog.punched_at >= start,
                    BiometricPunchLog.punched_at <= end,
                )
            ).all()
        )

    @staticmethod
    def _punch_filters(
        statement: Select[Any],
        *,
        device_id: int | None,
        employee_id: int | None,
        biometric_user_id: str | None,
        punch_type: str | None,
        search: str | None,
        from_at: datetime | None,
        to_at: datetime | None,
        emp_name: Any | None = None,
    ) -> Select[Any]:
        clauses = []
        if device_id is not None:
            clauses.append(BiometricPunchLog.device_id == device_id)
        if employee_id is not None:
            clauses.append(BiometricPunchLog.employee_id == employee_id)
        if biometric_user_id is not None:
            clauses.append(BiometricPunchLog.biometric_user_id == biometric_user_id)
        if punch_type is not None:
            clauses.append(BiometricPunchLog.punch_type == punch_type)
        if from_at is not None:
            clauses.append(BiometricPunchLog.punched_at >= from_at)
        if to_at is not None:
            clauses.append(BiometricPunchLog.punched_at <= to_at)
        if search:
            term = f"%{search.strip()}%"
            name_col = emp_name if emp_name is not None else Employee.first_name
            clauses.append(
                or_(
                    Employee.employee_code.ilike(term),
                    name_col.ilike(term),
                    BiometricPunchLog.biometric_user_id.ilike(term),
                    BiometricDevice.name.ilike(term),
                    BiometricDevice.location_name.ilike(term),
                    BiometricDevice.code.ilike(term),
                )
            )
        if clauses:
            statement = statement.where(and_(*clauses))
        return statement
