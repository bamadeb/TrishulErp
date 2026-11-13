import datetime as dt
from decimal import Decimal

from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime
from trishul_api.db.models.generated.svc import ServicePartRequestRequestChannel, ServicePartRequestStatus
from trishul_api.modules.sal.quotation_schemas import QuotationCreate


class PartRequestLineInput(InputModel):
    """One part asked for: an item from the item master, or a description when the part isn't in it."""

    item_id: int | None = Field(None, gt=0, description="The part from the item master (GET /inv/items).")
    part_description: str | None = Field(
        None, max_length=200, description="What the part is, when it isn't in the item master."
    )
    quantity: Decimal = Field(gt=0, max_digits=15, decimal_places=3)
    uom_id: int | None = Field(None, gt=0, description="Unit; defaults to the item's stock unit.")
    is_chargeable: bool = Field(True, description="Charged to the customer (false: warranty / ASC).")

    @model_validator(mode="after")
    def _item_or_description(self) -> "PartRequestLineInput":
        if self.item_id is None and not self.part_description:
            raise ValueError("Choose an item or describe the part.")
        return self


class PartRequestCreate(InputModel):
    """The parts an engineer needs for a call, all sent at once."""

    service_visit_id: int | None = Field(None, gt=0, description="The visit the parts were found missing on.")
    required_by_date: dt.date | None = Field(None, description="When the parts are needed on site.")
    parts: list[PartRequestLineInput] = Field(min_length=1, max_length=50)


class PartRequestOut(ApiModel):
    """One requested part on a call."""

    id: int
    service_call_id: int
    call_no: str
    service_visit_id: int | None
    item_id: int | None
    item_code: str | None
    oem_part_number: str | None
    part_description: str | None = Field(description="The item's description, or the one the engineer typed.")
    quantity: Decimal
    uom_id: int | None
    uom_code: str | None
    is_chargeable: bool
    status: ServicePartRequestStatus
    request_channel: ServicePartRequestRequestChannel | None
    requested_by_employee_id: int | None
    required_by_date: dt.date | None
    created_at: UtcDateTime


class PartRequestListItem(PartRequestOut):
    """A requested part with its call, customer, who asked and what the office did with it."""

    branch_id: int
    branch_name: str
    principal_id: int
    principal_name: str
    customer_id: int
    customer_name: str
    call_status: str
    requested_by_name: str | None
    quotation_id: int | None
    quotation_no: str | None
    review_note: str | None
    reviewed_at: UtcDateTime | None
    reviewed_by: str | None


class PartRequestQuery(PageQuery):
    """search: call no, customer, item code or part description."""

    status: ServicePartRequestStatus | None = None
    branch_id: int | None = None
    customer_id: int | None = None
    service_call_id: int | None = None
    from_date: dt.date | None = Field(None, description="Requested on or after (UTC date).")
    to_date: dt.date | None = Field(None, description="Requested on or before (UTC date).")


class WarehouseStock(ApiModel):
    branch_id: int
    branch_name: str
    qty_available: Decimal
    supplies_call_branch: bool = Field(description="This warehouse supplies the call's branch (or is it).")


class PartAvailability(ApiModel):
    """Stock of one part for a call: in the warehouse that supplies the call's branch, and elsewhere.
    Quantities only (no costs)."""

    item_id: int
    item_code: str
    description: str
    uom_code: str
    supplying_warehouse_id: int | None = Field(description="The warehouse that supplies the call's branch.")
    supplying_warehouse_name: str | None
    qty_in_supplying_warehouse: Decimal = Field(description="What the engineer can get from their own warehouse.")
    qty_elsewhere: Decimal = Field(description="In the other warehouses (needs a transfer).")
    total_available: Decimal
    warehouses: list[WarehouseStock] = Field(
        description="Every warehouse holding the part: the supplying one first, then the most stock first."
    )


class PartRequestCall(ApiModel):
    """A service call with the parts requested on it (one engineer or several)."""

    service_call_id: int
    call_no: str
    call_status: str
    branch_id: int
    branch_name: str
    principal_id: int
    principal_name: str
    customer_id: int
    customer_name: str
    last_requested_at: UtcDateTime
    required_by_date: dt.date | None = Field(description="The earliest date any of the parts is needed by.")
    waiting: int = Field(description="Parts still Requested (not yet quoted or rejected).")
    requested_by: list[str] = Field(description="The engineers who asked.")
    parts: list[PartRequestListItem] = Field(description="The call's parts that match the filters, oldest first.")


class PartRequestReject(InputModel):
    note: str = Field(min_length=1, max_length=300, description="Why the parts are not supplied.")


class PartRequestDraftLine(ApiModel):
    part_request_id: int
    item_id: int | None
    description: str | None
    quantity: Decimal
    unit_price: Decimal = Field(description="Price list, else MRP, else 0.")
    discount_pct: Decimal
    gst_pct: Decimal = Field(description="From the item's HSN, else 18.")


class PartRequestQuotationDraft(ApiModel):
    """What a quotation for the requested parts would be: for the user to check and change before saving it."""

    part_request_ids: list[int]
    call_nos: list[str]
    customer_id: int
    principal_id: int
    branch_id: int
    remarks: str
    lines: list[PartRequestDraftLine]


class PartRequestQuotationCreate(QuotationCreate):
    """The quotation the user checked (POST /sal/quotations body) plus the parts it quotes, which become Quoted.
    The parts must be of the quotation's customer and brand."""

    part_request_ids: list[int] = Field(min_length=1, max_length=200)


class PartRequestQuotationOut(ApiModel):
    quotation_id: int
    quotation_no: str
    parts: list[PartRequestListItem] = Field(description="The parts, now Quoted.")
