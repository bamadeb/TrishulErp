# Hand-written until the model generator is re-run. Keep these columns in step with
# migration 0050_price_import.

"""Bulk item price import (batches and their rows) and the add-only item price change history."""

import datetime as dt
from decimal import Decimal
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Audited, Base

PriceImportStatus = Literal[
    "Pending", "Pending approval", "Processing", "Completed", "Partially Completed", "Failed", "Rejected"
]
PriceImportLayout = Literal["Template", "SAP"]
PriceField = Literal["Selling", "Purchase", "MRP"]
PriceImportLineAction = Literal["Change", "Unchanged", "Duplicate", "Error"]
PriceImportLineOutcome = Literal["Updated", "Unchanged", "Skipped", "Failed"]
PriceChangeSource = Literal["Import", "Manual"]


class PriceImport(Audited, Base):
    """One uploaded price file and what became of it."""

    __tablename__ = "price_import"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    batch_no: Mapped[str | None] = mapped_column(sa.NVARCHAR(20))
    company_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.company.id"))
    file_name: Mapped[str] = mapped_column(sa.NVARCHAR(260))
    file_key: Mapped[str | None] = mapped_column(sa.NVARCHAR(400))
    file_size: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    file_hash: Mapped[str] = mapped_column(sa.CHAR(64))
    file_layout: Mapped[PriceImportLayout] = mapped_column(sa.NVARCHAR(10), server_default=sa.text("'Template'"))
    price_list_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("sal.price_list.id"))
    principal_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.principal.id"))
    sap_price_field: Mapped[PriceField | None] = mapped_column(sa.NVARCHAR(10))
    reason: Mapped[str] = mapped_column(sa.NVARCHAR(300))
    status: Mapped[PriceImportStatus] = mapped_column(sa.NVARCHAR(20), server_default=sa.text("'Pending'"))
    max_change_pct: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 2))
    total_rows: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    valid_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    invalid_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    duplicate_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    changed_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    unchanged_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    over_limit_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    updated_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    failed_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    skipped_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    error_message: Mapped[str | None] = mapped_column(sa.NVARCHAR(1000))
    uploaded_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    uploaded_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
    confirmed_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    approved_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    approved_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    rejected_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    rejected_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    decision_note: Mapped[str | None] = mapped_column(sa.NVARCHAR(500))
    completed_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))


class PriceImportLine(Base):
    """One row of a price file: the item, its current and new prices, and the outcome."""

    __tablename__ = "price_import_line"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    import_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.price_import.id"))
    row_number: Mapped[int] = mapped_column(sa.Integer())
    item_code: Mapped[str | None] = mapped_column(sa.NVARCHAR(60))
    item_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.item.id"))
    item_name: Mapped[str | None] = mapped_column(sa.NVARCHAR(200))
    action: Mapped[PriceImportLineAction] = mapped_column(sa.NVARCHAR(10))
    outcome: Mapped[PriceImportLineOutcome | None] = mapped_column(sa.NVARCHAR(10))
    old_selling: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    new_selling: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    old_purchase: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    new_purchase: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    old_mrp: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 2))
    new_mrp: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 2))
    max_change_pct: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 2))
    over_limit: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.text("0"))
    reason: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    messages: Mapped[str | None] = mapped_column(sa.NVARCHAR(None))
    source_data: Mapped[str | None] = mapped_column(sa.NVARCHAR(None))


class ItemPriceHistory(Base):
    """One price change of an item. Add-only: never updated or deleted."""

    __tablename__ = "item_price_history"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    item_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.item.id"))
    item_code: Mapped[str] = mapped_column(sa.NVARCHAR(40))
    price_list_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("sal.price_list.id"))
    min_qty: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 3))
    old_selling: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    new_selling: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    old_purchase: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    new_purchase: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 4))
    old_mrp: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 2))
    new_mrp: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 2))
    source: Mapped[PriceChangeSource] = mapped_column(sa.NVARCHAR(10))
    import_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.price_import.id"))
    reason: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    changed_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    changed_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
