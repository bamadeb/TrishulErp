from typing import Annotated

from fastapi import APIRouter, Depends, Query

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.errors import Forbidden
from trishul_api.common.schemas import Page
from trishul_api.modules.presales.repository import SalesActivityRepository
from trishul_api.modules.presales.schemas import AssignedSalesActivityListItem, AssignedSalesActivityQuery

router = APIRouter(prefix="/pre", tags=["presales"])


def get_sales_activity_repository(db: DbSession) -> SalesActivityRepository:
    return SalesActivityRepository(db)


SalesActivityRepo = Annotated[SalesActivityRepository, Depends(get_sales_activity_repository)]


@router.get(
    "/sales-activities/assigned-to-me",
    summary="Sales activities assigned to the signed-in salesperson",
    dependencies=[Depends(require_permission("pre.activity.view.assigned"))],
)
def list_assigned_sales_activities(
    query: Annotated[AssignedSalesActivityQuery, Query()],
    user: CurrentUserDep,
    repo: SalesActivityRepo,
) -> Page[AssignedSalesActivityListItem]:
    if user.employee_id is None:
        raise Forbidden("Your account is not linked to an employee, so it has no assigned activities.")
    return repo.list_assigned(user.employee_id, query)
