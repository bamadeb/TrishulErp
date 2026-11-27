"""Put-away and bin moves (/inv/putaway, /inv/bin-moves) and an item's storage type and home bins."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.inv.binmove_schemas import (
    BinMoveCreate,
    BinMoveOut,
    BinMoveQuery,
    ItemStorageOut,
    ItemStorageUpdate,
    PutAwayRow,
)
from trishul_api.modules.inv.binmove_service import BINMOVE_MANAGE, BinMoveService
from trishul_api.modules.inv.common import ANY_INVENTORY, ITEM_MANAGE

router = APIRouter(prefix="/inv", tags=["bin-moves"])

CAN_READ = Depends(require_permission(*ANY_INVENTORY))
CAN_MOVE = Depends(require_permission(BINMOVE_MANAGE))
CAN_SET_STORAGE = Depends(require_permission(ITEM_MANAGE))
ItemId = Annotated[int, Path(alias="itemId", gt=0)]


def _service(db: DbSession, actor: CurrentUserDep) -> BinMoveService:
    return BinMoveService(db, actor)


Moves = Annotated[BinMoveService, Depends(_service)]


@router.get(
    "/putaway",
    summary="Stock waiting in receiving bins or kept without a bin, with a suggested bin for each",
    dependencies=[CAN_MOVE],
    responses=NOT_FOUND_RESPONSE,
)
def list_putaway(location_id: Annotated[int, Query(alias="locationId", gt=0)], moves: Moves) -> list[PutAwayRow]:
    return moves.putaway(location_id)


@router.post(
    "/bin-moves",
    summary="Move stock between bins of one location (put-away or rack to rack); posted at once",
    status_code=201,
    dependencies=[CAN_MOVE],
)
def create_bin_move(data: BinMoveCreate, moves: Moves) -> BinMoveOut:
    return moves.move(data)


@router.get("/bin-moves", summary="Bin moves, newest first", dependencies=[CAN_READ])
def list_bin_moves(query: Annotated[BinMoveQuery, Query()], moves: Moves) -> Page[BinMoveOut]:
    return moves.search(query)


@router.get(
    "/bin-moves/{moveId}", summary="One bin move with its lines", dependencies=[CAN_READ], responses=NOT_FOUND_RESPONSE
)
def get_bin_move(move_id: Annotated[int, Path(alias="moveId", gt=0)], moves: Moves) -> BinMoveOut:
    return moves.get(move_id)


@router.get(
    "/items/{itemId}/storage",
    summary="An item's storage type and home bins",
    dependencies=[CAN_READ],
    responses=NOT_FOUND_RESPONSE,
)
def get_item_storage(item_id: ItemId, moves: Moves) -> ItemStorageOut:
    return moves.storage(item_id)


@router.put(
    "/items/{itemId}/storage",
    summary="Set an item's storage type and home bins (replaces them)",
    dependencies=[CAN_SET_STORAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_item_storage(
    item_id: ItemId,
    data: ItemStorageUpdate,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
    moves: Moves,
) -> ItemStorageOut:
    return moves.set_storage(item_id, row_version, data)
