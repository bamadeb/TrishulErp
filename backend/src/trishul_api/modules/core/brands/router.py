from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.modules.core.brands.schemas import (
    BrandCompanyCreate,
    BrandCreate,
    BrandFormOptions,
    BrandItem,
    BrandUpdate,
    CompanyChoice,
)
from trishul_api.modules.core.brands.service import BrandService

router = APIRouter(prefix="/core", tags=["brands"])

CAN_MANAGE = Depends(require_permission("core.brand.manage"))
BrandId = Annotated[int, Path(alias="brandId")]


def get_brand_service(db: DbSession) -> BrandService:
    return BrandService(db)


Brands = Annotated[BrandService, Depends(get_brand_service)]


@router.get("/brands", summary="Companies and brands, including inactive ones", dependencies=[CAN_MANAGE])
def list_brands(brands: Brands) -> list[BrandItem]:
    return brands.list()


# Declared before /brands/{brandId} so "form-options" is not read as a brand id.
@router.get("/brands/form-options", summary="Dropdown values for the brand form", dependencies=[CAN_MANAGE])
def get_brand_form_options(brands: Brands) -> BrandFormOptions:
    return brands.form_options()


@router.post("/brands/companies", summary="Add a company", status_code=201, dependencies=[CAN_MANAGE])
def create_brand_company(data: BrandCompanyCreate, actor: CurrentUserDep, brands: Brands) -> CompanyChoice:
    return brands.create_company(actor, data)


@router.post("/brands", summary="Add a brand", status_code=201, dependencies=[CAN_MANAGE])
def create_brand(data: BrandCreate, actor: CurrentUserDep, brands: Brands, response: Response) -> BrandItem:
    created = brands.create(actor, data)
    response.headers["Location"] = f"brands/{created.id}"
    return created


@router.patch(
    "/brands/{brandId}",
    summary="Change a brand or its company",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_brand(
    brand_id: BrandId,
    data: BrandUpdate,
    actor: CurrentUserDep,
    brands: Brands,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> BrandItem:
    return brands.update(actor, brand_id, row_version, data)


@router.post(
    "/brands/{brandId}/deactivate",
    summary="Mark a brand inactive",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_brand(brand_id: BrandId, actor: CurrentUserDep, brands: Brands) -> BrandItem:
    return brands.set_active(actor, brand_id, False)


@router.post(
    "/brands/{brandId}/activate",
    summary="Mark a brand active again",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def activate_brand(brand_id: BrandId, actor: CurrentUserDep, brands: Brands) -> BrandItem:
    return brands.set_active(actor, brand_id, True)
