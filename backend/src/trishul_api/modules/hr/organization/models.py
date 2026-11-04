"""Binds each Organization section to a table that already exists.

Nothing here is mapped as a new table. Grades are the ``grade`` column on
``hr.designation``. The Locations screen is ``core.branch`` (``core.location`` is a
warehouse stock bin). Reporting hierarchy is ``core.employee.reporting_manager_id``.
"""

from collections.abc import Mapping
from types import MappingProxyType

from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute

from trishul_api.db.models.generated.core import Branch, Company, Employee
from trishul_api.db.models.generated.hr import Department, Designation

SECTION_MODELS: Mapping[str, type[DeclarativeBase]] = MappingProxyType(
    {
        "departments": Department,
        "designations": Designation,
        "grades": Designation,
        "locations": Branch,
        "companies": Company,
        "hierarchy": Employee,
    }
)

GRADE_COLUMN: InstrumentedAttribute[str | None] = Designation.grade
HIERARCHY_COLUMN: InstrumentedAttribute[int | None] = Employee.reporting_manager_id
