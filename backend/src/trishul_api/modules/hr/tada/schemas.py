"""TA/DA report contracts. Money stays Decimal. Device identifiers are not part of these models."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, UtcDateTime
from trishul_api.modules.hr.tada.calculation import TrkTripStatus, TrkTripVehicleType

TrkTripType = Literal["To site", "Return", "Site to site"]

ApprovalStatus = Literal["Pending", "Approved", "Rejected"]
SettlementStatus = Literal["Open", "Sent", "Paid"]
PaymentMode = Literal["Payroll", "Bank transfer", "Cash"]

_MONEY = Field(ge=0, max_digits=8, decimal_places=2)
_CAR_RATE = Field(ge=Decimal("5"), le=Decimal("6"), max_digits=4, decimal_places=2)


class TadaReportQuery(PageQuery):
    month: str | None = Field(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Payroll month, YYYY-MM.")
    company_id: int | None = Field(None, gt=0)
    branch_id: int | None = Field(None, gt=0)
    employee_id: int | None = Field(None, gt=0)
    department_id: int | None = Field(None, gt=0)
    designation_id: int | None = Field(None, gt=0)
    vehicle_type: TrkTripVehicleType | None = None
    status: TrkTripStatus | None = None


class TadaEmployeeQuery(TadaReportQuery):
    approval_status: ApprovalStatus | None = None
    settlement_status: SettlementStatus | None = None


class TadaDecisionCreate(InputModel):
    payroll_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    employee_ids: list[Annotated[int, Field(gt=0)]] = Field(min_length=1, max_length=200)
    decision: Literal["Approved", "Rejected"]
    remarks: str | None = Field(
        None,
        max_length=500,
        description="Optional approval comment, or the required rejection reason. Stored on core.status_history.remarks.",
    )

    @model_validator(mode="after")
    def _rejection_reason(self) -> "TadaDecisionCreate":
        self.remarks = (self.remarks or "").strip() or None
        if self.decision == "Rejected" and self.remarks is None:
            raise ValueError("A rejection reason is required.")
        return self


class TadaDecisionHistoryItem(ApiModel):
    id: int
    action: str
    from_status: str | None
    to_status: str
    remarks: str | None
    changed_by_user_id: int | None
    changed_by_name: str | None
    changed_at: UtcDateTime
    trip_id: int | None = None
    call_no: str | None = None


class TadaTripDecisionCreate(InputModel):
    decision: Literal["Approved", "Rejected"]
    remarks: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _rejection_reason(self) -> "TadaTripDecisionCreate":
        self.remarks = (self.remarks or "").strip() or None
        if self.decision == "Rejected" and self.remarks is None:
            raise ValueError("A rejection reason is required.")
        return self


TripReviewStatus = Literal["Pending", "Approved", "Rejected", "Sent"]


class TadaTripDocument(ApiModel):
    id: int
    source: Literal["Fare receipt", "Service call", "Service report"]
    file_name: str
    content_type: str | None = None
    category: str | None = None
    file_size_bytes: int | None = None
    verification_status: str | None = None


class TadaSettlementCreate(InputModel):
    payroll_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    employee_ids: list[Annotated[int, Field(gt=0)]] = Field(min_length=1, max_length=200)
    payment_date: date | None = None
    payment_mode: PaymentMode | None = None
    payment_reference: str | None = Field(None, max_length=40)
    remarks: str | None = Field(None, max_length=300)

    @model_validator(mode="after")
    def _payment_details(self) -> "TadaSettlementCreate":
        self.payment_reference = (self.payment_reference or "").strip() or None
        self.remarks = (self.remarks or "").strip() or None
        if self.payment_date is None and self.payment_mode is None and self.payment_reference is None:
            return self
        if self.payment_date is None or self.payment_mode is None:
            raise ValueError("Payment date and payment mode are required.")
        if self.payment_mode == "Bank transfer" and self.payment_reference is None:
            raise ValueError("A bank transfer needs a payment reference.")
        return self


class TadaBulkSkip(ApiModel):
    employee_id: int
    employee_code: str
    reason: str


class TadaBulkResult(ApiModel):
    updated: int
    skipped: list[TadaBulkSkip]


class TadaEmployeeSummary(ApiModel):
    service_engineers: int
    trips: int
    travel_km: Decimal
    bike_allowance: Decimal
    car_allowance: Decimal
    total_ta_payable: Decimal
    month: str
    note: str
    previous_service_engineers: int
    previous_trips: int
    previous_travel_km: Decimal
    previous_bike_allowance: Decimal
    previous_car_allowance: Decimal
    previous_total_payable: Decimal


class TadaEmployeeItem(ApiModel):
    employee_id: int
    employee_code: str
    employee_name: str
    designation: str | None
    total_trips: int
    bike_km: Decimal
    car_km: Decimal
    total_km: Decimal
    ta_amount: Decimal
    additional_allowance: Decimal
    total_payable: Decimal
    approval_status: ApprovalStatus
    settlement_status: SettlementStatus
    pending_trips: int = 0
    approved_trips: int = 0
    rejected_trips: int = 0


class TadaRates(ApiModel):
    bike_per_km: Decimal = Field(description="Configured own-bike rate. 2.50 until HR saves one.")
    car_per_km: Decimal | None = Field(description="Configured own-car rate. Empty until HR saves one.")
    bike_configured: bool
    car_configured: bool


class TadaRatesUpdate(InputModel):
    bike_per_km: Decimal = _MONEY
    car_per_km: Decimal = _CAR_RATE


class TadaEmployeeReport(ApiModel):
    items: list[TadaEmployeeItem]
    total: int
    page: int
    page_size: int
    summary: TadaEmployeeSummary
    rates: TadaRates


class TadaSummary(ApiModel):
    service_engineers: int
    trips: int
    travel_km: Decimal
    bike_allowance: Decimal
    car_allowance: Decimal
    total_ta_payable: Decimal
    month: str
    note: str


class TadaTripItem(ApiModel):
    id: int
    employee_code: str
    employee_name: str
    designation: str | None
    company_name: str
    branch_name: str
    trip_date: str
    trip_type: TrkTripType
    start_at: UtcDateTime
    end_at: UtcDateTime | None
    travel_from: str
    travel_to: str
    vehicle_type: TrkTripVehicleType | None
    gps_distance_km: Decimal | None
    map_distance_km: Decimal | None
    adjusted_distance_km: Decimal | None
    is_distance_adjusted: bool
    applicable_distance_km: Decimal | None
    rate_per_km: Decimal | None
    ta_amount: Decimal | None
    status: TrkTripStatus
    payable: bool
    call_id: int | None = None
    call_no: str | None = None
    complaint_description: str | None = None
    oem_call_id: str | None = None
    employee_mobile: str | None = None
    review_status: TripReviewStatus = "Pending"


class TadaAllowance(ApiModel):
    code: str
    name: str
    monthly_amount: Decimal | None


class TadaTripDetail(TadaTripItem):
    start_latitude: Decimal
    start_longitude: Decimal
    end_latitude: Decimal | None
    end_longitude: Decimal | None
    duration_minutes: int | None
    route_polyline: str | None
    allowances: list[TadaAllowance]
    allowance_note: str
    documents: list[TadaTripDocument] = []


class TadaReport(ApiModel):
    items: list[TadaTripItem]
    total: int
    page: int
    page_size: int
    summary: TadaSummary
    rates: TadaRates
