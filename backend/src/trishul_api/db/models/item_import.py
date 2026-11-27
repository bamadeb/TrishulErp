# Hand-written until the model generator is re-run. Keep these columns in step with
# migration 0049_item_list_import.

"""Item list import: one batch per uploaded file and one line per row of it."""

import datetime as dt
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Audited, Base

ItemImportStatus = Literal["Pending", "Processing", "Completed", "Partially Completed", "Failed"]
ItemImportDuplicateMode = Literal["Skip", "Update"]
ItemImportLineAction = Literal["Create", "Update", "Skip", "Error"]
ItemImportLineOutcome = Literal["Created", "Updated", "Skipped", "Failed"]


class ItemImport(Audited, Base):
    """One uploaded item list: the file, who uploaded and confirmed it, and what it did."""

    __tablename__ = "item_import"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    batch_no: Mapped[str | None] = mapped_column(sa.NVARCHAR(20))
    company_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.company.id"))
    file_name: Mapped[str] = mapped_column(sa.NVARCHAR(260))
    file_key: Mapped[str | None] = mapped_column(sa.NVARCHAR(400))
    file_size: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    duplicate_mode: Mapped[ItemImportDuplicateMode] = mapped_column(sa.NVARCHAR(10), server_default=sa.text("'Skip'"))
    status: Mapped[ItemImportStatus] = mapped_column(sa.NVARCHAR(20), server_default=sa.text("'Pending'"))
    total_rows: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    valid_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    created_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    updated_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    failed_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    skipped_count: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.text("0"))
    error_message: Mapped[str | None] = mapped_column(sa.NVARCHAR(1000))
    uploaded_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    uploaded_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
    confirmed_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    completed_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))


class ItemImportLine(Base):
    """One row of an uploaded item list: what the check planned and what the import did."""

    __tablename__ = "item_import_line"
    __table_args__ = {"schema": "inv"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    import_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("inv.item_import.id"))
    row_number: Mapped[int] = mapped_column(sa.Integer())
    item_code: Mapped[str | None] = mapped_column(sa.NVARCHAR(60))
    description: Mapped[str | None] = mapped_column(sa.NVARCHAR(200))
    action: Mapped[ItemImportLineAction] = mapped_column(sa.NVARCHAR(10))
    outcome: Mapped[ItemImportLineOutcome | None] = mapped_column(sa.NVARCHAR(10))
    item_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.item.id"))
    messages: Mapped[str | None] = mapped_column(sa.NVARCHAR(None))
    changes: Mapped[str | None] = mapped_column(sa.NVARCHAR(None))
    source_data: Mapped[str | None] = mapped_column(sa.NVARCHAR(None))
