"""The company name shown beside a brand: its company's trade name, or the legal name when there is none."""

from sqlalchemy import func, select

from trishul_api.db.models import Company, Principal

BRAND_COMPANY_NAME = (
    select(func.coalesce(Company.trade_name, Company.legal_name))
    .where(Company.id == Principal.company_id)
    .correlate(Principal)
    .scalar_subquery()
    .label("company_name")
)
