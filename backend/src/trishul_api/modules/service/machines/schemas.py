import datetime as dt
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.generated.core import MachineModelProductLine, MachineUnitStatus

MachineStatusFilter = Literal["active", "inactive", "all"]


class MachineQuery(PageQuery):
    status: MachineStatusFilter = "active"
    customer_id: int | None = None
    model_id: int | None = None


class MachineListItem(ApiModel):
    id: int
    serial_number: str
    model_id: int
    model_code: str
    model_name: str
    product_line: MachineModelProductLine
    customer_id: int | None
    customer_code: str | None
    customer_name: str | None
    status: MachineUnitStatus
    warranty_end_date: dt.date | None
    current_hmr: float | None
    is_active: bool
    created_at: UtcDateTime


class MachineDetail(MachineListItem):
    principal_id: int
    principal_code: str
    engine_number: str | None
    registration_number: str | None
    year_of_manufacture: int | None
    sale_date: dt.date | None
    commissioning_date: dt.date | None
    warranty_start_date: dt.date | None
    oem_registered_product_id: str | None
    row_version: RowVersion


class MachineCreate(InputModel):
    serial_number: str = Field(min_length=1, max_length=40, description="Unique across all machines.")
    model_id: int = Field(description="The brand is taken from the model.")
    customer_id: int = Field(description="The customer who owns the machine.")
    status: MachineUnitStatus = "Sold"
    engine_number: str | None = Field(None, max_length=40)
    registration_number: str | None = Field(None, max_length=20)
    year_of_manufacture: int | None = Field(None, ge=1950, le=2100)
    sale_date: dt.date | None = None
    commissioning_date: dt.date | None = None
    warranty_start_date: dt.date | None = None
    warranty_end_date: dt.date | None = None
    oem_registered_product_id: str | None = Field(None, max_length=40)


class MachineUpdate(InputModel):
    """Only the fields sent are changed. The owner can be changed but not removed."""

    serial_number: str | None = Field(None, min_length=1, max_length=40)
    model_id: int | None = None
    customer_id: int | None = None
    status: MachineUnitStatus | None = None
    engine_number: str | None = Field(None, max_length=40)
    registration_number: str | None = Field(None, max_length=20)
    year_of_manufacture: int | None = Field(None, ge=1950, le=2100)
    sale_date: dt.date | None = None
    commissioning_date: dt.date | None = None
    warranty_start_date: dt.date | None = None
    warranty_end_date: dt.date | None = None
    oem_registered_product_id: str | None = Field(None, max_length=40)


class MachineModelOption(ApiModel):
    id: int
    model_code: str
    model_name: str
    product_line: MachineModelProductLine


class MachineFormOptions(ApiModel):
    """Everything the add/edit machine form needs: the active models of the selected brand."""

    models: list[MachineModelOption]
