"""Inventory masters: units and conversions, item categories (with subcategories), locations and racks
under branches and warehouses, suppliers, and sales price lists.

Codes are unique (database indexes); each is checked up front for a clear message and a concurrent
duplicate is still caught on commit. Masters are never deleted, only deactivated (isActive false), so
documents that used them keep showing them.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import (
    Bin,
    Branch,
    Currency,
    GstRate,
    HsnSac,
    Item,
    ItemCategory,
    Location,
    LookupType,
    LookupValue,
    PriceList,
    PriceListItem,
    Principal,
    Uom,
    UomConversion,
)
from trishul_api.modules.inv.common import check_branch, now, visible_branch, visible_location
from trishul_api.modules.inv.masters_schemas import (
    BranchOption,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ConversionCreate,
    ConversionOut,
    ConversionQuery,
    ConversionUpdate,
    HsnCreate,
    HsnOut,
    HsnUpdate,
    LocationCreate,
    LocationOut,
    LocationQuery,
    LocationUpdate,
    LookupOption,
    PriceListCreate,
    PriceListOut,
    PriceListUpdate,
    RackCreate,
    RackOut,
    RackUpdate,
    StatusFilter,
    UomCreate,
    UomOut,
    UomUpdate,
)

ADJUSTMENT_REASON = "ADJUSTMENT_REASON"


def _status(statement: Any, column: Any, status: StatusFilter) -> Any:
    return statement if status == "all" else statement.where(column == (status == "active"))


class MastersService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ================================================================ units of measure

    def uoms(self, status: StatusFilter) -> list[UomOut]:
        rows = self._db.scalars(_status(select(Uom), Uom.is_active, status).order_by(Uom.code)).all()
        return [UomOut.model_validate(row) for row in rows]

    def create_uom(self, data: UomCreate) -> UomOut:
        code = data.code.upper()
        self._unique(Uom, Uom.code, code, None, f"Unit '{code}' already exists.")
        row = Uom(code=code, name=data.name, decimals=data.decimals, created_by_user_id=self._actor.id)
        self._save(row, f"Unit '{code}' already exists.")
        return UomOut.model_validate(row)

    def update_uom(self, uom_id: int, expected: bytes, data: UomUpdate) -> UomOut:
        row = self._get(Uom, uom_id, "Unit not found.")
        check_row_version(row.row_version, expected)
        self._apply(row, data, ("name", "decimals", "is_active"))
        self._save(row, "The unit could not be saved.")
        return UomOut.model_validate(row)

    # ================================================================ HSN / SAC codes

    def hsn_codes(self, status: StatusFilter) -> list[HsnOut]:
        items = select(func.count(Item.id)).where(Item.hsn_sac_id == HsnSac.id).correlate(HsnSac).scalar_subquery()
        statement = (
            select(
                HsnSac.id,
                HsnSac.code,
                HsnSac.code_type,
                HsnSac.description,
                GstRate.total_rate.label("gst_pct"),
                items.label("item_count"),
                HsnSac.is_active,
                HsnSac.row_version,
            )
            .join(GstRate, GstRate.id == HsnSac.gst_rate_id)
            .order_by(HsnSac.code)
        )
        rows = self._db.execute(_status(statement, HsnSac.is_active, status)).mappings().all()
        return [HsnOut.model_validate(row) for row in rows]

    def create_hsn(self, data: HsnCreate) -> HsnOut:
        self._unique(HsnSac, HsnSac.code, data.code, None, f"HSN / SAC code {data.code} already exists.")
        row = HsnSac(
            code=data.code,
            code_type=data.code_type,
            description=data.description,
            gst_rate_id=self._gst_rate(data.gst_pct),
            created_by_user_id=self._actor.id,
        )
        self._save(row, f"HSN / SAC code {data.code} already exists.")
        return self._one_hsn(row.id)

    def update_hsn(self, hsn_id: int, expected: bytes, data: HsnUpdate) -> HsnOut:
        row = self._get(HsnSac, hsn_id, "HSN / SAC code not found.")
        check_row_version(row.row_version, expected)
        self._apply(row, data, ("description", "is_active"))
        if data.code_type is not None:
            row.code_type = data.code_type
        if data.gst_pct is not None:
            row.gst_rate_id = self._gst_rate(data.gst_pct)
        row.updated_at = now()
        row.updated_by_user_id = self._actor.id
        self._save(row, "The HSN / SAC code could not be saved.")
        return self._one_hsn(row.id)

    def _one_hsn(self, hsn_id: int) -> HsnOut:
        return next(h for h in self.hsn_codes("all") if h.id == hsn_id)

    def _gst_rate(self, pct: Decimal) -> int:
        """The GST rate row for a percentage (acc.gst_rate, e.g. GST18), added the first time it is used."""
        rate_id = self._db.scalar(
            select(GstRate.id)
            .where(GstRate.total_rate == pct, GstRate.is_active)
            .order_by(GstRate.effective_from.desc())
            .limit(1)
        )
        if rate_id is not None:
            return int(rate_id)
        label = format(pct.normalize(), "f")
        half = (pct / 2).quantize(Decimal("0.01"))
        rate = GstRate(
            code=f"GST{label}",
            description=f"GST {label}%",
            total_rate=pct,
            cgst_rate=half,
            sgst_rate=pct - half,
            igst_rate=pct,
            cess_rate=Decimal(0),
            effective_from=date(2017, 7, 1),  # GST came into force
            created_by_user_id=self._actor.id,
        )
        self._db.add(rate)
        self._db.flush()
        return int(rate.id)

    def conversions(self, query: ConversionQuery) -> list[ConversionOut]:
        from_uom, to_uom = aliased(Uom), aliased(Uom)
        statement = (
            select(
                UomConversion.id,
                UomConversion.item_id,
                Item.item_code,
                Item.description.label("item_description"),
                UomConversion.from_uom_id,
                from_uom.code.label("from_uom_code"),
                UomConversion.to_uom_id,
                to_uom.code.label("to_uom_code"),
                UomConversion.factor,
                UomConversion.is_active,
                UomConversion.row_version,
            )
            .join(from_uom, from_uom.id == UomConversion.from_uom_id)
            .join(to_uom, to_uom.id == UomConversion.to_uom_id)
            .outerjoin(Item, Item.id == UomConversion.item_id)
        )
        statement = _status(statement, UomConversion.is_active, query.status)
        if query.item_id is not None:
            statement = statement.where(or_(UomConversion.item_id == query.item_id, UomConversion.item_id.is_(None)))
        statement = statement.order_by(Item.item_code, from_uom.code, to_uom.code, UomConversion.id)
        return [ConversionOut.model_validate(row) for row in self._db.execute(statement).mappings()]

    def create_conversion(self, data: ConversionCreate) -> ConversionOut:
        if data.from_uom_id == data.to_uom_id:
            raise ApiError("Choose two different units.", errors={"toUomId": ["Same as the from unit."]})
        for field, uom_id in (("fromUomId", data.from_uom_id), ("toUomId", data.to_uom_id)):
            unit = self._db.get(Uom, uom_id)
            if unit is None or not unit.is_active:
                raise ApiError("Choose an active unit.", errors={field: [f"Unknown or inactive unit {uom_id}."]})
        if data.item_id is not None:
            item = self._db.get(Item, data.item_id)
            if item is None:
                raise ApiError("Choose an item.", errors={"itemId": [f"Unknown item {data.item_id}."]})
        existing = self._db.scalar(
            select(UomConversion.id).where(
                UomConversion.from_uom_id == data.from_uom_id,
                UomConversion.to_uom_id == data.to_uom_id,
                UomConversion.item_id.is_(None) if data.item_id is None else UomConversion.item_id == data.item_id,
            )
        )
        if existing is not None:
            raise AlreadyExists("This conversion already exists; change its factor instead.")
        row = UomConversion(
            item_id=data.item_id,
            from_uom_id=data.from_uom_id,
            to_uom_id=data.to_uom_id,
            factor=data.factor,
            created_by_user_id=self._actor.id,
        )
        self._save(row, "This conversion already exists.")
        return self._conversion(row.id)

    def update_conversion(self, conversion_id: int, expected: bytes, data: ConversionUpdate) -> ConversionOut:
        row = self._get(UomConversion, conversion_id, "Conversion not found.")
        check_row_version(row.row_version, expected)
        self._apply(row, data, ("factor", "is_active"))
        self._save(row, "The conversion could not be saved.")
        return self._conversion(row.id)

    def _conversion(self, conversion_id: int) -> ConversionOut:
        found = [c for c in self.conversions(ConversionQuery(status="all")) if c.id == conversion_id]
        return found[0]

    # ================================================================ item categories

    def categories(self, status: StatusFilter) -> list[CategoryOut]:
        """Every category with its path; ordered so each subcategory follows its parent."""
        all_rows = self._db.scalars(select(ItemCategory)).all()
        by_id = {row.id: row for row in all_rows}
        uoms = dict(self._db.execute(select(Uom.id, Uom.code)).all())
        counts = dict(
            self._db.execute(
                select(Item.category_id, func.count(Item.id)).where(Item.is_active).group_by(Item.category_id)
            ).all()
        )

        def chain(row: ItemCategory) -> list[ItemCategory]:
            names: list[ItemCategory] = []
            current: ItemCategory | None = row
            while current is not None and current not in names and len(names) < 10:
                names.insert(0, current)
                current = by_id.get(current.parent_category_id) if current.parent_category_id else None
            return names

        out: list[tuple[str, CategoryOut]] = []
        for row in all_rows:
            if status != "all" and row.is_active != (status == "active"):
                continue
            parents = chain(row)
            parent = by_id.get(row.parent_category_id) if row.parent_category_id else None
            out.append(
                (
                    " / ".join(p.name.lower() for p in parents),
                    CategoryOut(
                        id=row.id,
                        code=row.code,
                        name=row.name,
                        parent_category_id=row.parent_category_id,
                        parent_name=parent.name if parent else None,
                        path=" / ".join(p.name for p in parents),
                        level=len(parents) - 1,
                        item_nature=row.item_nature,
                        default_uom_id=row.default_uom_id,
                        default_uom_code=uoms.get(row.default_uom_id) if row.default_uom_id else None,
                        item_count=int(counts.get(row.id, 0)),
                        is_active=row.is_active,
                        row_version=row.row_version,
                    ),
                )
            )
        return [category for _, category in sorted(out, key=lambda pair: pair[0])]

    def create_category(self, data: CategoryCreate) -> CategoryOut:
        code = data.code.upper()
        self._unique(ItemCategory, ItemCategory.code, code, None, f"Category code '{code}' is already used.")
        if data.parent_category_id is not None:
            self._active_category(data.parent_category_id, "parentCategoryId")
        self._active_uom(data.default_uom_id, "defaultUomId")
        row = ItemCategory(
            code=code,
            name=data.name,
            parent_category_id=data.parent_category_id,
            item_nature=data.item_nature,
            default_uom_id=data.default_uom_id,
            created_by_user_id=self._actor.id,
        )
        self._save(row, f"Category code '{code}' is already used.")
        return self._category(row.id)

    def update_category(self, category_id: int, expected: bytes, data: CategoryUpdate) -> CategoryOut:
        row = self._get(ItemCategory, category_id, "Category not found.")
        check_row_version(row.row_version, expected)
        changed = data.model_fields_set
        if "parent_category_id" in changed and data.parent_category_id != row.parent_category_id:
            if data.parent_category_id is not None:
                self._active_category(data.parent_category_id, "parentCategoryId")
                self._check_no_cycle(row.id, data.parent_category_id)
            row.parent_category_id = data.parent_category_id
        if "default_uom_id" in changed:
            self._active_uom(data.default_uom_id, "defaultUomId")
            row.default_uom_id = data.default_uom_id
        if data.is_active is False and row.is_active:
            in_use = self._db.scalar(
                select(func.count(ItemCategory.id)).where(
                    ItemCategory.parent_category_id == row.id, ItemCategory.is_active
                )
            )
            if in_use:
                raise ApiError(
                    "This category still has active subcategories. Deactivate or move them first.",
                    errors={"isActive": ["Has active subcategories."]},
                )
        self._apply(row, data, ("name", "item_nature", "is_active"))
        self._save(row, "The category could not be saved.")
        return self._category(row.id)

    def _category(self, category_id: int) -> CategoryOut:
        return next(c for c in self.categories("all") if c.id == category_id)

    def _check_no_cycle(self, category_id: int, new_parent_id: int) -> None:
        current: int | None = new_parent_id
        for _ in range(20):
            if current is None:
                return
            if current == category_id:
                raise ApiError(
                    "A category cannot sit under itself or one of its own subcategories.",
                    errors={"parentCategoryId": ["Would make a loop."]},
                )
            current = self._db.scalar(select(ItemCategory.parent_category_id).where(ItemCategory.id == current))

    def _active_category(self, category_id: int, field: str) -> ItemCategory:
        row = self._db.get(ItemCategory, category_id)
        if row is None or not row.is_active:
            raise ApiError(
                "Choose an active category.", errors={field: [f"Unknown or inactive category {category_id}."]}
            )
        return row

    def _active_uom(self, uom_id: int | None, field: str) -> None:
        if uom_id is None:
            return
        unit = self._db.get(Uom, uom_id)
        if unit is None or not unit.is_active:
            raise ApiError("Choose an active unit.", errors={field: [f"Unknown or inactive unit {uom_id}."]})

    # ================================================================ branches, locations, racks

    def branches(self) -> list[BranchOption]:
        rows = self._db.scalars(
            select(Branch).where(Branch.is_active, visible_branch(self._actor)).order_by(Branch.name)
        ).all()
        return [BranchOption.model_validate(row) for row in rows]

    def locations(self, query: LocationQuery) -> list[LocationOut]:
        racks = (
            select(Bin.location_id, func.count(Bin.id).label("rack_count"))
            .where(Bin.is_active)
            .group_by(Bin.location_id)
            .subquery()
        )
        statement = (
            select(
                Location.id,
                Location.branch_id,
                Branch.code.label("branch_code"),
                Branch.name.label("branch_name"),
                Branch.branch_type,
                Location.code,
                Location.name,
                Location.location_type,
                Location.address,
                Location.is_stock_location,
                func.coalesce(racks.c.rack_count, 0).label("rack_count"),
                Location.is_active,
                Location.row_version,
            )
            .join(Branch, Branch.id == Location.branch_id)
            .outerjoin(racks, racks.c.location_id == Location.id)
            .where(visible_location(self._actor))
        )
        statement = _status(statement, Location.is_active, query.status)
        if query.branch_id is not None:
            statement = statement.where(Location.branch_id == query.branch_id)
        statement = statement.order_by(Branch.name, Location.code)
        return [LocationOut.model_validate(row) for row in self._db.execute(statement).mappings()]

    def create_location(self, data: LocationCreate) -> LocationOut:
        branch = self._db.get(Branch, data.branch_id)
        if branch is None or not branch.is_active:
            raise ApiError("Choose an active branch.", errors={"branchId": [f"Unknown branch {data.branch_id}."]})
        check_branch(self._actor, branch.id)
        code = data.code.upper()
        self._unique(Location, Location.code, code, None, f"Location code '{code}' is already used.")
        row = Location(
            branch_id=branch.id,
            code=code,
            name=data.name,
            location_type=data.location_type,
            address=data.address,
            is_stock_location=data.is_stock_location,
            created_by_user_id=self._actor.id,
        )
        self._save(row, f"Location code '{code}' is already used.")
        return self._location(row.id)

    def update_location(self, location_id: int, expected: bytes, data: LocationUpdate) -> LocationOut:
        row = self._visible_location(location_id)
        check_row_version(row.row_version, expected)
        self._apply(row, data, ("name", "location_type", "address", "is_stock_location", "is_active"))
        self._save(row, "The location could not be saved.")
        return self._location(row.id)

    def _location(self, location_id: int) -> LocationOut:
        return next(loc for loc in self.locations(LocationQuery(status="all")) if loc.id == location_id)

    def _visible_location(self, location_id: int) -> Location:
        row = self._db.get(Location, location_id)
        if row is None or not self._actor.can_use_branch(row.branch_id):
            raise NotFound("Location not found.")
        return row

    def racks(self, location_id: int, status: StatusFilter) -> list[RackOut]:
        location = self._visible_location(location_id)
        statement = _status(select(Bin).where(Bin.location_id == location.id), Bin.is_active, status)
        return [self._rack_out(row, location) for row in self._db.scalars(statement.order_by(Bin.code)).all()]

    def create_rack(self, location_id: int, data: RackCreate) -> RackOut:
        location = self._visible_location(location_id)
        code = data.code.upper()
        self._unique(Bin, Bin.code, code, None, f"Rack code '{code}' is already used.")
        row = Bin(
            location_id=location.id,
            code=code,
            rack=data.rack,
            shelf=data.shelf,
            description=data.description,
            created_by_user_id=self._actor.id,
        )
        self._save(row, f"Rack code '{code}' is already used.")
        return self._rack_out(row, location)

    def update_rack(self, rack_id: int, expected: bytes, data: RackUpdate) -> RackOut:
        row = self._get(Bin, rack_id, "Rack not found.")
        location = self._visible_location(row.location_id)
        check_row_version(row.row_version, expected)
        if data.code is not None and data.code.upper() != row.code:
            code = data.code.upper()
            self._unique(Bin, Bin.code, code, row.id, f"Rack code '{code}' is already used.")
            row.code = code
        self._apply(row, data, ("rack", "shelf", "description", "is_active"))
        self._save(row, "The rack code is already used.")
        return self._rack_out(row, location)

    @staticmethod
    def _rack_out(row: Bin, location: Location) -> RackOut:
        return RackOut(
            id=row.id,
            location_id=location.id,
            location_code=location.code,
            code=row.code,
            rack=row.rack,
            shelf=row.shelf,
            description=row.description,
            is_active=row.is_active,
            row_version=row.row_version,
        )

    # ================================================================ price lists

    def price_lists(self, status: StatusFilter) -> list[PriceListOut]:
        counts = (
            select(PriceListItem.price_list_id, func.count(PriceListItem.id).label("item_count"))
            .where(PriceListItem.is_active)
            .group_by(PriceListItem.price_list_id)
            .subquery()
        )
        statement = (
            select(
                PriceList.id,
                PriceList.code,
                PriceList.name,
                PriceList.price_list_type,
                PriceList.principal_id,
                Principal.code.label("principal_code"),
                PriceList.includes_tax,
                PriceList.valid_from,
                PriceList.valid_to,
                func.coalesce(counts.c.item_count, 0).label("item_count"),
                PriceList.is_active,
                PriceList.row_version,
            )
            .outerjoin(Principal, Principal.id == PriceList.principal_id)
            .outerjoin(counts, counts.c.price_list_id == PriceList.id)
        )
        if self._actor.principal_ids is not None:
            statement = statement.where(
                or_(PriceList.principal_id.is_(None), PriceList.principal_id.in_(self._actor.principal_ids))
            )
        statement = _status(statement, PriceList.is_active, status).order_by(PriceList.code)
        return [PriceListOut.model_validate(row) for row in self._db.execute(statement).mappings()]

    def create_price_list(self, data: PriceListCreate) -> PriceListOut:
        code = data.code.upper()
        self._unique(PriceList, PriceList.code, code, None, f"Price list code '{code}' is already used.")
        if data.principal_id is not None and not self._actor.can_see_principal(data.principal_id):
            raise ApiError("You do not have access to that brand.", errors={"principalId": ["Not one of your brands."]})
        self._check_validity(data.valid_from, data.valid_to)
        row = PriceList(
            code=code,
            name=data.name,
            price_list_type=data.price_list_type,
            principal_id=data.principal_id,
            currency_id=self.currency_id(),
            includes_tax=data.includes_tax,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            created_by_user_id=self._actor.id,
        )
        self._save(row, f"Price list code '{code}' is already used.")
        return self._price_list(row.id)

    def update_price_list(self, price_list_id: int, expected: bytes, data: PriceListUpdate) -> PriceListOut:
        row = self._get(PriceList, price_list_id, "Price list not found.")
        check_row_version(row.row_version, expected)
        changed = data.model_fields_set
        valid_from = data.valid_from if "valid_from" in changed else row.valid_from
        valid_to = data.valid_to if "valid_to" in changed else row.valid_to
        self._check_validity(valid_from, valid_to)
        row.valid_from, row.valid_to = valid_from, valid_to
        self._apply(row, data, ("name", "price_list_type", "includes_tax", "is_active"))
        self._save(row, "The price list could not be saved.")
        return self._price_list(row.id)

    def _price_list(self, price_list_id: int) -> PriceListOut:
        return next(p for p in self.price_lists("all") if p.id == price_list_id)

    @staticmethod
    def _check_validity(valid_from: Any, valid_to: Any) -> None:
        if valid_from and valid_to and valid_to < valid_from:
            raise ApiError("The end date is before the start date.", errors={"validTo": ["Before the start date."]})

    def currency_id(self) -> int:
        currency_id = self._db.scalar(select(Currency.id).where(Currency.code == "INR"))
        if currency_id is None:
            currency_id = self._db.scalar(select(Currency.id).order_by(Currency.id).limit(1))
        if currency_id is None:
            raise ApiError("No currency is set up.")
        return int(currency_id)

    # ================================================================ lookups

    def adjustment_reasons(self) -> list[LookupOption]:
        statement = (
            select(LookupValue.id, LookupValue.code, LookupValue.label)
            .join(LookupType, LookupType.id == LookupValue.lookup_type_id)
            .where(LookupType.code == ADJUSTMENT_REASON, LookupValue.is_active)
            .order_by(LookupValue.sort_order, LookupValue.label)
        )
        return [LookupOption.model_validate(row) for row in self._db.execute(statement).mappings()]

    # ================================================================ helpers

    def _get(self, model: Any, row_id: int, message: str) -> Any:
        row = self._db.get(model, row_id)
        if row is None:
            raise NotFound(message)
        return row

    def _unique(self, model: Any, column: Any, value: str, own_id: int | None, message: str) -> None:
        statement = select(model.id).where(column == value)
        if own_id is not None:
            statement = statement.where(model.id != own_id)
        if self._db.scalar(statement.limit(1)) is not None:
            raise AlreadyExists(message)

    def _apply(self, row: Any, data: Any, fields: tuple[str, ...]) -> None:
        changed = data.model_fields_set
        for field in fields:
            if field not in changed:
                continue
            value = getattr(data, field)
            if value is None and field in (
                "name",
                "is_active",
                "decimals",
                "item_nature",
                "factor",
                "location_type",
                "is_stock_location",
                "supplier_type",
                "price_list_type",
                "includes_tax",
            ):
                continue  # required columns: null means "leave as is"
            setattr(row, field, value)
        row.updated_at = now()
        row.updated_by_user_id = self._actor.id

    def _save(self, row: Any, duplicate: str) -> None:
        self._db.add(row)
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(duplicate) from error
        self._db.refresh(row)
