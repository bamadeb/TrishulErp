"""Stock going out on a sale, and coming back when the sale is cancelled.

Out: the ledger takes the quantity from the dispatch location, oldest GRN date first (or the batch / rack
named), writing one stock_move per batch with the delivery note (or direct invoice) as its source. The
line keeps the weighted cost of what was taken.

Back (cancellation): the same batches go back to the same place, from those stock_move rows, so their GRN
date (and the inventory age) is unchanged. Nothing is deleted: the reversal is new SALES_RETURN movements.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.db.models import Item, Location, StockLot, StockMove
from trishul_api.modules.inv.ledger import Source, StockLedger

SALE = "SALE"
SALE_REVERSAL = "SALES_RETURN"
_COST = Decimal("0.0001")


def take_for_sale(
    ledger: StockLedger,
    *,
    item: Item,
    location: Location,
    bin_id: int | None,
    quantity: Decimal,
    lot_id: int | None,
    source: Source,
) -> Decimal:
    """Takes the stock; returns the weighted unit cost of the batches taken."""
    taken = ledger.take(
        item=item,
        location_id=location.id,
        bin_id=bin_id,
        quantity=quantity,
        movement=SALE,
        source=source,
        lot_id=lot_id,
        location_label=location.name,
    )
    value = sum((t.quantity * t.lot.unit_cost for t in taken), Decimal(0))
    return (value / quantity).quantize(_COST)


def put_back(db: Session, ledger: StockLedger, *, document_type: str, document_id: int, reference: str) -> None:
    """Returns every batch a document took, to the place it came from."""
    moves = db.scalars(
        select(StockMove)
        .where(
            StockMove.source_document_type == document_type,
            StockMove.source_document_id == document_id,
            StockMove.quantity < 0,
        )
        .order_by(StockMove.id)
    ).all()
    for move in moves:
        lot = db.get(StockLot, move.stock_lot_id)
        assert lot is not None
        ledger.put(
            lot,
            move.location_id,
            move.bin_id,
            -move.quantity,
            SALE_REVERSAL,
            Source(f"{document_type}_CANCEL", document_id, reference, move.source_line_id),
        )
