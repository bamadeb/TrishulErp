from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion


class BrandItem(ApiModel):
    id: int
    code: str
    name: str
    company_id: int | None
    company_name: str | None
    website: str | None
    handles_sales: bool
    handles_service: bool
    handles_parts: bool
    inspection_report_required: bool
    is_active: bool
    row_version: RowVersion


class CompanyChoice(ApiModel):
    id: int
    name: str


class BrandCompanyCreate(InputModel):
    code: str = Field(min_length=1, max_length=10, description="Short unique company code, e.g. KASI.")
    legal_name: str = Field(min_length=1, max_length=200, description="Registered legal name.")
    trade_name: str | None = Field(None, max_length=200, description="Shown beside brands; legal name if blank.")


class BrandFormOptions(ApiModel):
    companies: list[CompanyChoice]


class BrandCreate(InputModel):
    code: str = Field(min_length=1, max_length=20, description="Unique brand code, e.g. TATA_HITACHI.")
    name: str = Field(min_length=1, max_length=120)
    company_id: int | None = None
    website: str | None = Field(None, max_length=200)
    handles_sales: bool = True
    handles_service: bool = True
    handles_parts: bool = True
    inspection_report_required: bool = True


class BrandUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=20)
    name: str | None = Field(None, min_length=1, max_length=120)
    company_id: int | None = None
    website: str | None = Field(None, max_length=200)
    handles_sales: bool | None = None
    handles_service: bool | None = None
    handles_parts: bool | None = None
    inspection_report_required: bool | None = None
