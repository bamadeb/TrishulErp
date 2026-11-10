"""Item master (core.item) and its prices and costs.

* Every item has a category (or subcategory) and a stock unit; codes are unique.
* Brand items carry principal_id; items without one are common (lubricants, consumables).
* Stock per item is the sum of its GRN batches at the user's locations (inv.lot_balance), valued at each
  batch's actual cost.
* Sales prices live in sal.price_list_item (per price list and minimum quantity), purchase prices in
  pur.supplier_item_price (per supplier and validity); standard cost, MRP and last purchase cost on the item.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    HsnSac,
    Item,
    ItemCategory,
    Location,
    LotBalance,
    PriceList,
    PriceListItem,
    Principal,
    StockLot,
    StockMove,
    Supplier,
    SupplierItemPrice,
    Uom,
)
from trishul_api.modules.inv.common import default_company, now, visible_item, visible_location
from trishul_api.modules.inv.item_schemas import (
    HsnOption,
    ItemCreate,
    ItemDetail,
    ItemFormOptions,
    ItemListItem,
    ItemPrices,
    ItemQuery,
    ItemUpdate,
    PrincipalOption,
    PurchasePriceCreate,
    PurchasePriceOut,
    PurchasePriceUpdate,
    SalesPriceCreate,
    SalesPriceOut,
    SalesPriceUpdate,
)
from trishul_api.modules.inv.masters_service import MastersService

_SORT: SortColumns = {
    "itemCode": Item.item_code,
    "description": Item.description,
    "categoryName": ItemCategory.name,
    "standardCost": Item.standard_cost,
    "createdAt": Item.created_at,
}
# Item fields copied straight from the request (code, category, unit, brand, HSN are checked first).
_PLAIN = (
    "description",
    "long_description",
    "oem_part_number",
    "item_type",
    "is_serialized",
    "is_batch_tracked",
    "standard_cost",
    "mrp",
    "reorder_level",
    "reorder_qty",
    "lead_time_days",
    "is_active",
)
_REQUIRED = {"description", "item_type", "is_serialized", "is_batch_tracked", "is_active"}


class ItemService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ reads

    def _stock(self) -> Any:
        """qty and value on hand per item at the user's locations."""
        return (
            select(
                LotBalance.item_id,
                func.sum(LotBalance.qty_on_hand).label("qty"),
                func.sum(LotBalance.qty_on_hand * StockLot.unit_cost).label("value"),
            )
            .join(StockLot, StockLot.id == LotBalance.stock_lot_id)
            .join(Location, Location.id == LotBalance.location_id)
            .where(LotBalance.qty_on_hand > 0, visible_location(self._actor))
            .group_by(LotBalance.item_id)
            .subquery()
        )

    def _list_select(self) -> tuple[Select[*tuple[Any, ...]], Any]:
        """Columns of ItemListItem, and the stock subquery they read from."""
        stock = self._stock()
        statement = (
            select(
                Item.id,
                Item.item_code,
                Item.description,
                Item.oem_part_number,
                Item.category_id,
                ItemCategory.name.label("category_name"),
                Item.uom_id,
                Uom.code.label("uom_code"),
                Item.item_type,
                Item.principal_id,
                Principal.code.label("principal_code"),
                Item.standard_cost,
                Item.mrp,
                Item.reorder_level,
                func.coalesce(stock.c.qty, 0).label("qty_on_hand"),
                func.coalesce(stock.c.value, 0).label("stock_value"),
                Item.is_active,
            )
            .join(ItemCategory, ItemCategory.id == Item.category_id)
            .join(Uom, Uom.id == Item.uom_id)
            .outerjoin(Principal, Principal.id == Item.principal_id)
            .outerjoin(stock, stock.c.item_id == Item.id)
        )
        return statement, stock

    def search(self, scope: RequestScope, query: ItemQuery) -> Page[ItemListItem]:
        statement, stock = self._list_select()
        statement = statement.where(visible_item(self._actor, scope))
        if query.status != "all":
            statement = statement.where(Item.is_active == (query.status == "active"))
        if query.category_id is not None:
            statement = statement.where(Item.category_id.in_(self._category_and_children(query.category_id)))
        if query.item_type is not None:
            statement = statement.where(Item.item_type == query.item_type)
        if query.below_reorder:
            statement = statement.where(
                Item.reorder_level.is_not(None), func.coalesce(stock.c.qty, 0) <= Item.reorder_level
            )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Item.item_code.contains(term, autoescape=True),
                    Item.description.contains(term, autoescape=True),
                    Item.oem_part_number.contains(term, autoescape=True),
                )
            )
        sort: SortColumns = {**_SORT, "qtyOnHand": func.coalesce(stock.c.qty, 0)}
        statement = order_by_sort(statement, query.sort, sort, default="itemCode", tiebreaker=Item.id.asc())
        return paginate(self._db, statement, query, ItemListItem)

    def get(self, item_id: int) -> ItemDetail:
        self._visible(item_id)
        statement, _ = self._list_select()
        statement = (
            statement.add_columns(
                Item.long_description,
                Item.hsn_sac_id,
                HsnSac.code.label("hsn_code"),
                Item.is_serialized,
                Item.is_batch_tracked,
                Item.last_purchase_cost,
                Item.reorder_qty,
                Item.lead_time_days,
                Item.created_at,
                Item.row_version,
            )
            .outerjoin(HsnSac, HsnSac.id == Item.hsn_sac_id)
            .where(Item.id == item_id)
        )
        return ItemDetail.model_validate(self._db.execute(statement).mappings().one())

    def form_options(self) -> ItemFormOptions:
        masters = MastersService(self._db, self._actor)
        principals = select(Principal).where(Principal.is_active).order_by(Principal.name)
        if self._actor.principal_ids is not None:
            principals = principals.where(Principal.id.in_(self._actor.principal_ids))
        hsn = self._db.scalars(select(HsnSac).where(HsnSac.is_active).order_by(HsnSac.code)).all()
        return ItemFormOptions(
            categories=masters.categories("active"),
            uoms=masters.uoms("active"),
            principals=[PrincipalOption.model_validate(p) for p in self._db.scalars(principals).all()],
            hsn_codes=[HsnOption.model_validate(h) for h in hsn],
        )

    # ------------------------------------------------------------------ writes

    def create(self, data: ItemCreate, scope: RequestScope) -> ItemDetail:
        code = data.item_code.upper()
        self._check_code(code, None)
        category = self._category(data.category_id)
        uom_id = data.uom_id or category.default_uom_id
        if uom_id is None:
            raise ApiError(
                "Choose the item's stock unit.", errors={"uomId": ["Required (the category has no default)."]}
            )
        self._check_uom(uom_id)
        self._check_principal(data.principal_id)
        self._check_hsn(data.hsn_sac_id)
        item = Item(
            company_id=default_company(self._db, self._actor, scope),
            item_code=code,
            category_id=category.id,
            uom_id=uom_id,
            principal_id=data.principal_id,
            hsn_sac_id=data.hsn_sac_id or category.default_hsn_sac_id,
            created_by_user_id=self._actor.id,
            **{field: getattr(data, field) for field in _PLAIN if field != "is_active"},
        )
        self._save(item)
        return self.get(item.id)

    def update(self, item_id: int, expected: bytes, data: ItemUpdate) -> ItemDetail:
        item = self._visible(item_id)
        check_row_version(item.row_version, expected)
        changed = data.model_fields_set
        if "item_code" in changed and data.item_code and data.item_code.upper() != item.item_code:
            self._check_code(data.item_code.upper(), item.id)
            item.item_code = data.item_code.upper()
        if "category_id" in changed and data.category_id is not None:
            item.category_id = self._category(data.category_id).id
        if "uom_id" in changed and data.uom_id is not None and data.uom_id != item.uom_id:
            self._check_uom(data.uom_id)
            if self._db.scalar(select(StockMove.id).where(StockMove.item_id == item.id).limit(1)) is not None:
                raise ApiError(
                    "The stock unit can't change once the item has stock. Add a unit conversion instead.",
                    errors={"uomId": ["Item already has stock movements."]},
                )
            item.uom_id = data.uom_id
        if "principal_id" in changed:
            self._check_principal(data.principal_id)
            item.principal_id = data.principal_id
        if "hsn_sac_id" in changed:
            self._check_hsn(data.hsn_sac_id)
            item.hsn_sac_id = data.hsn_sac_id
        for field in _PLAIN:
            if field in changed:
                value = getattr(data, field)
                if value is None and field in _REQUIRED:
                    continue
                setattr(item, field, value)
        item.updated_at = now()
        item.updated_by_user_id = self._actor.id
        self._save(item)
        return self.get(item.id)

    # ------------------------------------------------------------------ prices

    def prices(self, item_id: int) -> ItemPrices:
        item = self._visible(item_id)
        sales = self._db.execute(
            select(
                PriceListItem.id,
                PriceListItem.price_list_id,
                PriceList.code.label("price_list_code"),
                PriceList.name.label("price_list_name"),
                PriceList.price_list_type,
                PriceList.includes_tax,
                PriceList.valid_from,
                PriceList.valid_to,
                PriceListItem.min_qty,
                PriceListItem.unit_price,
                PriceListItem.is_active,
                PriceListItem.row_version,
            )
            .join(PriceList, PriceList.id == PriceListItem.price_list_id)
            .where(PriceListItem.item_id == item.id)
            .order_by(PriceList.code, PriceListItem.min_qty)
        ).mappings()
        purchase = self._db.execute(
            select(
                SupplierItemPrice.id,
                SupplierItemPrice.supplier_id,
                Supplier.code.label("supplier_code"),
                Supplier.name.label("supplier_name"),
                SupplierItemPrice.supplier_part_no,
                SupplierItemPrice.supplier_uom,
                SupplierItemPrice.conversion_factor,
                SupplierItemPrice.price,
                SupplierItemPrice.valid_from,
                SupplierItemPrice.valid_to,
                SupplierItemPrice.lead_time_days,
                SupplierItemPrice.is_active,
                SupplierItemPrice.row_version,
            )
            .join(Supplier, Supplier.id == SupplierItemPrice.supplier_id)
            .where(SupplierItemPrice.item_id == item.id)
            .order_by(Supplier.name, SupplierItemPrice.valid_from.desc())
        ).mappings()
        sales_prices = [SalesPriceOut.model_validate(row) for row in sales]
        purchase_prices = [PurchasePriceOut.model_validate(row) for row in purchase]
        qty, value = self._db.execute(
            select(func.sum(LotBalance.qty_on_hand), func.sum(LotBalance.qty_on_hand * StockLot.unit_cost))
            .join(StockLot, StockLot.id == LotBalance.stock_lot_id)
            .join(Location, Location.id == LotBalance.location_id)
            .where(LotBalance.item_id == item.id, LotBalance.qty_on_hand > 0, visible_location(self._actor))
        ).one()
        average = (Decimal(value) / Decimal(qty)).quantize(Decimal("0.0001")) if qty else None
        return ItemPrices(
            item_id=item.id,
            standard_cost=item.standard_cost,
            last_purchase_cost=item.last_purchase_cost,
            mrp=item.mrp,
            average_cost=average,
            sales_prices=sales_prices,
            purchase_prices=purchase_prices,
        )

    def add_sales_price(self, item_id: int, data: SalesPriceCreate) -> ItemPrices:
        item = self._visible(item_id)
        price_list = self._db.get(PriceList, data.price_list_id)
        if price_list is None or not price_list.is_active:
            raise ApiError("Choose an active price list.", errors={"priceListId": ["Unknown or inactive price list."]})
        duplicate = self._db.scalar(
            select(PriceListItem.id).where(
                PriceListItem.price_list_id == price_list.id,
                PriceListItem.item_id == item.id,
                PriceListItem.min_qty == data.min_qty,
            )
        )
        if duplicate is not None:
            raise AlreadyExists("This price list already has a price for that quantity; change it instead.")
        self._db.add(
            PriceListItem(
                price_list_id=price_list.id,
                item_id=item.id,
                unit_price=data.unit_price,
                min_qty=data.min_qty,
                created_by_user_id=self._actor.id,
            )
        )
        self._commit("This price list already has a price for that quantity.")
        return self.prices(item.id)

    def update_sales_price(self, price_id: int, expected: bytes, data: SalesPriceUpdate) -> ItemPrices:
        row = self._db.get(PriceListItem, price_id)
        if row is None:
            raise NotFound("Price not found.")
        self._visible(row.item_id)
        check_row_version(row.row_version, expected)
        for field in ("unit_price", "min_qty", "is_active"):
            value = getattr(data, field)
            if field in data.model_fields_set and value is not None:
                setattr(row, field, value)
        row.updated_at = now()
        row.updated_by_user_id = self._actor.id
        self._commit("This price list already has a price for that quantity.")
        return self.prices(row.item_id)

    def add_purchase_price(self, item_id: int, data: PurchasePriceCreate) -> ItemPrices:
        item = self._visible(item_id)
        supplier = self._db.get(Supplier, data.supplier_id)
        if supplier is None or not supplier.is_active:
            raise ApiError("Choose an active supplier.", errors={"supplierId": ["Unknown or inactive supplier."]})
        if data.valid_from and data.valid_to and data.valid_to < data.valid_from:
            raise ApiError("The end date is before the start date.", errors={"validTo": ["Before the start date."]})
        self._db.add(
            SupplierItemPrice(
                supplier_id=supplier.id,
                item_id=item.id,
                supplier_part_no=data.supplier_part_no,
                supplier_uom=data.supplier_uom,
                conversion_factor=data.conversion_factor,
                price=data.price,
                currency_id=MastersService(self._db, self._actor).currency_id(),
                valid_from=data.valid_from,
                valid_to=data.valid_to,
                lead_time_days=data.lead_time_days,
                created_by_user_id=self._actor.id,
            )
        )
        self._commit("This supplier already has a price for the item from that date.")
        return self.prices(item.id)

    def update_purchase_price(self, price_id: int, expected: bytes, data: PurchasePriceUpdate) -> ItemPrices:
        row = self._db.get(SupplierItemPrice, price_id)
        if row is None:
            raise NotFound("Price not found.")
        self._visible(row.item_id)
        check_row_version(row.row_version, expected)
        changed = data.model_fields_set
        for field in ("price", "conversion_factor", "is_active"):
            value = getattr(data, field)
            if field in changed and value is not None:
                setattr(row, field, value)
        for field in ("supplier_part_no", "supplier_uom", "valid_from", "valid_to", "lead_time_days"):
            if field in changed:
                setattr(row, field, getattr(data, field))
        if row.valid_from and row.valid_to and row.valid_to < row.valid_from:
            raise ApiError("The end date is before the start date.", errors={"validTo": ["Before the start date."]})
        row.updated_at = now()
        row.updated_by_user_id = self._actor.id
        self._commit("This supplier already has a price for the item from that date.")
        return self.prices(row.item_id)

    # ------------------------------------------------------------------ helpers

    def _visible(self, item_id: int) -> Item:
        item = self._db.get(Item, item_id)
        if item is None or (item.principal_id is not None and not self._actor.can_see_principal(item.principal_id)):
            raise NotFound("Item not found.")
        return item

    def _category_and_children(self, category_id: int) -> list[int]:
        parents = dict(self._db.execute(select(ItemCategory.id, ItemCategory.parent_category_id)).all())
        wanted = {category_id}
        grew = True
        while grew:
            grew = False
            for child, parent in parents.items():
                if parent in wanted and child not in wanted:
                    wanted.add(child)
                    grew = True
        return sorted(wanted)

    def _check_code(self, code: str, own_id: int | None) -> None:
        statement = select(Item.id).where(Item.item_code == code)
        if own_id is not None:
            statement = statement.where(Item.id != own_id)
        if self._db.scalar(statement.limit(1)) is not None:
            raise AlreadyExists(f"Item code '{code}' is already used.")

    def _category(self, category_id: int) -> ItemCategory:
        category = self._db.get(ItemCategory, category_id)
        if category is None or not category.is_active:
            raise ApiError("Choose an active category.", errors={"categoryId": [f"Unknown category {category_id}."]})
        return category

    def _check_uom(self, uom_id: int) -> None:
        unit = self._db.get(Uom, uom_id)
        if unit is None or not unit.is_active:
            raise ApiError("Choose an active unit.", errors={"uomId": [f"Unknown or inactive unit {uom_id}."]})

    def _check_principal(self, principal_id: int | None) -> None:
        if principal_id is None:
            return
        if self._db.get(Principal, principal_id) is None or not self._actor.can_see_principal(principal_id):
            raise ApiError("Choose one of your brands.", errors={"principalId": ["Unknown or not one of your brands."]})

    def _check_hsn(self, hsn_id: int | None) -> None:
        if hsn_id is not None and self._db.get(HsnSac, hsn_id) is None:
            raise ApiError("Choose an HSN / SAC code from the list.", errors={"hsnSacId": [f"Unknown code {hsn_id}."]})

    def _save(self, item: Item) -> None:
        self._db.add(item)
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("Another item already has this code.") from error

    def _commit(self, duplicate: str) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(duplicate) from error
