from pydantic import Field

from trishul_api.common.schemas import ApiModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import SalesActivityActivityType

# Activity types come from the pre.sales_activity CHECK constraint, through the generated model.
ActivityType = SalesActivityActivityType

# Field activities an engineer/salesperson actually travels for; the default list excludes desk work.
FIELD_ACTIVITY_TYPES: tuple[ActivityType, ...] = ("Visit", "Demo", "Meeting")


class AssignedSalesActivityQuery(PageQuery):
    """Filter for the mobile 'my activities' list. No employee parameter: it is the signed-in user,
    so the client cannot widen the result to other salespeople's activities."""

    activity_type: list[ActivityType] = Field(default_factory=list)


class AssignedSalesActivityListItem(ApiModel):
    id: int
    activity_type: ActivityType
    customer_name: str | None
    lead_name: str | None
    planned_at: UtcDateTime | None
    started_at: UtcDateTime | None
    ended_at: UtcDateTime | None
    notes: str | None
    next_follow_up_at: UtcDateTime | None
    row_version: RowVersion
