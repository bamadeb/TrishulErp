from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, Forbidden
from trishul_api.db.models import (
    TrackableActivityModule,
    TrkGpsDiagnosticEventType,
    TrkTripStatusMaster,
    TrkTripTypeMaster,
    TrkTripVehicleTypeMaster,
)
from trishul_api.modules.trk.master_repository import MasterModel, TripMasterRepository
from trishul_api.modules.trk.schemas import (
    ModuleCodeItem,
    TripMasterData,
    TripStatusItem,
    TripTypeItem,
    VehicleTypeItem,
)


class InvalidMasterValue(ApiError):
    """A request used a module / trip type / vehicle type that is not an active master value."""

    status = 422
    title = "Invalid input"


class TripMasterService:
    def __init__(self, db: Session) -> None:
        self._repo = TripMasterRepository(db)

    # ------------------------------------------------------------------ reads

    def module_codes(self, user: CurrentUser, include_inactive: bool) -> list[ModuleCodeItem]:
        rows = self._rows(user, TrackableActivityModule, include_inactive)
        return [ModuleCodeItem.model_validate(row) for row in rows]

    def trip_types(self, user: CurrentUser, include_inactive: bool) -> list[TripTypeItem]:
        rows = self._rows(user, TrkTripTypeMaster, include_inactive)
        return [TripTypeItem.model_validate(row) for row in rows]

    def vehicle_types(self, user: CurrentUser, include_inactive: bool) -> list[VehicleTypeItem]:
        rows = self._rows(user, TrkTripVehicleTypeMaster, include_inactive)
        return [VehicleTypeItem.model_validate(row) for row in rows]

    def trip_statuses(self, user: CurrentUser, include_inactive: bool) -> list[TripStatusItem]:
        rows = self._rows(user, TrkTripStatusMaster, include_inactive)
        return [TripStatusItem.model_validate(row) for row in rows]

    def all(self, user: CurrentUser, include_inactive: bool) -> TripMasterData:
        return TripMasterData(
            module_codes=self.module_codes(user, include_inactive),
            trip_types=self.trip_types(user, include_inactive),
            vehicle_types=self.vehicle_types(user, include_inactive),
            trip_statuses=self.trip_statuses(user, include_inactive),
        )

    def _rows(self, user: CurrentUser, model: MasterModel, include_inactive: bool) -> list:
        # Inactive rows are for reviewers reading history and for administration, not for pickers.
        if include_inactive and not user.can("trk.trip.view.team", "trk.trip.adjust"):
            raise Forbidden("You may not list inactive master data.")
        return self._repo.rows(model, include_inactive)

    # ------------------------------------------------------------------ validation

    def resolve_start(self, module: str, trip_type: str | None, vehicle_type: str | None) -> str:
        """Check a start request's master values and return the trip type to use (the default when the
        client sent none). Raises InvalidMasterValue listing every bad field."""
        errors: dict[str, list[str]] = {}

        modules = self._repo.active_codes(TrackableActivityModule)
        if module not in modules:
            errors["module"] = [self._not_active("module", module, modules)]

        types = self._repo.active_codes(TrkTripTypeMaster)
        if trip_type is None:
            trip_type = self._repo.default_trip_type()
            if trip_type is None:
                errors["tripType"] = ["No default trip type is configured; send a tripType."]
        elif trip_type not in types:
            errors["tripType"] = [self._not_active("trip type", trip_type, types)]

        if vehicle_type is not None:
            vehicles = self._repo.active_codes(TrkTripVehicleTypeMaster)
            if vehicle_type not in vehicles:
                errors["vehicleType"] = [self._not_active("vehicle type", vehicle_type, vehicles)]

        if errors:
            raise InvalidMasterValue("One or more values are not valid for this trip.", errors)
        assert trip_type is not None
        return trip_type

    def require_known_statuses(self, statuses: list[str]) -> None:
        """A status filter may name any status, including a deactivated one that old trips still use."""
        unknown = sorted(set(statuses) - self._repo.all_codes(TrkTripStatusMaster))
        if unknown:
            raise InvalidMasterValue(
                "Unknown trip status.", {"status": [f"'{value}' is not a trip status." for value in unknown]}
            )

    def require_known_diagnostic_event_types(self, event_types: list[str]) -> None:
        """Every event type must exist. A type deactivated after the device recorded the event is still
        accepted: the device may upload hours later, and refusing would drop the whole batch."""
        unknown = sorted(set(event_types) - self._repo.all_codes(TrkGpsDiagnosticEventType))
        if unknown:
            raise InvalidMasterValue(
                "Unknown GPS diagnostic event type.",
                {"eventType": [f"'{value}' is not a GPS diagnostic event type." for value in unknown]},
            )

    @staticmethod
    def _not_active(label: str, value: str, allowed: list[str]) -> str:
        return f"'{value}' is not an active {label}. Allowed: {', '.join(allowed)}."
