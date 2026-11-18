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
from trishul_api.db.models.asc import ContractVisitDay
from trishul_api.db.models.machine import MachineEngineer
from trishul_api.db.models.leave import (
    LeaveAttendanceClass,
    LeaveBalanceTransaction,
    LeaveEntitlementRun,
    LeavePolicy,
    LeavePolicyAssignment,
    LeavePolicyLine,
    LeaveTypeSetting,
    LeaveWeeklyRestGrant,
)
from trishul_api.db.models.reporting import ReportingAssignment
from trishul_api.db.models.salary_template import (
    SalaryTemplate,
    SalaryTemplateAssignment,
    SalaryTemplateDesignation,
    SalaryTemplateGrade,
    SalaryTemplateLine,
)
from trishul_api.db.models.trk import (
    TrackableActivity,
    TrackableActivityModule,
    TrkGpsDiagnosticEventType,
    TrkManualTravel,
    TrkTrackingConfig,
    TrkTrip,
    TrkTripDistanceAdjustment,
    TrkTripGpsDiagnostic,
    TrkTripGpsPoint,
    TrkTripStatusMaster,
    TrkTripTypeMaster,
    TrkTripVehicleTypeMaster,
)

__all__ = [
    "Audited",
    "Base",
    "ContractVisitDay",
    "LeaveAttendanceClass",
    "LeaveBalanceTransaction",
    "LeaveEntitlementRun",
    "LeavePolicy",
    "LeavePolicyAssignment",
    "LeavePolicyLine",
    "LeaveTypeSetting",
    "LeaveWeeklyRestGrant",
    "MachineEngineer",
    "ReportingAssignment",
    "SalaryTemplate",
    "SalaryTemplateAssignment",
    "SalaryTemplateDesignation",
    "SalaryTemplateGrade",
    "SalaryTemplateLine",
    "TrackableActivity",
    "TrackableActivityModule",
    "TrkGpsDiagnosticEventType",
    "TrkManualTravel",
    "TrkTrackingConfig",
    "TrkTrip",
    "TrkTripDistanceAdjustment",
    "TrkTripGpsDiagnostic",
    "TrkTripGpsPoint",
    "TrkTripStatusMaster",
    "TrkTripTypeMaster",
    "TrkTripVehicleTypeMaster",
    *_generated,
]
