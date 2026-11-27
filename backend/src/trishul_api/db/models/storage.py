# Hand-written until the model generator is re-run. Keep these columns in step with
# migrations 0051_storage_racks, 0052_barcodes_scan, 0053_putaway_bin_moves, 0054_stock_counts and
# 0055_batch_scan.

"""A physical rack of a stock location; its bins (inv.bin) are generated level x position."""

import datetime as dt
from decimal import Decimal
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Audited, Base

StorageRackType = Literal["Rack", "Shelf", "Bin cabinet", "Floor"]


class StorageRack(Audited, Base):
    """A rack (or shelf unit, bin cabinet, floor block) of a location, with levels x positions of bins."""

    __tablename__ = "storage_rack"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    location_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.location.id"))
    code: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    short_code: Mapped[str] = mapped_column(sa.NVARCHAR(8))
    name: Mapped[str | None] = mapped_column(sa.NVARCHAR(80))
    rack_type: Mapped[StorageRackType] = mapped_column(sa.NVARCHAR(20), server_default=sa.text("'Rack'"))
    levels: Mapped[int] = mapped_column(sa.SmallInteger())
    positions: Mapped[int] = mapped_column(sa.SmallInteger())
    max_weight_kg: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 2))
    is_blocked: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("0"))
    blocked_reason: Mapped[str | None] = mapped_column(sa.NVARCHAR(200))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("1"))
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


ScanResolvedType = Literal["Item", "Lot", "Bin", "Rack", "Location", "Many", "Unknown"]


class ScanLog(Base):
    """A scanned or typed code that was looked up (migration 0052). Insert-only."""

    __tablename__ = "scan_log"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    scanned_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
    user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    scanned_value: Mapped[str] = mapped_column(sa.NVARCHAR(100))
    resolved_type: Mapped[ScanResolvedType] = mapped_column(sa.NVARCHAR(10))
    resolved_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    match_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    screen: Mapped[str | None] = mapped_column(sa.NVARCHAR(40))


class ItemStorageRule(Audited, Base):
    """An item's home bin in a location, with optional min / max (migration 0053)."""

    __tablename__ = "item_storage_rule"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    item_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.item.id"))
    location_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.location.id"))
    bin_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.bin.id"))
    min_qty: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 3))
    max_qty: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 3))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("1"))
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


BinMoveType = Literal["Put-away", "Bin move"]


class BinMove(Base):
    """Stock moved between bins of one location, posted at once (migration 0053). The stock_move rows are the
    ledger; this keeps who moved what together, and its number."""

    __tablename__ = "bin_move"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    move_no: Mapped[str | None] = mapped_column(sa.NVARCHAR(20))
    location_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.location.id"))
    move_type: Mapped[BinMoveType] = mapped_column(sa.NVARCHAR(12))
    note: Mapped[str | None] = mapped_column(sa.NVARCHAR(200))
    moved_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    moved_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))


class BinMoveLine(Base):
    """One item (and batch) moved from a bin (or from no bin) to a bin."""

    __tablename__ = "bin_move_line"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    bin_move_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.bin_move.id"))
    item_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.item.id"))
    stock_lot_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.stock_lot.id"))
    from_bin_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.bin.id"))
    to_bin_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.bin.id"))
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(18, 3))


class StockCountBin(Base):
    """A bin of a stock count whose scope is a list of bins."""

    __tablename__ = "stock_count_bin"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    stock_count_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.stock_count.id"))
    bin_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.bin.id"))
