"""Physical stock counts (/inv/stock-counts): count sheets, counting, finishing, posting the differences."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.errors import NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.inv.common import STOCK_VIEW
from trishul_api.modules.inv.count_schemas import (
    StockCountClose,
    StockCountCreate,
    StockCountEntry,
    StockCountLineOut,
    StockCountOut,
    StockCountQuery,
)
from trishul_api.modules.inv.count_service import COUNT_APPROVE, COUNT_MANAGE, StockCountService

router = APIRouter(prefix="/inv", tags=["stock-counts"])

CAN_READ = Depends(require_permission(COUNT_MANAGE, COUNT_APPROVE, STOCK_VIEW))
CAN_COUNT = Depends(require_permission(COUNT_MANAGE))
CAN_POST = Depends(require_permission(COUNT_APPROVE))
CountId = Annotated[int, Path(alias="countId", gt=0)]


def _service(db: DbSession, actor: CurrentUserDep) -> StockCountService:
    return StockCountService(db, actor)


Counts = Annotated[StockCountService, Depends(_service)]


@router.get("/stock-counts", summary="Stock counts, newest first", dependencies=[CAN_READ])
def list_stock_counts(query: Annotated[StockCountQuery, Query()], counts: Counts) -> Page[StockCountOut]:
    return counts.search(query)


@router.post(
    "/stock-counts",
    summary="Start a count of a location, a rack or a list of bins (lines for the stock there now)",
    status_code=201,
    dependencies=[CAN_COUNT],
)
def create_stock_count(data: StockCountCreate, counts: Counts, response: Response) -> StockCountOut:
    created = counts.create(data)
    response.headers["Location"] = f"/api/v1/inv/stock-counts/{created.id}"
    return created


@router.get(
    "/stock-counts/{countId}",
    summary="One count with its lines (system quantities hidden while a blind count is open)",
    dependencies=[CAN_READ],
    responses=NOT_FOUND_RESPONSE,
)
def get_stock_count(count_id: CountId, counts: Counts) -> StockCountOut:
    return counts.get(count_id)


@router.post(
    "/stock-counts/{countId}/lines",
    summary="Record a counted quantity of an item in a bin (set it, or add to it when scanning)",
    dependencies=[CAN_COUNT],
    responses=NOT_FOUND_RESPONSE,
)
def record_stock_count_line(count_id: CountId, data: StockCountEntry, counts: Counts) -> StockCountLineOut:
    return counts.count(count_id, data)


@router.post(
    "/stock-counts/{countId}/close",
    summary="Finish counting; the differences can then be reviewed and posted",
    dependencies=[CAN_COUNT],
    responses=NOT_FOUND_RESPONSE,
)
def close_stock_count(count_id: CountId, data: StockCountClose, counts: Counts) -> StockCountOut:
    return counts.close(count_id, data)


@router.post(
    "/stock-counts/{countId}/reopen",
    summary="Go back to counting",
    dependencies=[CAN_COUNT],
    responses=NOT_FOUND_RESPONSE,
)
def reopen_stock_count(count_id: CountId, counts: Counts) -> StockCountOut:
    return counts.reopen(count_id)


@router.post(
    "/stock-counts/{countId}/cancel",
    summary="Cancel a count that was not posted",
    dependencies=[CAN_COUNT],
    responses=NOT_FOUND_RESPONSE,
)
def cancel_stock_count(count_id: CountId, counts: Counts) -> StockCountOut:
    return counts.cancel(count_id)


@router.post(
    "/stock-counts/{countId}/post",
    summary="Post the differences as one stock adjustment (reason Count difference)",
    dependencies=[CAN_POST],
    responses=NOT_FOUND_RESPONSE,
)
def post_stock_count(count_id: CountId, counts: Counts) -> StockCountOut:
    return counts.post(count_id)
