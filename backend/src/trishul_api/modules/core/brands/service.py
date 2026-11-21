"""Companies & brands (core.principal): list, add, change and activate/deactivate.

A brand's code is unique (UX_core_principal_code). A brand belongs to a company (core.company); the
company's name is what the brand dropdowns show beside the brand name. core.principal is audited, so
every write is recorded.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import Company, Principal
from trishul_api.modules.core.brands.names import BRAND_COMPANY_NAME
from trishul_api.modules.core.brands.schemas import (
    BrandCompanyCreate,
    BrandCreate,
    BrandFormOptions,
    BrandItem,
    BrandUpdate,
    CompanyChoice,
)

_FIELDS = (
    "name",
    "company_id",
    "website",
    "handles_sales",
    "handles_service",
    "handles_parts",
    "inspection_report_required",
)


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


class BrandService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def form_options(self) -> BrandFormOptions:
        name = func.coalesce(Company.trade_name, Company.legal_name)
        rows = self._db.execute(select(Company.id, name.label("name")).where(Company.is_active).order_by(name)).all()
        return BrandFormOptions(companies=[CompanyChoice(id=r.id, name=r.name) for r in rows])

    def create_company(self, actor: CurrentUser, data: BrandCompanyCreate) -> CompanyChoice:
        code = data.code.strip().upper()
        if self._db.scalar(select(Company.id).where(Company.code == code)) is not None:
            raise AlreadyExists(f"Company code '{code}' is already in use.")
        legal_name = data.legal_name.strip()
        company = Company(
            code=code,
            legal_name=legal_name,
            trade_name=_clean(data.trade_name),
            created_by_user_id=actor.id,
        )
        self._db.add(company)
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("Another company already has this code.") from error
        return CompanyChoice(id=company.id, name=company.trade_name or company.legal_name)

    def list(self) -> list[BrandItem]:
        rows = self._db.execute(
            select(Principal, BRAND_COMPANY_NAME).order_by(Principal.is_active.desc(), Principal.name)
        ).all()
        return [self._item(brand, company) for brand, company in rows]

    def create(self, actor: CurrentUser, data: BrandCreate) -> BrandItem:
        code = data.code.strip().upper()
        self._check_code(code, None)
        self._check_company(data.company_id)
        brand = Principal(
            code=code,
            name=data.name.strip(),
            company_id=data.company_id,
            website=_clean(data.website),
            handles_sales=data.handles_sales,
            handles_service=data.handles_service,
            handles_parts=data.handles_parts,
            inspection_report_required=data.inspection_report_required,
            created_by_user_id=actor.id,
        )
        self._db.add(brand)
        return self._save(brand)

    def update(self, actor: CurrentUser, brand_id: int, expected_row_version: bytes, data: BrandUpdate) -> BrandItem:
        brand = self._require(brand_id)
        check_row_version(brand.row_version, expected_row_version)
        changed = data.model_fields_set
        if "code" in changed and data.code:
            code = data.code.strip().upper()
            self._check_code(code, brand.id)
            brand.code = code
        if "company_id" in changed:
            self._check_company(data.company_id)
        for field in _FIELDS:
            if field not in changed:
                continue
            value = getattr(data, field)
            if field == "website":
                value = _clean(value)
            elif field == "name":
                value = (value or brand.name).strip()
            elif value is None and field != "company_id":
                continue
            setattr(brand, field, value)
        return self._save(brand, actor)

    def set_active(self, actor: CurrentUser, brand_id: int, active: bool) -> BrandItem:
        brand = self._require(brand_id)
        if brand.is_active != active:
            brand.is_active = active
            return self._save(brand, actor)
        return self._item(brand, self._company_name(brand))

    def _require(self, brand_id: int) -> Principal:
        brand = self._db.get(Principal, brand_id)
        if brand is None:
            raise NotFound("Brand not found.")
        return brand

    def _check_code(self, code: str, brand_id: int | None) -> None:
        owner = self._db.scalar(select(Principal.id).where(Principal.code == code))
        if owner is not None and owner != brand_id:
            raise AlreadyExists(f"Brand code '{code}' is already in use.")

    def _check_company(self, company_id: int | None) -> None:
        if company_id is None:
            return
        found = self._db.scalar(select(Company.id).where(Company.id == company_id, Company.is_active))
        if found is None:
            raise ApiError("Choose one of the listed companies.", errors={"companyId": ["Unknown company."]})

    def _company_name(self, brand: Principal) -> str | None:
        return self._db.scalar(select(BRAND_COMPANY_NAME).where(Principal.id == brand.id))

    @staticmethod
    def _item(brand: Principal, company_name: str | None) -> BrandItem:
        return BrandItem(
            id=brand.id,
            code=brand.code,
            name=brand.name,
            company_id=brand.company_id,
            company_name=company_name,
            website=brand.website,
            handles_sales=brand.handles_sales,
            handles_service=brand.handles_service,
            handles_parts=brand.handles_parts,
            inspection_report_required=brand.inspection_report_required,
            is_active=brand.is_active,
            row_version=brand.row_version,
        )

    def _save(self, brand: Principal, actor: CurrentUser | None = None) -> BrandItem:
        if actor is not None:
            brand.updated_by_user_id = actor.id
            brand.updated_at = datetime.now(UTC).replace(tzinfo=None)
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("Another brand already has this code.") from error
        self._db.refresh(brand)
        return self._item(brand, self._company_name(brand))
