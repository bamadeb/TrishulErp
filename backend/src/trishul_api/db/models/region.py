# Hand-written until the generator is re-run against the migrated DB (migration 0023): it mirrors
# core.region and core.branch.region_id. After regenerating, delete this file.

"""Warehouse regions: a group of branches supplied by one warehouse."""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Audited, Base
from trishul_api.db.models.generated.core import Branch


class Region(Base, Audited):
    """A group of branches supplied by one warehouse; every branch of the region follows that warehouse."""

    __tablename__ = "region"
    __table_args__ = {"schema": "core"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    code: Mapped[str] = mapped_column(sa.NVARCHAR(10), doc="Region code")
    name: Mapped[str] = mapped_column(sa.NVARCHAR(80), doc="Region name")
    warehouse_id: Mapped[int] = mapped_column(
        sa.BigInteger(),
        sa.ForeignKey("core.branch.id"),
        doc="Warehouse (branch of type Warehouse) supplying the region",
    )
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


# The region a branch belongs to; the branch's parent_warehouse_id follows the region's warehouse.
Branch.region_id = mapped_column(sa.BigInteger(), sa.ForeignKey("core.region.id"), nullable=True)  # type: ignore[attr-defined]
