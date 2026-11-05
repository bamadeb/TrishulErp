"""Tracking configuration: the values the mobile app fetches instead of hard-coding.

Rows live in trk.tracking_config. The flat TrackingConfigOut is the contract with the phone; the rows
carry what an administrator needs (unit, limits, allowed values, calibration state).
"""

import hashlib
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import NotFound
from trishul_api.db.models import TrkTrackingConfig
from trishul_api.modules.trk.master_service import InvalidMasterValue
from trishul_api.modules.trk.schemas import TrackingConfigOut, TrackingConfigParameter, TrackingConfigUpdate

# The app's own behaviour if a row is missing or deactivated: the same values the table is seeded with.
# Calibration parameters have no default, so they stay null.
_FALLBACK: dict[str, str | None] = {
    "movingIntervalMs": "3000",
    "movingPriority": "HIGH_ACCURACY",
    "stationaryCandidateDurationMs": "180000",
    "stationaryDwellRadiusMeters": "35",
    "movementRecoveryDisplacementMeters": "25",
    "varianceThresholdMoving": None,
    "varianceThresholdStationary": None,
    "samplingPeriodUs": None,
}


def _number(text: str) -> Decimal:
    return Decimal(text)


def _plain(value: Decimal) -> str:
    """35.0000 -> '35', 0.5 -> '0.5' (never scientific notation)."""
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class TrackingConfigService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------ reads

    def _rows(self) -> list[TrkTrackingConfig]:
        return list(
            self._db.scalars(
                select(TrkTrackingConfig)
                .where(TrkTrackingConfig.is_active)
                .order_by(TrkTrackingConfig.sort_order, TrkTrackingConfig.code)
            )
        )

    def current(self) -> TrackingConfigOut:
        values = {**_FALLBACK, **{r.code: r.value for r in self._rows()}}

        def whole(key: str) -> int | None:
            return None if values[key] is None else int(_number(values[key] or ""))

        def decimal(key: str) -> float | None:
            return None if values[key] is None else float(_number(values[key] or ""))

        pending = [key for key, value in values.items() if value is None]
        digest = hashlib.sha256("|".join(f"{k}={values[k]}" for k in sorted(values)).encode()).hexdigest()[:12]
        return TrackingConfigOut(
            moving_interval_ms=whole("movingIntervalMs") or 0,
            moving_priority=values["movingPriority"] or "",
            stationary_candidate_duration_ms=whole("stationaryCandidateDurationMs") or 0,
            stationary_dwell_radius_meters=decimal("stationaryDwellRadiusMeters") or 0.0,
            movement_recovery_displacement_meters=decimal("movementRecoveryDisplacementMeters") or 0.0,
            variance_threshold_moving=decimal("varianceThresholdMoving"),
            variance_threshold_stationary=decimal("varianceThresholdStationary"),
            sampling_period_us=whole("samplingPeriodUs"),
            calibration_pending=pending,
            version=digest,
        )

    def parameters(self) -> list[TrackingConfigParameter]:
        return [self._parameter(row) for row in self._rows()]

    # ------------------------------------------------------------------ write

    def update(
        self, user: CurrentUser, code: str, row_version: bytes, data: TrackingConfigUpdate
    ) -> TrackingConfigParameter:
        row = self._db.scalar(
            select(TrkTrackingConfig).where(TrkTrackingConfig.code == code, TrkTrackingConfig.is_active)
        )
        if row is None:
            raise NotFound("Tracking parameter not found.")
        check_row_version(row.row_version, row_version)
        row.value = self._checked(row, data.value)
        row.updated_by_user_id = user.id
        self._db.commit()
        return self._parameter(row)

    def _checked(self, row: TrkTrackingConfig, raw: int | float | str | None) -> str | None:
        """The value to store, or a 422 saying what is wrong with it."""
        if raw is None:
            if row.default_value is not None:
                self._reject(f"{row.name} has a default and cannot be cleared; set a value.")
            return None
        if row.value_type == "string":
            if not isinstance(raw, str) or not raw.strip():
                self._reject("Send the value as non-empty text.")
            text = raw.strip()
            allowed = (row.allowed_values or "").split(",") if row.allowed_values else []
            if allowed and text not in allowed:
                self._reject(f"Must be one of: {', '.join(allowed)}.")
            return text
        text = raw.strip() if isinstance(raw, str) else str(raw)
        try:
            number = _number(text) if text else None
        except InvalidOperation:
            number = None
        if number is None or not number.is_finite():
            self._reject("Send a number.")
        assert number is not None
        if row.value_type == "int" and number != number.to_integral_value():
            self._reject("Must be a whole number.")
        unit = f" {row.unit}" if row.unit else ""
        if row.min_value is not None and number < row.min_value:
            self._reject(f"Must be at least {_plain(row.min_value)}{unit}.")
        if row.max_value is not None and number > row.max_value:
            self._reject(f"Must be at most {_plain(row.max_value)}{unit}.")
        return _plain(number)

    @staticmethod
    def _reject(message: str) -> None:
        raise InvalidMasterValue("The value is not valid for this parameter.", {"value": [message]})

    @staticmethod
    def _parameter(row: TrkTrackingConfig) -> TrackingConfigParameter:
        return TrackingConfigParameter(
            code=row.code,
            name=row.name,
            description=row.description,
            value_type=row.value_type,
            value=row.value,
            default_value=row.default_value,
            unit=row.unit,
            min_value=None if row.min_value is None else float(row.min_value),
            max_value=None if row.max_value is None else float(row.max_value),
            allowed_values=row.allowed_values.split(",") if row.allowed_values else None,
            is_calibrated=row.value is not None,
            updated_at=row.updated_at,
            row_version=row.row_version,
        )
