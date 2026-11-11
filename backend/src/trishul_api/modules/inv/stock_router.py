from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.errors import NOT_FOUND_RESPONSE, problem_response
from trishul_api.common.schemas import Page
from trishul_api.modules.inv.common import GRN_MANAGE, STOCK_ADJUST, STOCK_USERS, STOCK_VIEW, TRANSFER_MANAGE
from trishul_api.modules.inv.doc_schemas import (
    AdjustmentCreate,
    AdjustmentDetail,
    AdjustmentListItem,
    DocumentQuery,
    LotListItem,
    LotQuery,
    OpeningStockCreate,
    TransferCreate,
    TransferDetail,
    TransferListItem,
)
from trishul_api.modules.inv.doc_service import DocumentService
from trishul_api.modules.inv.stock_schemas import (
    AgeingQuery,
    AgeingReport,
    MovementQuery,
    MovementRow,
    StockQuery,
    StockRow,
)
from trishul_api.modules.inv.stock_service import StockService

router = APIRouter(prefix="/inv", tags=["stock"])

# Anyone who moves stock may also look at it (to pick a batch or check what is there).
CAN_VIEW_STOCK = Depends(require_permission(*STOCK_USERS))
CAN_REPORT = Depends(require_permission(STOCK_VIEW))
CAN_RECEIVE = Depends(require_permission(GRN_MANAGE))
CAN_TRANSFER = Depends(require_permission(TRANSFER_MANAGE))
CAN_SEE_TRANSFERS = Depends(require_permission(TRANSFER_MANAGE, STOCK_VIEW))
CAN_ADJUST = Depends(require_permission(STOCK_ADJUST))
CAN_SEE_ADJUSTMENTS = Depends(require_permission(STOCK_ADJUST, STOCK_VIEW))

POSTING_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: problem_response("Stock changed while the document was being saved; try again.")
}


def _documents(db: DbSession, actor: CurrentUserDep) -> DocumentService:
    return DocumentService(db, actor)


def _stock(db: DbSession, actor: CurrentUserDep) -> StockService:
    return StockService(db, actor)


Documents = Annotated[DocumentService, Depends(_documents)]
Stock = Annotated[StockService, Depends(_stock)]


# ---------------------------------------------------------------- stock and reports


@router.get("/stock", summary="Stock on hand by GRN batch, location and rack", dependencies=[CAN_VIEW_STOCK])
def list_stock(query: Annotated[StockQuery, Query()], scope: ScopeDep, stock: Stock) -> Page[StockRow]:
    return stock.stock(scope, query)


@router.get(
    "/reports/ageing",
    summary="Inventory ageing from GRN dates, in 0-30 / 31-60 / 61-90 / 91-180 / 180+ day buckets",
    dependencies=[CAN_REPORT],
)
def get_ageing_report(query: Annotated[AgeingQuery, Query()], scope: ScopeDep, stock: Stock) -> AgeingReport:
    return stock.ageing(scope, query)


@router.get("/movements", summary="Stock movements (the ledger), newest first", dependencies=[CAN_REPORT])
def list_movements(query: Annotated[MovementQuery, Query()], stock: Stock) -> Page[MovementRow]:
    return stock.movements(query)


@router.get("/lots", summary="GRN batches: received quantity, GRN date and what is left", dependencies=[CAN_VIEW_STOCK])
def list_lots(query: Annotated[LotQuery, Query()], documents: Documents) -> Page[LotListItem]:
    return documents.lots(query)


# ---------------------------------------------------------------- opening stock


@router.post(
    "/opening-stock",
    summary="Enter stock on hand at go-live with its original GRN number and date",
    status_code=201,
    dependencies=[CAN_RECEIVE],
    responses=POSTING_RESPONSES,
)
def create_opening_stock(data: OpeningStockCreate, documents: Documents) -> list[LotListItem]:
    return documents.create_opening(data)


# ---------------------------------------------------------------- transfers


@router.get("/transfers", summary="Stock transfers, newest first", dependencies=[CAN_SEE_TRANSFERS])
def list_transfers(query: Annotated[DocumentQuery, Query()], documents: Documents) -> Page[TransferListItem]:
    return documents.transfers(query)


@router.get(
    "/transfers/{transferId}",
    summary="One transfer with the GRN batches it moved",
    dependencies=[CAN_SEE_TRANSFERS],
    responses=NOT_FOUND_RESPONSE,
)
def get_transfer(transfer_id: Annotated[int, Path(alias="transferId", gt=0)], documents: Documents) -> TransferDetail:
    return documents.transfer(transfer_id)


@router.post(
    "/transfers",
    summary="Transfer stock between branches, warehouses or racks; GRN dates are kept",
    status_code=201,
    dependencies=[CAN_TRANSFER],
    responses=POSTING_RESPONSES,
)
def create_transfer(data: TransferCreate, documents: Documents, response: Response) -> TransferDetail:
    created = documents.create_transfer(data)
    response.headers["Location"] = f"transfers/{created.id}"
    return created


# ---------------------------------------------------------------- adjustments


@router.get("/adjustments", summary="Stock adjustments, newest first", dependencies=[CAN_SEE_ADJUSTMENTS])
def list_adjustments(query: Annotated[DocumentQuery, Query()], documents: Documents) -> Page[AdjustmentListItem]:
    return documents.adjustments(query)


@router.get(
    "/adjustments/{adjustmentId}",
    summary="One adjustment with the GRN batches it changed",
    dependencies=[CAN_SEE_ADJUSTMENTS],
    responses=NOT_FOUND_RESPONSE,
)
def get_adjustment(
    adjustment_id: Annotated[int, Path(alias="adjustmentId", gt=0)], documents: Documents
) -> AdjustmentDetail:
    return documents.adjustment(adjustment_id)


@router.post(
    "/adjustments",
    summary="Increase or decrease stock with a reason (posted by the signed-in user)",
    status_code=201,
    dependencies=[CAN_ADJUST],
    responses=POSTING_RESPONSES,
)
def create_adjustment(data: AdjustmentCreate, documents: Documents, response: Response) -> AdjustmentDetail:
    created = documents.create_adjustment(data)
    response.headers["Location"] = f"adjustments/{created.id}"
    return created
