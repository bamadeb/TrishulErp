"""Holiday calendar requests and responses. JSON is camelCase."""

from datetime import date
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion

HolidayCategory = Literal["National", "Regional", "Optional"]


class HolidayListQuery(PageQuery):
    financial_year: int | None = Field(None, ge=2000, le=2100)
    calendar_year: int | None = Field(None, ge=2000, le=2100)
    holiday_category: HolidayCategory | None = None
    state_id: int | None = Field(None, gt=0)
    location_id: int | None = Field(None, gt=0)
    active_only: bool = True


class HolidaySummaryQuery(ApiModel):
    financial_year: int | None = Field(None, ge=2000, le=2100)
    calendar_year: int | None = Field(None, ge=2000, le=2100)
    holiday_category: HolidayCategory | None = None
    state_id: int | None = Field(None, gt=0)
    location_id: int | None = Field(None, gt=0)
    search: str | None = Field(None, max_length=100)
    active_only: bool = True


class HolidayCalendarQuery(HolidaySummaryQuery):
    start_date: date
    end_date: date


class HolidayWrite(InputModel):
    name: str = Field(min_length=1, max_length=80)
    holiday_date: date
    category: HolidayCategory
    state_id: int | None = Field(None, gt=0)
    location_id: int | None = Field(None, gt=0)
    description: str | None = Field(None, max_length=400)
    is_active: bool = True


class HolidayItem(ApiModel):
    id: int
    name: str
    holiday_date: date
    day: str
    category: HolidayCategory
    state_id: int | None
    state_name: str | None
    location_id: int | None
    location_name: str
    description: str | None
    optional: bool
    is_active: bool
    source_notification_no: str | None
    source_notification_date: date | None
    row_version: RowVersion


class HolidaySummary(ApiModel):
    total: int
    upcoming: int
    national: int
    regional: int
    optional: int


class HolidayOption(ApiModel):
    id: int
    name: str
    state_id: int | None = None


class HolidayCategoryOption(ApiModel):
    id: HolidayCategory
    name: str


class HolidayFilters(ApiModel):
    categories: list[HolidayCategoryOption]
    states: list[HolidayOption]
    locations: list[HolidayOption]
    financial_years: list[int]
