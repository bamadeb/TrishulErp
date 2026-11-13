"""Shared pieces of the inventory module: permissions, the user's branch / brand limits, lookups.

Who sees what:
  * stock and locations: only locations of the branches the user may work in (CurrentUser.branch_ids);
  * items: common items (no brand) plus the brands the user may see; the brand picked in the header
    narrows that to common items plus that brand.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import ColumnElement, case, or_, select, true
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.errors import ApiError, Forbidden, NotFound
from trishul_api.db.models import Bin, Branch, Item, Location

ITEM_VIEW = "inv.item.view"
ITEM_MANAGE = "inv.item.manage"
LOCATION_MANAGE = "inv.location.manage"
STOCK_VIEW = "inv.stock.view"
GRN_MANAGE = "inv.grn.manage"
TRANSFER_MANAGE = "inv.transfer.manage"
STOCK_ADJUST = "inv.stock.adjust"

#: Sales users who pick items, dispatch locations and racks (quotations, orders, deliveries, invoices).
SALES_PICKERS = ("sal.quotation.manage", "sal.order.manage", "sal.delivery.manage", "sal.invoice.direct")
#: Any inventory permission: enough to read the masters the inventory screens pick from.
ANY_INVENTORY = (
    ITEM_VIEW, ITEM_MANAGE, LOCATION_MANAGE, STOCK_VIEW, GRN_MANAGE, TRANSFER_MANAGE, STOCK_ADJUST, *SALES_PICKERS,
)  # fmt: skip
#: Who may see what items cost us (standard / last purchase cost, stock value). Others, e.g. service engineers
#: who only look items up, get these fields empty.
COST_VIEWERS = (
    ITEM_MANAGE, STOCK_VIEW, GRN_MANAGE, TRANSFER_MANAGE, STOCK_ADJUST,
    "pur.po.manage", "pur.invoice.manage", "pur.credit_note.manage",
)  # fmt: skip
#: Screens that work with stock (pick a location, see what is there; deliveries pick a batch).
STOCK_USERS = (STOCK_VIEW, GRN_MANAGE, TRANSFER_MANAGE, STOCK_ADJUST, "sal.delivery.manage", "sal.invoice.direct")

ZERO = Decimal(0)


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def today() -> date:
    return date.today()


def visible_branch(actor: CurrentUser) -> ColumnElement[bool]:
    """Condition on core.branch.id (or a column holding it): a branch the user may work in."""
    if actor.branch_ids is None:
        return true()
    return Branch.id.in_(actor.branch_ids)


def visible_location(actor: CurrentUser) -> ColumnElement[bool]:
    """Condition on core.location: in one of the user's branches."""
    if actor.branch_ids is None:
        return true()
    return Location.branch_id.in_(actor.branch_ids)


def visible_item(actor: CurrentUser, scope: RequestScope | None = None) -> ColumnElement[bool]:
    """Condition on core.item: a common item, or a brand the user may see (and the selected brand)."""
    conditions: list[ColumnElement[bool]] = []
    if actor.principal_ids is not None:
        conditions.append(or_(Item.principal_id.is_(None), Item.principal_id.in_(actor.principal_ids)))
    if scope is not None and scope.principal_id is not None:
        conditions.append(or_(Item.principal_id.is_(None), Item.principal_id == scope.principal_id))
    if not conditions:
        return true()
    condition = conditions[0]
    for extra in conditions[1:]:
        condition = condition & extra
    return condition


def check_branch(actor: CurrentUser, branch_id: int | None) -> None:
    if branch_id is not None and not actor.can_use_branch(branch_id):
        raise Forbidden("You do not have access to this branch.")


def stock_location(db: Session, actor: CurrentUser, location_id: int, field: str = "locationId") -> Location:
    """An active stock location in one of the user's branches, or a 400 naming the field."""
    location = db.get(Location, location_id)
    if location is None or not location.is_active:
        raise ApiError("Choose an active location.", errors={field: [f"Unknown or inactive location {location_id}."]})
    if not actor.can_use_branch(location.branch_id):
        raise ApiError(
            "That location is in a branch you do not work in.", errors={field: ["Not one of your branches."]}
        )
    if not location.is_stock_location:
        raise ApiError("That location does not hold stock.", errors={field: ["Not a stock location."]})
    return location


def rack_of(db: Session, location: Location, bin_id: int | None, field: str) -> int | None:
    """The rack id after checking it belongs to the location and is active (None = no rack)."""
    if bin_id is None:
        return None
    rack = db.get(Bin, bin_id)
    if rack is None or not rack.is_active or rack.location_id != location.id:
        raise ApiError(
            f"That rack is not in location {location.code}.",
            errors={field: [f"Rack {bin_id} is not in this location."]},
        )
    return rack.id


def stock_item(db: Session, actor: CurrentUser, item_id: int, field: str = "itemId") -> Item:
    """An active stock item of a brand the user may see."""
    item = db.get(Item, item_id)
    if item is None or not item.is_active:
        raise ApiError("Choose an active item.", errors={field: [f"Unknown or inactive item {item_id}."]})
    if item.principal_id is not None and not actor.can_see_principal(item.principal_id):
        raise ApiError("You do not have access to that item's brand.", errors={field: ["Not one of your brands."]})
    if item.item_type != "Stock":
        raise ApiError(
            f"{item.item_code} is a {item.item_type.lower()} item and is not kept in stock.",
            errors={field: ["Not a stock item."]},
        )
    return item


def company_of_branch(db: Session, branch_id: int) -> int:
    company_id = db.scalar(select(Branch.company_id).where(Branch.id == branch_id))
    if company_id is None:
        raise NotFound("Branch not found.")
    return int(company_id)


def default_company(db: Session, actor: CurrentUser, scope: RequestScope | None) -> int:
    """The company new masters (items, suppliers) belong to: the selected branch's, else the head office's."""
    branch_id = (scope.branch_id if scope else None) or actor.default_branch_id
    if branch_id is not None:
        company_id = db.scalar(select(Branch.company_id).where(Branch.id == branch_id))
        if company_id is not None:
            return int(company_id)
    company_id = db.scalar(
        select(Branch.company_id).order_by(case((Branch.branch_type == "Head office", 0), else_=1), Branch.id).limit(1)
    )
    if company_id is None:
        raise ApiError("No branch is set up yet, so there is no company to add this to.")
    return int(company_id)
