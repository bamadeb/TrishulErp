"""ORM models for every table, generated from the SQL scripts.

    generated/        one module per schema; never edit (scripts/generate_models.py writes it)
    base.py           Base and the Audited marker

Import models from here: `from trishul_api.db.models import ServiceCall`. To change a model, change
the SQL (a migration) or scripts/model_options.toml and re-run the generator.
"""

from trishul_api.db.models.base import Audited, Base
from trishul_api.db.models.generated import *  # noqa: F403
from trishul_api.db.models.generated import __all__ as _generated

# Hand-written until the generator is re-run against the migrated DB (see trk.py).
from trishul_api.db.models.trk import (
    TrackableActivity,
    TrackableActivityModuleCode,
    TrkTrip,
    TrkTripDistanceAdjustment,
    TrkTripGpsPoint,
    TrkTripStatus,
    TrkTripType,
    TrkTripVehicleType,
)

__all__ = [
    "Audited",
    "Base",
    "TrackableActivity",
    "TrackableActivityModuleCode",
    "TrkTrip",
    "TrkTripDistanceAdjustment",
    "TrkTripGpsPoint",
    "TrkTripStatus",
    "TrkTripType",
    "TrkTripVehicleType",
    *_generated,
]
