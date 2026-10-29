from typing import Literal

from pydantic import EmailStr, Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.generated.core import (
    CustomerCustomerType,
    CustomerGstRegistrationType,
    CustomerPriorityTier,
)
from trishul_api.modules.core.employees.schemas import CompanyOption  # reused: company picker shape

__all__ = [
    "CompanyOption",
    "CustomerCreate",
    "CustomerDetail",
    "CustomerFormOptions",
    "CustomerListItem",
    "CustomerQuery",
    "CustomerStatusFilter",
    "CustomerUpdate",
    "StateOption",
]

CustomerStatusFilter = Literal["active", "inactive", "all"]

# A phone or landline: digits, with optional +, spaces, hyphens or brackets. The column holds 15 chars.
PHONE_PATTERN = r"^[0-9+\-() ]{6,15}$"


class CustomerQuery(PageQuery):
    status: CustomerStatusFilter = "active"
    customer_type: CustomerCustomerType | None = None
    priority_tier: CustomerPriorityTier | None = None


class CustomerListItem(ApiModel):
    id: int
    code: str
    name: str
    customer_type: CustomerCustomerType
    primary_phone: str
    email: str | None
    gstin: str | None
    billing_state_id: int | None
    billing_state_name: str | None
    priority_tier: CustomerPriorityTier | None
    is_asc_customer: bool
    is_active: bool
    created_at: UtcDateTime


class CustomerDetail(CustomerListItem):
    company_id: int
    company_name: str | None
    alternate_phone: str | None
    pan: str | None
    gst_registration_type: CustomerGstRegistrationType
    billing_address: str | None
    row_version: RowVersion


class CustomerCreate(InputModel):
    code: str = Field(min_length=1, max_length=20, description="Unique across all customers.")
    name: str = Field(min_length=1, max_length=200)
    customer_type: CustomerCustomerType
    company_id: int
    primary_phone: str = Field(pattern=PHONE_PATTERN, max_length=15)
    alternate_phone: str | None = Field(None, pattern=PHONE_PATTERN, max_length=15)
    email: EmailStr | None = Field(None, max_length=120)
    pan: str | None = Field(None, max_length=10)
    gstin: str | None = Field(None, max_length=15)
    gst_registration_type: CustomerGstRegistrationType = "Unregistered"
    billing_address: str | None = Field(None, max_length=500)
    billing_state_id: int | None = None
    priority_tier: CustomerPriorityTier | None = "Normal"
    is_asc_customer: bool = False


class CustomerUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=20)
    name: str | None = Field(None, min_length=1, max_length=200)
    customer_type: CustomerCustomerType | None = None
    company_id: int | None = None
    primary_phone: str | None = Field(None, pattern=PHONE_PATTERN, max_length=15)
    alternate_phone: str | None = Field(None, pattern=PHONE_PATTERN, max_length=15)
    email: EmailStr | None = Field(None, max_length=120)
    pan: str | None = Field(None, max_length=10)
    gstin: str | None = Field(None, max_length=15)
    gst_registration_type: CustomerGstRegistrationType | None = None
    billing_address: str | None = Field(None, max_length=500)
    billing_state_id: int | None = None
    priority_tier: CustomerPriorityTier | None = None
    is_asc_customer: bool | None = None


class StateOption(ApiModel):
    id: int
    name: str
    gst_state_code: str


class CustomerFormOptions(ApiModel):
    """Everything the add/edit customer form needs, in one request."""

    companies: list[CompanyOption]
    states: list[StateOption]
