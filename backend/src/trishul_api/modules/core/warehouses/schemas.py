from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion


class WarehouseOut(ApiModel):
    """A warehouse: a core.branch row of type Warehouse."""

    id: int
    code: str
    name: str
    is_active: bool
    branch_count: int = Field(description="Active branches this warehouse supplies.")
    row_version: RowVersion


class WarehouseBranch(ApiModel):
    """A branch or service point, and the warehouse that supplies it (if any)."""

    id: int
    code: str
    name: str
    branch_type: str
    warehouse_id: int | None
    is_active: bool
    row_version: RowVersion


class WarehouseMap(ApiModel):
    warehouses: list[WarehouseOut]
    branches: list[WarehouseBranch]


class WarehouseCreate(InputModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=120)


class WarehouseUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=10)
    name: str | None = Field(None, min_length=1, max_length=120)
    is_active: bool | None = None


class BranchWarehouseUpdate(InputModel):
    warehouse_id: int | None = Field(description="The supplying warehouse; null for none.")
