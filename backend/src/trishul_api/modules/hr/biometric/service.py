"""Biometric device management, punch viewing and gated synchronization."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.common.schemas import Page
from trishul_api.config import Settings, get_settings
from trishul_api.db.models import Employee
from trishul_api.db.models.biometric import (
    BiometricDevice,
    BiometricEmployeeMapping,
    BiometricPunchLog,
    BiometricSyncLog,
)
from trishul_api.modules.hr.biometric.client import (
    BiometricApiContractMissing,
    BiometricConnectionConfig,
    BiometricNotConfigured,
    EsslBiometricClient,
)
from trishul_api.modules.hr.biometric.config import BiometricSettings, load_biometric_settings
from trishul_api.modules.hr.biometric.repository import (
    BiometricRepository,
    MappingRow,
    PunchRow,
    SyncRow,
)
from trishul_api.modules.hr.biometric.schemas import (
    BiometricDashboardOut,
    BiometricDeviceCreate,
    BiometricDeviceOut,
    BiometricDeviceUpdate,
    BiometricMappingCreate,
    BiometricMappingOut,
    BiometricMappingUpdate,
    BiometricPunchOut,
    BiometricPunchQuery,
    BiometricSyncLogOut,
    BiometricSyncLogQuery,
    BiometricSyncRequest,
    DeviceStatusCounts,
    DeviceStatusLabel,
    PunchTrendPoint,
)
from trishul_api.secrets import SecretError, SecretProvider

logger = logging.getLogger(__name__)


class BiometricService:
    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        secret_provider: SecretProvider | None = None,
        biometric_settings: BiometricSettings | None = None,
    ) -> None:
        self._db = db
        self._repo = BiometricRepository(db)
        self._settings = settings or get_settings()
        self._biometric = biometric_settings or load_biometric_settings(self._settings)
        self._secrets = secret_provider

    # --- dashboard ---------------------------------------------------------------

    def dashboard(self) -> BiometricDashboardOut:
        devices = self._repo.list_devices()
        status_counts = DeviceStatusCounts(online=0, offline=0, maintenance=0)
        for device in devices:
            label = _device_status(device)
            if label == "Online":
                status_counts.online += 1
            elif label == "Offline":
                status_counts.offline += 1
            else:
                status_counts.maintenance += 1

        today = date.today()
        start = datetime.combine(today, datetime.min.time())
        end = start + timedelta(days=1)
        todays_punches = self._repo.count_punches_between(start, end)
        latest = self._repo.latest_sync_log()
        recent_rows, _ = self._repo.list_punches(
            device_id=None,
            employee_id=None,
            biometric_user_id=None,
            punch_type=None,
            search=None,
            from_at=None,
            to_at=None,
            page=1,
            page_size=6,
        )
        return BiometricDashboardOut(
            registered_devices=len(devices),
            mapped_employees=self._repo.count_mapped_employees(),
            todays_punches=todays_punches,
            last_sync_at=(latest.finished_at or latest.started_at) if latest else None,
            last_sync_status=latest.status if latest else None,  # type: ignore[arg-type]
            sync_failures=self._repo.count_sync_failures(),
            device_status=status_counts,
            punch_trend=_build_trend(self._repo.punches_for_day(today)),
            recent_punches=[_punch_out(row) for row in recent_rows],
        )

    # --- devices -----------------------------------------------------------------

    def list_devices(self) -> list[BiometricDeviceOut]:
        return [_device_out(row) for row in self._repo.list_devices()]

    def get_device(self, device_id: int) -> BiometricDeviceOut:
        return _device_out(self._require_device(device_id))

    def create_device(self, actor: CurrentUser, data: BiometricDeviceCreate) -> BiometricDeviceOut:
        if self._repo.get_device_by_code(data.code):
            raise AlreadyExists(f"A biometric device with code '{data.code}' already exists.")
        now = _utc_now()
        row = BiometricDevice(
            code=data.code,
            name=data.name,
            vendor=data.vendor,
            serial_number=data.serial_number,
            location_name=data.location_name,
            branch_id=data.branch_id,
            external_device_id=data.external_device_id,
            credential_secret_name=data.credential_secret_name,
            base_url=data.base_url,
            is_sync_enabled=data.is_sync_enabled,
            created_by_user_id=actor.id,
            created_at=now,
            is_active=True,
        )
        self._repo.add(row)
        self._repo.commit()
        logger.info("biometric.device.created id=%s code=%s actor=%s", row.id, row.code, actor.id)
        return _device_out(row)

    def update_device(self, actor: CurrentUser, device_id: int, data: BiometricDeviceUpdate) -> BiometricDeviceOut:
        row = self._require_device(device_id)
        payload = data.model_dump(exclude_unset=True)
        for field, value in payload.items():
            setattr(row, field, value)
        row.updated_at = _utc_now()
        row.updated_by_user_id = actor.id
        self._repo.commit()
        logger.info("biometric.device.updated id=%s actor=%s fields=%s", row.id, actor.id, sorted(payload))
        return _device_out(row)

    # --- mappings ----------------------------------------------------------------

    def list_mappings(self, employee_id: int | None = None, device_id: int | None = None) -> list[BiometricMappingOut]:
        return [_mapping_out(row) for row in self._repo.list_mappings(employee_id=employee_id, device_id=device_id)]

    def create_mapping(self, actor: CurrentUser, data: BiometricMappingCreate) -> BiometricMappingOut:
        employee = self._db.get(Employee, data.employee_id)
        if employee is None or not employee.is_active:
            raise NotFound("Employee not found.")
        if data.device_id is not None:
            self._require_device(data.device_id)
        if data.effective_to is not None and data.effective_to < data.effective_from:
            raise ApiError(
                "effectiveTo must be on or after effectiveFrom.",
                errors={"effectiveTo": ["Must be on or after effectiveFrom."]},
            )
        row = BiometricEmployeeMapping(
            employee_id=data.employee_id,
            biometric_user_id=data.biometric_user_id,
            device_id=data.device_id,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            created_by_user_id=actor.id,
            created_at=_utc_now(),
            is_active=True,
        )
        self._repo.add(row)
        self._repo.commit()
        logger.info(
            "biometric.mapping.created id=%s employee_id=%s biometric_user_id=%s actor=%s",
            row.id,
            row.employee_id,
            row.biometric_user_id,
            actor.id,
        )
        enriched = self._repo.list_mappings(employee_id=row.employee_id, device_id=row.device_id)
        match = next((item for item in enriched if item.mapping.id == row.id), None)
        return _mapping_out(match) if match else _mapping_out_plain(row)

    def update_mapping(self, actor: CurrentUser, mapping_id: int, data: BiometricMappingUpdate) -> BiometricMappingOut:
        row = self._repo.get_mapping(mapping_id)
        if row is None:
            raise NotFound("Biometric mapping not found.")
        payload = data.model_dump(exclude_unset=True)
        if "device_id" in payload and payload["device_id"] is not None:
            self._require_device(payload["device_id"])
        effective_from = payload.get("effective_from", row.effective_from)
        effective_to = payload.get("effective_to", row.effective_to)
        if effective_to is not None and effective_from is not None and effective_to < effective_from:
            raise ApiError(
                "effectiveTo must be on or after effectiveFrom.",
                errors={"effectiveTo": ["Must be on or after effectiveFrom."]},
            )
        for field, value in payload.items():
            setattr(row, field, value)
        row.updated_at = _utc_now()
        row.updated_by_user_id = actor.id
        self._repo.commit()
        enriched = self._repo.list_mappings(employee_id=row.employee_id, device_id=row.device_id, active_only=False)
        match = next((item for item in enriched if item.mapping.id == row.id), None)
        return _mapping_out(match) if match else _mapping_out_plain(row)

    def deactivate_mapping(self, actor: CurrentUser, mapping_id: int) -> BiometricMappingOut:
        return self.update_mapping(actor, mapping_id, BiometricMappingUpdate(is_active=False))

    # --- punches -----------------------------------------------------------------

    def list_punches(self, query: BiometricPunchQuery) -> Page[BiometricPunchOut]:
        rows, total = self._repo.list_punches(
            device_id=query.device_id,
            employee_id=query.employee_id,
            biometric_user_id=query.biometric_user_id,
            punch_type=query.punch_type,
            search=query.search,
            from_at=_naive_utc(query.from_at),
            to_at=_naive_utc(query.to_at),
            page=query.page,
            page_size=query.page_size,
        )
        return Page(
            items=[_punch_out(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def insert_punch_if_new(
        self,
        *,
        device_id: int,
        biometric_user_id: str,
        punched_at: datetime,
        punch_type: str | None = None,
        external_punch_id: str | None = None,
        source: str = "Sync",
        sync_log_id: int | None = None,
        actor_id: int | None = None,
    ) -> bool:
        punched = _naive_utc(punched_at) or punched_at
        if self._repo.punch_exists(
            device_id=device_id,
            biometric_user_id=biometric_user_id,
            punched_at=punched,
            external_punch_id=external_punch_id,
        ):
            logger.info(
                "biometric.punch.duplicate device_id=%s biometric_user_id=%s punched_at=%s external_punch_id=%s",
                device_id,
                biometric_user_id,
                punched.isoformat(),
                external_punch_id,
            )
            return False
        employee_id = self._repo.find_employee_id(biometric_user_id, device_id, on_date=punched.date())
        self._repo.add(
            BiometricPunchLog(
                device_id=device_id,
                employee_id=employee_id,
                biometric_user_id=biometric_user_id,
                punched_at=punched,
                punch_type=punch_type,
                external_punch_id=external_punch_id,
                source=source,
                sync_log_id=sync_log_id,
                created_by_user_id=actor_id,
                created_at=_utc_now(),
                is_active=True,
            )
        )
        self._repo.flush()
        return True

    # --- sync --------------------------------------------------------------------

    def list_sync_logs(self, query: BiometricSyncLogQuery) -> Page[BiometricSyncLogOut]:
        rows, total = self._repo.list_sync_logs(
            device_id=query.device_id,
            status=query.status,
            trigger=query.trigger,
            page=query.page,
            page_size=query.page_size,
        )
        return Page(
            items=[_sync_out(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def run_manual_sync(self, actor: CurrentUser, data: BiometricSyncRequest) -> BiometricSyncLogOut:
        started = _utc_now()
        log = BiometricSyncLog(
            device_id=data.device_id,
            started_at=started,
            status="Running",
            trigger="Manual",
            records_fetched=0,
            records_inserted=0,
            records_duplicate=0,
            created_by_user_id=actor.id,
            created_at=started,
        )
        self._repo.add(log)
        self._repo.flush()
        sync_log_id = log.id

        if not self._biometric.sync_enabled:
            message = (
                "Biometric synchronization is disabled until eSSL API documentation and credentials are provided."
            )
            self._finish_skipped(log, message)
            raise ApiError(message)

        devices = self._repo.list_sync_enabled_devices(data.device_id)
        if data.device_id is not None and not devices:
            device = self._repo.get_device(data.device_id)
            if device is None:
                return self._finish_failed(log, "Device not found.")
            return self._finish_skipped(log, "Device sync is not enabled or the device is inactive.")
        if not devices:
            return self._finish_skipped(log, "No active biometric devices have sync enabled.")

        fetched = inserted = duplicates = 0
        try:
            for device in devices:
                counts = self._sync_device(device, actor_id=actor.id, sync_log_id=sync_log_id, request=data)
                fetched += counts["fetched"]
                inserted += counts["inserted"]
                duplicates += counts["duplicates"]
                device.last_synced_at = _utc_now()
                device.updated_at = device.last_synced_at
                device.updated_by_user_id = actor.id
        except (BiometricNotConfigured, BiometricApiContractMissing, SecretError, ApiError) as error:
            message = str(error)
            logger.warning(
                "biometric.sync.refused sync_log_id=%s device_id=%s reason=%s",
                sync_log_id,
                data.device_id,
                type(error).__name__,
            )
            self._finish_skipped(log, message, fetched=fetched, inserted=inserted, duplicates=duplicates)
            raise ApiError(message) from error
        except Exception:
            logger.exception("biometric.sync.failed sync_log_id=%s device_id=%s", sync_log_id, data.device_id)
            self._finish_failed(
                log,
                "Synchronization failed. See server logs for details.",
                fetched=fetched,
                inserted=inserted,
                duplicates=duplicates,
            )
            raise

        log.records_fetched = fetched
        log.records_inserted = inserted
        log.records_duplicate = duplicates
        log.status = "Success"
        log.finished_at = _utc_now()
        self._repo.commit()
        logger.info(
            "biometric.sync.success sync_log_id=%s fetched=%s inserted=%s duplicates=%s",
            sync_log_id,
            fetched,
            inserted,
            duplicates,
        )
        return _sync_out(SyncRow(sync=log, device_name=None, device_code=None))

    def _sync_device(
        self,
        device: BiometricDevice,
        *,
        actor_id: int,
        sync_log_id: int,
        request: BiometricSyncRequest,
    ) -> dict[str, int]:
        secret_name = device.credential_secret_name or self._biometric.default_secret_id
        connection = BiometricConnectionConfig(
            base_url=device.base_url,
            credential_secret_name=secret_name,
        )
        credentials = self._load_credentials(secret_name)
        with EsslBiometricClient(connection, credentials=credentials) as client:
            punches = client.fetch_punches(
                device_external_id=device.external_device_id,
                since=_naive_utc(request.since),
                until=_naive_utc(request.until),
            )

        inserted = duplicates = 0
        for punch in punches:
            if not isinstance(punch, dict):
                continue
            biometric_user_id = str(punch.get("biometric_user_id") or "").strip()
            punched_at = punch.get("punched_at")
            if not biometric_user_id or not isinstance(punched_at, datetime):
                logger.warning(
                    "biometric.sync.skip_unmapped_punch sync_log_id=%s device_id=%s keys=%s",
                    sync_log_id,
                    device.id,
                    sorted(punch.keys()),
                )
                continue
            external_punch_id = punch.get("external_punch_id")
            external_id = str(external_punch_id).strip() if external_punch_id else None
            punch_type = punch.get("punch_type")
            type_value = str(punch_type).strip() if punch_type else None
            if self.insert_punch_if_new(
                device_id=device.id,
                biometric_user_id=biometric_user_id,
                punched_at=punched_at,
                punch_type=type_value,
                external_punch_id=external_id,
                source="Sync",
                sync_log_id=sync_log_id,
                actor_id=actor_id,
            ):
                inserted += 1
            else:
                duplicates += 1
        return {"fetched": len(punches), "inserted": inserted, "duplicates": duplicates}

    def _load_credentials(self, secret_name: str | None) -> dict[str, Any]:
        if not secret_name:
            raise BiometricNotConfigured(
                "Biometric credential secret name is not configured (AWS Secrets Manager)."
            )
        if self._secrets is None:
            raise BiometricNotConfigured("Secrets Manager provider is not available.")
        data = self._secrets.get_json(secret_name)
        return dict(data)

    def _finish_skipped(
        self,
        log: BiometricSyncLog,
        message: str,
        *,
        fetched: int = 0,
        inserted: int = 0,
        duplicates: int = 0,
    ) -> BiometricSyncLogOut:
        log.status = "Skipped"
        log.error_message = message[:500]
        log.records_fetched = fetched
        log.records_inserted = inserted
        log.records_duplicate = duplicates
        log.finished_at = _utc_now()
        self._repo.commit()
        logger.info("biometric.sync.skipped sync_log_id=%s reason=%s", log.id, message)
        return _sync_out(SyncRow(sync=log, device_name=None, device_code=None))

    def _finish_failed(
        self,
        log: BiometricSyncLog,
        message: str,
        *,
        fetched: int = 0,
        inserted: int = 0,
        duplicates: int = 0,
    ) -> BiometricSyncLogOut:
        log.status = "Failed"
        log.error_message = message[:500]
        log.records_fetched = fetched
        log.records_inserted = inserted
        log.records_duplicate = duplicates
        log.finished_at = _utc_now()
        self._repo.commit()
        logger.error("biometric.sync.failed sync_log_id=%s reason=%s", log.id, message)
        return _sync_out(SyncRow(sync=log, device_name=None, device_code=None))

    def _require_device(self, device_id: int) -> BiometricDevice:
        row = self._repo.get_device(device_id)
        if row is None:
            raise NotFound("Biometric device not found.")
        return row


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _device_status(row: BiometricDevice) -> DeviceStatusLabel:
    if not row.is_active:
        return "Offline"
    if not row.is_sync_enabled:
        return "Maintenance"
    return "Online"


def _device_out(row: BiometricDevice) -> BiometricDeviceOut:
    return BiometricDeviceOut(
        id=row.id,
        code=row.code,
        name=row.name,
        vendor=row.vendor,
        serial_number=row.serial_number,
        location_name=row.location_name,
        branch_id=row.branch_id,
        external_device_id=row.external_device_id,
        credential_secret_name=row.credential_secret_name,
        base_url=row.base_url,
        is_sync_enabled=row.is_sync_enabled,
        last_synced_at=row.last_synced_at,
        is_active=row.is_active,
        status=_device_status(row),
        created_at=row.created_at,
        row_version=row.row_version,
    )


def _mapping_out(row: MappingRow) -> BiometricMappingOut:
    m = row.mapping
    return BiometricMappingOut(
        id=m.id,
        employee_id=m.employee_id,
        employee_code=row.employee_code,
        employee_name=row.employee_name,
        department_name=row.department_name,
        branch_name=row.branch_name,
        biometric_user_id=m.biometric_user_id,
        device_id=m.device_id,
        device_name=row.device_name,
        effective_from=m.effective_from,
        effective_to=m.effective_to,
        is_active=m.is_active,
        created_at=m.created_at,
    )


def _mapping_out_plain(row: BiometricEmployeeMapping) -> BiometricMappingOut:
    return BiometricMappingOut(
        id=row.id,
        employee_id=row.employee_id,
        biometric_user_id=row.biometric_user_id,
        device_id=row.device_id,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        is_active=row.is_active,
        created_at=row.created_at,
    )


def _punch_out(row: PunchRow) -> BiometricPunchOut:
    p = row.punch
    return BiometricPunchOut(
        id=p.id,
        device_id=p.device_id,
        device_name=row.device_name,
        device_location=row.device_location,
        employee_id=p.employee_id,
        employee_code=row.employee_code,
        employee_name=row.employee_name,
        department_name=row.department_name,
        biometric_user_id=p.biometric_user_id,
        punched_at=p.punched_at,
        punch_type=p.punch_type,
        external_punch_id=p.external_punch_id,
        source=p.source,
        sync_log_id=p.sync_log_id,
        created_at=p.created_at,
    )


def _sync_out(row: SyncRow) -> BiometricSyncLogOut:
    s = row.sync
    return BiometricSyncLogOut(
        id=s.id,
        device_id=s.device_id,
        device_name=row.device_name,
        device_code=row.device_code,
        started_at=s.started_at,
        finished_at=s.finished_at,
        status=s.status,  # type: ignore[arg-type]
        trigger=s.trigger,  # type: ignore[arg-type]
        records_fetched=s.records_fetched,
        records_inserted=s.records_inserted,
        records_duplicate=s.records_duplicate,
        error_message=s.error_message,
        created_by_user_id=s.created_by_user_id,
    )


def _build_trend(punches: list[BiometricPunchLog]) -> list[PunchTrendPoint]:
    buckets: dict[int, dict[str, int]] = defaultdict(lambda: {"IN": 0, "OUT": 0})
    for punch in punches:
        hour = punch.punched_at.hour
        kind = (punch.punch_type or "").upper()
        if kind == "IN":
            buckets[hour]["IN"] += 1
        elif kind == "OUT":
            buckets[hour]["OUT"] += 1
    # Always show a working-day window so the chart has structure even with sparse data.
    hours = list(range(8, 19))
    for hour in buckets:
        if hour not in hours:
            hours.append(hour)
    hours.sort()
    return [
        PunchTrendPoint(
            hour=_hour_label(hour),
            check_in=buckets[hour]["IN"],
            check_out=buckets[hour]["OUT"],
        )
        for hour in hours
    ]


def _hour_label(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    display = hour % 12 or 12
    return f"{display} {suffix}"
