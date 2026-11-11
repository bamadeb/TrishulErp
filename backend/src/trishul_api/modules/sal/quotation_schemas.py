import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import QuotationQuotationType
from trishul_api.modules.sal.lines import MONEY, PricedLineIn, PricedLineOut

#: What the screens show: the stored status, with a submitted quotation past its validity shown as Expired.
QuotationState = Literal["Draft", "Pending approval", "Submitted", "Accepted", "Rejected", "Expired", "Converted"]


class QuotationQuery(PageQuery):
    state: QuotationState | None = None
    customer_id: int | None = None
    branch_id: int | None = None
    from_date: dt.date | None = None
    to_date: dt.date | None = None


class QuotationCreate(InputModel):
    principal_id: int = Field(description="Brand: one brand per quotation.")
    branch_id: int
    customer_id: int
    customer_site_id: int | None = Field(None, description="The customer's branch.")
    quotation_type: QuotationQuotationType = "Parts"
    quotation_date: dt.date | None = Field(None, description="Default today.")
    valid_until: dt.date | None = Field(None, description="Default 30 days from the quotation date.")
    other_charges: Decimal = MONEY
    terms: str | None = Field(None, max_length=2000)
    remarks: str | None = Field(None, max_length=500)
    lines: list[PricedLineIn] = Field(min_length=1, max_length=200)


class QuotationNote(InputModel):
    note: str | None = Field(None, max_length=300, description="Why (needed to reject or revise).")


class ConvertQuotation(InputModel):
    customer_po_no: str | None = Field(None, max_length=40)
    customer_po_date: dt.date | None = None
    expected_delivery_date: dt.date | None = None
    is_prepaid: bool = False


class QuotationListItem(ApiModel):
    id: int
    quotation_no: str
    quotation_date: dt.date
    valid_until: dt.date | None
    customer_id: int
    customer_name: str
    customer_site_name: str | None
    branch_name: str
    principal_name: str
    status: str
    state: QuotationState
    current_version: int
    total: Decimal
    created_at: UtcDateTime


class QuotationVersionOut(ApiModel):
    version_no: int
    total: Decimal
    change_note: str | None
    created_at: UtcDateTime
    created_by: str | None


class QuotationDetail(QuotationListItem):
    principal_id: int
    branch_id: int
    customer_site_id: int | None
    quotation_type: QuotationQuotationType
    company_name: str
    company_address: str | None
    branch_address: str | None
    customer_code: str
    customer_gstin: str | None
    customer_address: str | None
    customer_phone: str | None
    place_of_supply: str
    subtotal: Decimal = Field(description="Before discount.")
    discount_total: Decimal
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    tax_total: Decimal
    other_charges: Decimal
    terms: str | None
    remarks: str | None
    created_by: str | None
    submitted_by: str | None
    submitted_at: UtcDateTime | None
    approved_by: str | None
    approved_at: UtcDateTime | None
    responded_by: str | None
    responded_at: UtcDateTime | None
    response_note: str | None
    sales_order_id: int | None
    order_no: str | None
    needs_discount_approval: bool
    lines: list[PricedLineOut]
    versions: list[QuotationVersionOut]
    row_version: RowVersion
