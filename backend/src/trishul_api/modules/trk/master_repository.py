from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.db.models import (
    TrackableActivityModule,
    TrkGpsDiagnosticEventType,
    TrkTripStatusMaster,
    TrkTripTypeMaster,
    TrkTripVehicleTypeMaster,
)

MasterModel = (
    type[TrackableActivityModule]
    | type[TrkTripTypeMaster]
    | type[TrkTripVehicleTypeMaster]
    | type[TrkTripStatusMaster]
    | type[TrkGpsDiagnosticEventType]
)


class TripMasterRepository:
    """Reads the trip-tracking master tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def rows(self, model: MasterModel, include_inactive: bool = False) -> list:
        statement = select(model).order_by(model.sort_order, model.name)
        if not include_inactive:
            statement = statement.where(model.is_active)
        return list(self._session.scalars(statement))

    def active_codes(self, model: MasterModel) -> list[str]:
        """Codes a client may use now, in display order."""
        return list(
            self._session.scalars(select(model.code).where(model.is_active).order_by(model.sort_order, model.name))
        )

    def all_codes(self, model: MasterModel) -> set[str]:
        """Every code, active or not: past trips keep using a code that was later deactivated."""
        return set(self._session.scalars(select(model.code)))

    def default_trip_type(self) -> str | None:
        return self._session.scalar(
            select(TrkTripTypeMaster.code).where(TrkTripTypeMaster.is_default, TrkTripTypeMaster.is_active)
        )
