import datetime as dt
from decimal import Decimal

from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime
from trishul_api.db.models.generated.svc import ServicePartRequestRequestChannel, ServicePartRequestStatus


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


class PartRequestIds(InputModel):
    part_request_ids: list[int] = Field(min_length=1, max_length=200)


class PartRequestReject(InputModel):
    note: str = Field(min_length=1, max_length=300, description="Why the parts are not supplied.")


class PartRequestQuotationCreate(PartRequestIds):
    """Make one draft quotation from requested parts of one customer, brand and branch (usually one call).
    Prices come from the price list (else MRP, else 0) and GST from the item's HSN; edit the draft after."""

    customer_site_id: int | None = Field(None, description="The customer's branch to quote.")
    valid_until: dt.date | None = Field(None, description="Default 30 days from today.")
    remarks: str | None = Field(None, max_length=500, description="Default: the call numbers the parts are for.")


class PartRequestQuotationOut(ApiModel):
    quotation_id: int
    quotation_no: str
    parts: list[PartRequestListItem] = Field(description="The parts, now Quoted.")
