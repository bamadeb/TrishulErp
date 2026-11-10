from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion


class WarehouseCompany(ApiModel):
    """A company a warehouse or branch can belong to."""

    id: int
    code: str
    name: str


class WarehouseOut(ApiModel):
    """A warehouse: a core.branch row of type Warehouse."""

    id: int
    code: str
    name: str
    company_id: int
    company_name: str | None
    is_active: bool
    branch_count: int = Field(description="Active branches this warehouse supplies.")
    row_version: RowVersion


class WarehouseBranch(ApiModel):
    """A branch or service point, and the warehouse that supplies it (if any)."""

    id: int
    code: str
    name: str
    branch_type: str
    company_id: int
    company_name: str | None
    warehouse_id: int | None
    is_active: bool
    row_version: RowVersion


class WarehouseMap(ApiModel):
    warehouses: list[WarehouseOut]
    branches: list[WarehouseBranch]
    companies: list[WarehouseCompany]


class WarehouseCreate(InputModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=120)
    company_id: int | None = Field(
        None, gt=0, description="The company it belongs to; blank = the head office's company."
    )


class WarehouseUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=10)
    name: str | None = Field(None, min_length=1, max_length=120)
    company_id: int | None = Field(None, gt=0, description="Move the warehouse to another company.")
    is_active: bool | None = None


class BranchWarehouseUpdate(InputModel):
    warehouse_id: int | None = Field(description="The supplying warehouse; null for none.")


class WarehouseBranchCreate(InputModel):
    """A new branch (or service point), optionally supplied by a warehouse straight away."""

    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=120)
    branch_type: Literal["Branch", "Service point"] = "Branch"
    warehouse_id: int | None = Field(None, gt=0, description="The supplying warehouse; blank for none yet.")
    company_id: int | None = Field(
        None, gt=0, description="The company it belongs to; blank = the warehouse's company."
    )
