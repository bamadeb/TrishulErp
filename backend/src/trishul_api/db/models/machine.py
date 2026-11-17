# Hand-written until the model generator is re-run. Keep these columns in step with
# migration 0042_machine_engineer.

"""The service engineer attached to a machine: new service calls on it are assigned to them."""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Audited, Base


class MachineEngineer(Audited, Base):
    """One row per machine that has an engineer attached; no row means none."""

    __tablename__ = "machine_engineer"
    __table_args__ = (
        sa.UniqueConstraint("machine_unit_id", name="UQ_svc_machine_engineer_machine_unit_id"),
        {"schema": "svc"},
    )

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    machine_unit_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.machine_unit.id"))
    engineer_employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
